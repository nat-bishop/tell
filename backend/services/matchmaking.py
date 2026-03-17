"""Matchmaking service — rolling lobby that groups players into games."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

import structlog

from backend.api.deps import get_connection_manager, get_game_repository, get_settings
from schemas.aliases import generate_aliases, generate_game_id, generate_player_id
from schemas.api_models import (
    GameAssignedEvent,
    LobbyStatusEvent,
    MatchmakingJoinResponse,
)
from schemas.constants import MATCHMAKING_LOBBY_ID
from schemas.game_state import GamePhase, Player, PlayerRole, TellGameState

log = structlog.get_logger(__name__)


@dataclass
class QueuedPlayer:
    player_id: str
    alias: str


class MatchmakingService:
    """Rolling lobby matchmaking — players gather, countdown fires, game starts."""

    def __init__(self) -> None:
        self._queue: list[QueuedPlayer] = []
        self._queue_lock: asyncio.Lock = asyncio.Lock()
        self._countdown_task: asyncio.Task | None = None
        self._solo_timeout_task: asyncio.Task | None = None
        self._join_window_open: asyncio.Event = asyncio.Event()
        self._join_window_open.set()  # starts open
        self._seq: int = 0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def initialize(self) -> None:
        """Set up the lobby SSE infrastructure."""
        cm = get_connection_manager()
        cm.get_lock(MATCHMAKING_LOBBY_ID)
        log.info("matchmaking_initialized")

    @property
    def human_count(self) -> int:
        return len(self._queue)

    async def join(self, player_name: str) -> MatchmakingJoinResponse:
        """Add a player to the matchmaking queue."""
        await asyncio.wait_for(self._join_window_open.wait(), timeout=5.0)

        player_id = generate_player_id()

        async with self._queue_lock:
            existing_aliases = {p.alias for p in self._queue}
            aliases = generate_aliases(1, existing_aliases)
            alias = aliases[0]

            entry = QueuedPlayer(player_id=player_id, alias=alias)
            self._queue.append(entry)
            queue_size = len(self._queue)

        log.info("matchmaking_joined", alias=alias, queue_size=queue_size)
        await self._on_player_change(queue_size)

        return MatchmakingJoinResponse(
            player_id=player_id,
            alias=alias,
            position=queue_size,
        )

    async def leave(self, player_id: str) -> None:
        """Remove a player from the matchmaking queue."""
        async with self._queue_lock:
            before = len(self._queue)
            self._queue = [p for p in self._queue if p.player_id != player_id]
            if len(self._queue) == before:
                return  # player wasn't in queue — skip side effects
            queue_size = len(self._queue)

        log.info("matchmaking_left", player_id=player_id, queue_size=queue_size)
        cm = get_connection_manager()
        cm.disconnect(MATCHMAKING_LOBBY_ID, player_id)
        await self._on_player_change(queue_size)

    async def _on_player_change(self, count: int) -> None:
        """Check thresholds after any join/leave and manage countdown."""
        settings = get_settings()

        if count >= settings.mm_min_humans and self._countdown_task is None:
            await self._start_countdown(count)
            return
        elif count < settings.mm_min_humans and self._countdown_task is not None:
            self._cancel_countdown()

        # Solo timeout: if exactly 1 player, start a timeout
        if count == 1 and self._solo_timeout_task is None:
            self._solo_timeout_task = asyncio.create_task(self._solo_timeout())
        elif count != 1 and self._solo_timeout_task is not None:
            self._solo_timeout_task.cancel()
            self._solo_timeout_task = None

        if count == 0:
            return

        if self._countdown_task is None:
            await self._broadcast_status(f"{count} assembled — waiting for more", count=count)

    async def _start_countdown(self, count: int) -> None:
        """Begin the countdown to game creation."""
        settings = get_settings()
        seconds = settings.mm_countdown_seconds
        log.info("matchmaking_countdown_started", seconds=seconds)
        await self._broadcast_status(
            f"{count} assembled — game begins shortly",
            countdown_seconds=seconds,
            count=count,
        )
        self._countdown_task = asyncio.create_task(self._countdown_timer(seconds))

    def _cancel_countdown(self) -> None:
        if self._countdown_task:
            self._countdown_task.cancel()
            self._countdown_task = None
            log.info("matchmaking_countdown_cancelled")

    async def _countdown_timer(self, seconds: int) -> None:
        """Wait for the countdown, then fire a game."""
        try:
            await asyncio.sleep(seconds)
            await self._fire_game()
        except asyncio.CancelledError:
            pass
        finally:
            self._countdown_task = None

    async def _solo_timeout(self) -> None:
        """After waiting solo, offer to start with AI companions."""
        settings = get_settings()
        try:
            await asyncio.sleep(settings.mm_solo_timeout_seconds)
            if self.human_count == 1:
                await self._broadcast_status(
                    "no others yet — starting with AI companions",
                    countdown_seconds=5,
                )
                await asyncio.sleep(5)
                if self.human_count >= 1:
                    await self._fire_game()
        except asyncio.CancelledError:
            pass
        finally:
            self._solo_timeout_task = None

    async def _fire_game(self) -> None:
        """Pop all queued players, create a real game, add AI, start it."""
        from backend.services.transitions import initialize_and_start_game

        self._join_window_open.clear()
        settings = get_settings()
        cm = get_connection_manager()

        try:
            # Snapshot and clear queue
            async with self._queue_lock:
                players = list(self._queue)
                self._queue.clear()
            self._cancel_countdown()
            if self._solo_timeout_task:
                self._solo_timeout_task.cancel()
                self._solo_timeout_task = None

            if not players:
                return

            # Cap humans
            human_count = min(len(players), settings.mm_max_humans)
            players = players[:human_count]

            # Randomized AI count: total ∈ [min_total, max_total], ai >= 1
            target_total = random.randint(settings.mm_min_total, settings.mm_max_total)
            ai_count = max(1, target_total - human_count)

            # Create game
            repo = get_game_repository()
            game_id = generate_game_id()
            game_state = TellGameState(game_id=game_id, phase=GamePhase.LOBBY, players=[])
            repo.create(game_state)

            # Add human players to the game
            lock = cm.get_lock(game_id)
            async with lock:
                session = repo.get(game_id)
                if not session:
                    return
                for p in players:
                    player = Player(
                        id=p.player_id,
                        alias=p.alias,
                        role=PlayerRole.HUMAN,
                        is_connected=True,
                    )
                    session.state.players.append(player)

            # Start the game (spawns AI, assigns personalities, transitions to PROMPT)
            await initialize_and_start_game(game_id, ai_count)

            # Notify lobby SSE clients AFTER successful game init
            event = GameAssignedEvent(
                seq=self._next_seq(),
                game_id=game_id,
            )
            await cm.broadcast(MATCHMAKING_LOBBY_ID, event)

            log.info(
                "matchmaking_game_created",
                game_id=game_id,
                human_count=human_count,
                ai_count=ai_count,
            )

        finally:
            # Disconnect all lobby SSE clients and reopen
            for pid in list(cm.get_connected_players(MATCHMAKING_LOBBY_ID)):
                cm.disconnect(MATCHMAKING_LOBBY_ID, pid)
            self._join_window_open.set()

    async def _broadcast_status(
        self,
        message: str,
        countdown_seconds: int | None = None,
        count: int | None = None,
    ) -> None:
        """Send a lobby status update to all connected matchmaking clients."""
        cm = get_connection_manager()
        event = LobbyStatusEvent(
            seq=self._next_seq(),
            human_count=count if count is not None else self.human_count,
            countdown_seconds=countdown_seconds,
            message=message,
        )
        await cm.broadcast(MATCHMAKING_LOBBY_ID, event)

    def get_status(self) -> dict:
        """Current lobby state for the status endpoint."""
        settings = get_settings()
        return {
            "human_count": self.human_count,
            "min_humans": settings.mm_min_humans,
            "max_humans": settings.mm_max_humans,
            "countdown_active": self._countdown_task is not None,
            "queue_open": self._join_window_open.is_set(),
        }
