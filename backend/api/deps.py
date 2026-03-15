"""Shared dependencies — singletons for services."""

from __future__ import annotations

from functools import lru_cache

from backend.config import Settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Stubs — filled in Wave 2
def get_game_repository():
    raise NotImplementedError("GameRepository not yet implemented")


def get_connection_manager():
    raise NotImplementedError("ConnectionManager not yet implemented")


def get_timer_manager():
    raise NotImplementedError("TimerManager not yet implemented")
