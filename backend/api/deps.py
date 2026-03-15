"""Shared dependencies — singletons for services."""

from __future__ import annotations

from functools import lru_cache

from backend.config import Settings
from backend.services.connection_manager import ConnectionManager
from backend.services.game_repository import GameRepository
from backend.services.timer_manager import TimerManager

_connection_manager: ConnectionManager | None = None
_game_repository: GameRepository | None = None
_timer_manager: TimerManager | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def get_connection_manager() -> ConnectionManager:
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager


def get_game_repository() -> GameRepository:
    global _game_repository
    if _game_repository is None:
        _game_repository = GameRepository()
    return _game_repository


def get_timer_manager() -> TimerManager:
    global _timer_manager
    if _timer_manager is None:
        _timer_manager = TimerManager()
    return _timer_manager
