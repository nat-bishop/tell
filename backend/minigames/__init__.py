"""Minigame registry — maps round types to handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schemas.game_state import RoundType

from backend.minigames.base import MinigameHandler
from backend.minigames.base import MinigameMeta as MinigameMeta

MINIGAME_REGISTRY: dict[RoundType, MinigameHandler] = {}


def register(handler: MinigameHandler) -> None:
    MINIGAME_REGISTRY[handler.round_type] = handler


def get_handler(round_type: RoundType) -> MinigameHandler:
    return MINIGAME_REGISTRY[round_type]


def _register_builtins() -> None:
    from backend.minigames.brain_test import BrainTestHandler
    from backend.minigames.task import TaskHandler
    from backend.minigames.wager import WagerHandler

    register(TaskHandler())
    register(BrainTestHandler())
    register(WagerHandler())


_register_builtins()
