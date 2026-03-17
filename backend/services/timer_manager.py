"""Phase timer management — asyncio tasks that fire on phase expiry."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import structlog

log = structlog.get_logger(__name__)


class TimerManager:
    """Manages one timer task per game. Fires a callback on expiry."""

    def __init__(self) -> None:
        self._timers: dict[str, asyncio.Task] = {}

    def start_timer(
        self,
        game_id: str,
        duration: int,
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        """Start a timer for a game phase. Cancels any existing timer for the game."""
        self.cancel_timer(game_id)

        async def _run():
            try:
                await asyncio.sleep(duration)
                await callback()
            except asyncio.CancelledError:
                pass
            except Exception:
                log.exception("timer_callback_error", game_id=game_id)

        self._timers[game_id] = asyncio.create_task(_run())
        log.info("timer_started", game_id=game_id, duration=duration)

    def cancel_timer(self, game_id: str) -> None:
        """Cancel the active timer for a game."""
        task = self._timers.pop(game_id, None)
        if task and not task.done():
            task.cancel()
            log.info("timer_cancelled", game_id=game_id)

    def cleanup_game(self, game_id: str) -> None:
        self.cancel_timer(game_id)
