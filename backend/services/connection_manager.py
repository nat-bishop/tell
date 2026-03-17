"""Per-game asyncio.Queue broadcast hub with event log for reconnection."""

from __future__ import annotations

import asyncio
from collections import deque

import structlog

from schemas.api_models import GameEvent

log = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages SSE connections: per-game queues, locks, and event logs."""

    def __init__(self) -> None:
        # game_id -> {player_id -> Queue}
        self._connections: dict[str, dict[str, asyncio.Queue[GameEvent | None]]] = {}
        # game_id -> Lock (serializes state mutations)
        self._locks: dict[str, asyncio.Lock] = {}
        # game_id -> deque of recent events (for reconnection replay)
        self._event_logs: dict[str, deque[GameEvent]] = {}
        # game_id -> full event list (for game recording)
        self._recordings: dict[str, list[GameEvent]] = {}

    def get_lock(self, game_id: str) -> asyncio.Lock:
        if game_id not in self._locks:
            self._locks[game_id] = asyncio.Lock()
        return self._locks[game_id]

    def connect(self, game_id: str, player_id: str) -> asyncio.Queue[GameEvent | None]:
        if game_id not in self._connections:
            self._connections[game_id] = {}
            self._event_logs[game_id] = deque(maxlen=200)
            self._recordings[game_id] = []
        queue: asyncio.Queue[GameEvent | None] = asyncio.Queue()
        self._connections[game_id][player_id] = queue
        log.info("player_connected", game_id=game_id, player_id=player_id)
        return queue

    def disconnect(self, game_id: str, player_id: str) -> None:
        conns = self._connections.get(game_id, {})
        conns.pop(player_id, None)
        log.info("player_disconnected", game_id=game_id, player_id=player_id)

    async def broadcast(self, game_id: str, event: GameEvent) -> None:
        """Send event to all connected clients in a game and log it."""
        if game_id in self._event_logs:
            self._event_logs[game_id].append(event)
        if game_id in self._recordings:
            self._recordings[game_id].append(event)
        conns = self._connections.get(game_id, {})
        for pid, queue in conns.items():
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                log.warning("queue_full", game_id=game_id, player_id=pid)

    async def send_to(self, game_id: str, player_id: str, event: GameEvent) -> None:
        """Send event to a specific player."""
        conns = self._connections.get(game_id, {})
        queue = conns.get(player_id)
        if queue:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                log.warning("queue_full", game_id=game_id, player_id=player_id)

    def get_events_after(self, game_id: str, seq: int) -> list[GameEvent] | None:
        """Get events after a sequence number for replay. Returns None if seq is too old."""
        event_log = self._event_logs.get(game_id)
        if event_log is None:
            return None
        events = [e for e in event_log if e.seq > seq]
        if not events and seq > 0:
            # Check if we have events at all — if the oldest event seq > requested seq,
            # the client missed too many events
            if event_log and event_log[0].seq > seq:
                return None  # Force full state sync
        return events

    def get_connected_players(self, game_id: str) -> set[str]:
        return set(self._connections.get(game_id, {}).keys())

    def pop_recording(self, game_id: str) -> list[GameEvent]:
        """Return and remove the full event recording for a game."""
        return self._recordings.pop(game_id, [])

    def cleanup_game(self, game_id: str) -> None:
        """Remove all data for a game."""
        self._connections.pop(game_id, None)
        self._locks.pop(game_id, None)
        self._event_logs.pop(game_id, None)
        self._recordings.pop(game_id, None)
