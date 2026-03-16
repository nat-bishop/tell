"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from tests.factories import make_game_state, make_player, make_round_state, make_standard_game


@pytest.fixture
def standard_game():
    """4-player game (2 human, 2 AI) in PROMPT phase."""
    return make_standard_game()


@pytest.fixture
def game_state():
    """Bare game state factory — call with kwargs to customize."""
    return make_game_state


@pytest.fixture
def player():
    """Player factory — call with kwargs to customize."""
    return make_player


@pytest.fixture
def round_state():
    """RoundState factory — call with kwargs to customize."""
    return make_round_state
