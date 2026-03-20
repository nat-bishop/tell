"""Shared pytest fixtures."""

from __future__ import annotations

import os

# Ensure logfire is disabled before any backend module is imported at module-load time
os.environ.setdefault("TELL_LOGFIRE_ENABLED", "false")

from unittest.mock import AsyncMock, patch

import pytest

from tests.factories import make_game_state, make_player, make_round_state, make_standard_game


@pytest.fixture
def standard_game():
    """4-player game (2 human, 2 AI) in ROUND phase."""
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


# ---------------------------------------------------------------------------
# Integration test infrastructure
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_deps():
    """Reset singleton globals in deps.py between tests."""
    import backend.api.deps as deps
    from backend.services.connection_manager import ConnectionManager
    from backend.services.game_repository import GameRepository
    from backend.services.timer_manager import TimerManager

    deps._connection_manager = ConnectionManager()
    deps._game_repository = GameRepository()
    deps._timer_manager = TimerManager()
    deps._matchmaking_service = None
    deps.get_settings.cache_clear()

    yield

    deps._connection_manager = None
    deps._game_repository = None
    deps._timer_manager = None
    deps._matchmaking_service = None
    deps.get_settings.cache_clear()


@pytest.fixture
def mock_ai():
    """Patch AI scheduler functions to no-ops."""
    with (
        patch(
            "backend.services.ai_scheduler.schedule_ai_answers",
            new_callable=AsyncMock,
        ) as mock_answers,
        patch(
            "backend.services.ai_scheduler.schedule_ai_votes",
            new_callable=AsyncMock,
        ) as mock_votes,
        patch(
            "backend.services.ai_scheduler.assign_personalities",
        ) as mock_assign,
        patch(
            "backend.services.ai_scheduler.register_task",
        ) as mock_register,
        patch(
            "backend.services.ai_scheduler.cleanup_game",
        ) as mock_cleanup,
        patch(
            "backend.services.ai_scheduler.on_brain_test_challenge",
            new_callable=AsyncMock,
        ) as mock_bt,
        patch(
            "backend.services.ai_scheduler.on_wager_guess",
            new_callable=AsyncMock,
        ) as mock_wg,
        patch(
            "backend.services.ai_scheduler.on_wager_bet",
            new_callable=AsyncMock,
        ) as mock_wb,
        patch(
            "backend.services.ai_scheduler.on_signal_sub_round",
            new_callable=AsyncMock,
        ) as mock_ss,
    ):
        yield {
            "schedule_ai_answers": mock_answers,
            "schedule_ai_votes": mock_votes,
            "assign_personalities": mock_assign,
            "register_task": mock_register,
            "cleanup_game": mock_cleanup,
            "on_brain_test_challenge": mock_bt,
            "on_wager_guess": mock_wg,
            "on_wager_bet": mock_wb,
            "on_signal_sub_round": mock_ss,
        }


@pytest.fixture
def mock_llm():
    """Patch LLM agent functions used in transitions."""
    with (
        patch(
            "backend.llm.agents.generate_narration",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_narration,
    ):
        yield {
            "generate_narration": mock_narration,
        }


@pytest.fixture
async def client(fresh_deps):
    """Async HTTP client for route tests."""
    from httpx import ASGITransport, AsyncClient

    from backend.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


def seed_game(phase, round_type=None, current_step_index=None, **kwargs):
    """Create a game directly in the repo at a given phase. Returns (game_id, session, players)."""
    from backend.api.deps import get_connection_manager, get_game_repository

    state, players = make_standard_game(
        phase=phase,
        round_type=round_type or "task",
        current_step_index=current_step_index,
    )
    # Apply any extra kwargs to the state
    for k, v in kwargs.items():
        if hasattr(state, k):
            setattr(state, k, v)
    repo = get_game_repository()
    session = repo.create(state)
    cm = get_connection_manager()
    cm.get_lock(state.game_id)
    return state.game_id, session, players
