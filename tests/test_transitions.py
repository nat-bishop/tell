"""Tests for backend/services/transitions.py — async phase transition sequences."""

from __future__ import annotations

from backend.api.deps import get_connection_manager, get_game_repository
from backend.services.game_repository import TellGameSession
from schemas.game_state import (
    GamePhase,
    RoundType,
)
from tests.factories import make_game_state, make_player, make_standard_game


def _make_session(phase, round_type=RoundType.TASK, **round_kwargs):
    """Create a game state + session at a given phase."""
    state, players = make_standard_game(phase=phase, round_type=round_type)
    for k, v in round_kwargs.items():
        setattr(state.current_round, k, v)
    session = TellGameSession(state=state)
    return state, session, players


def _store_session(session):
    """Store a session in the repo + create CM lock."""
    repo = get_game_repository()
    repo._games[session.state.game_id] = session
    cm = get_connection_manager()
    cm.get_lock(session.state.game_id)
    cm.connect(session.state.game_id, "__test__")
    return session.state.game_id


def _get_broadcast_events(game_id):
    """Read all broadcast events from the CM event log."""
    cm = get_connection_manager()
    events = cm.get_events_after(game_id, 0)
    return events or []


# ---------------------------------------------------------------------------
# do_prompt_complete
# ---------------------------------------------------------------------------


class TestDoPromptComplete:
    async def test_task_round_goes_to_active(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_prompt_complete

        _state, session, _ = _make_session(
            GamePhase.PROMPT,
            round_type=RoundType.TASK,
            answers={"h1": "a", "h2": "b", "a1": "c", "a2": "d"},
        )
        game_id = _store_session(session)
        await do_prompt_complete(game_id, session)

        assert session.state.phase == GamePhase.ACTIVE


# ---------------------------------------------------------------------------
# do_active_complete — scoring + next round or game over
# ---------------------------------------------------------------------------


class TestDoActiveComplete:
    async def test_task_scores_and_advances(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_active_complete
        from schemas.game_state import Matchup

        _state, session, _ = _make_session(GamePhase.ACTIVE, round_type=RoundType.TASK)
        session.state.current_round.matchups = [
            Matchup(
                pair=["h1", "h2"],
                prompt_text="test",
                prompt_category="test",
                votes={"a1": 0, "a2": 0},  # h1 wins
            ),
            Matchup(
                pair=["a1", "a2"],
                prompt_text="test2",
                prompt_category="test",
                votes={"h1": 1, "h2": 1},  # a2 wins
            ),
        ]
        session.state.round_number = 1
        session.state.total_rounds = 5
        session.state.round_types = [RoundType.TASK]
        game_id = _store_session(session)
        await do_active_complete(game_id, session)

        # Should advance to a new round
        assert session.state.phase in (GamePhase.PROMPT, GamePhase.ACTIVE)
        assert session.state.round_number == 2

        # Check scores were applied
        h1 = next(p for p in session.state.players if p.id == "h1")
        assert h1.score == 1

        events = _get_broadcast_events(game_id)
        event_types = [e.event_type for e in events]
        assert "round_results" in event_types

    async def test_game_over_after_final_round(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_active_complete
        from schemas.game_state import Matchup

        _state, session, _ = _make_session(GamePhase.ACTIVE, round_type=RoundType.TASK)
        session.state.current_round.matchups = [
            Matchup(
                pair=["h1", "h2"],
                prompt_text="test",
                prompt_category="test",
                votes={"a1": 0, "a2": 0},
            ),
        ]
        session.state.round_number = 5
        session.state.total_rounds = 5
        session.state.players[0].score = 3  # h1 leading
        game_id = _store_session(session)
        await do_active_complete(game_id, session)

        assert session.state.phase == GamePhase.GAME_OVER
        assert session.state.winner == "winners"
        assert "h1" in session.state.winner_ids

    async def test_brain_test_scores_and_shows_results(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_active_complete
        from schemas.game_state import BrainTestChallenge

        _state, session, _ = _make_session(GamePhase.ACTIVE, round_type=RoundType.BRAIN_TEST)
        session.state.current_round.brain_challenges = [
            BrainTestChallenge(
                challenge_type="trick",
                question="2+2?",
                options=["3", "4", "5", "6"],
                correct_index=1,
                responses={"h1": 1, "h2": 0, "a1": 1, "a2": 2},
            ),
            BrainTestChallenge(
                challenge_type="trick",
                question="Capital of France?",
                options=["London", "Paris", "Berlin", "Madrid"],
                correct_index=1,
                responses={"h1": 1, "h2": 1, "a1": 0, "a2": 1},
            ),
        ]
        game_id = _store_session(session)
        await do_active_complete(game_id, session)

        assert session.state.phase == GamePhase.RESULTS

        events = _get_broadcast_events(game_id)
        event_types = [e.event_type for e in events]
        assert "round_results" in event_types

        # Check scores in the results event
        results_event = next(e for e in events if e.event_type == "round_results")
        assert results_event.scores is not None
        # h1 got both right = 2
        assert results_event.scores["h1"] == 2

    async def test_brain_test_no_correct_answers(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_active_complete
        from schemas.game_state import BrainTestChallenge

        _state, session, _ = _make_session(GamePhase.ACTIVE, round_type=RoundType.BRAIN_TEST)
        session.state.current_round.brain_challenges = [
            BrainTestChallenge(
                challenge_type="trick",
                question="Impossible?",
                options=["A", "B", "C", "D"],
                correct_index=3,
                responses={"h1": 0, "h2": 1, "a1": 2, "a2": 0},
            ),
        ]
        game_id = _store_session(session)
        await do_active_complete(game_id, session)

        assert session.state.phase == GamePhase.RESULTS

        events = _get_broadcast_events(game_id)
        results_event = next(e for e in events if e.event_type == "round_results")
        # All wrong — all scores should be 0
        for pid in ("h1", "h2", "a1", "a2"):
            assert results_event.scores[pid] == 0


# ---------------------------------------------------------------------------
# do_results_complete — next round or game over
# ---------------------------------------------------------------------------


class TestDoResultsComplete:
    async def test_advances_to_next_round(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_results_complete

        _state, session, _ = _make_session(GamePhase.RESULTS, round_type=RoundType.BRAIN_TEST)
        session.state.round_number = 2
        session.state.total_rounds = 5
        session.state.round_types = [RoundType.BRAIN_TEST]
        game_id = _store_session(session)
        await do_results_complete(game_id, session)

        assert session.state.phase in (GamePhase.PROMPT, GamePhase.ACTIVE)
        assert session.state.round_number == 3

    async def test_game_over_after_final_round(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_results_complete

        _state, session, _ = _make_session(GamePhase.RESULTS, round_type=RoundType.BRAIN_TEST)
        session.state.round_number = 5
        session.state.total_rounds = 5
        session.state.players[0].score = 4  # h1 leading
        game_id = _store_session(session)
        await do_results_complete(game_id, session)

        assert session.state.phase == GamePhase.GAME_OVER
        assert session.state.winner == "winners"
        assert "h1" in session.state.winner_ids


# ---------------------------------------------------------------------------
# initialize_and_start_game
# ---------------------------------------------------------------------------


class TestInitializeAndStartGame:
    async def test_adds_ai_players_and_starts(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import initialize_and_start_game

        state = make_game_state(
            game_id="init_test",
            phase=GamePhase.LOBBY,
            round_number=0,
            current_round=None,
            players=[
                make_player(role="human", player_id="h1", is_host=True, alias="UNIT-01"),
                make_player(role="human", player_id="h2", alias="BOT-42"),
            ],
        )
        repo = get_game_repository()
        session = repo.create(state)
        cm = get_connection_manager()
        cm.get_lock("init_test")
        cm.connect("init_test", "__test__")

        await initialize_and_start_game("init_test", 2)

        assert session.state.phase in (
            GamePhase.PROMPT,
            GamePhase.ACTIVE,
        )
        assert len(session.state.players) == 4  # 2 human + 2 AI
        assert session.state.round_number == 1
        assert len(session.state.round_types) >= 1  # dynamically grown
        assert session.state.total_rounds == 5

        mock_ai["assign_personalities"].assert_called_once()


# ---------------------------------------------------------------------------
# _start_next_round
# ---------------------------------------------------------------------------


class TestStartNextRound:
    async def test_advances_round_number(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import _start_next_round

        _state, session, _ = _make_session(GamePhase.ACTIVE, round_type=RoundType.TASK)
        session.state.round_types = [RoundType.TASK]
        session.state.round_number = 1
        game_id = _store_session(session)
        await _start_next_round(game_id, session)

        assert session.state.round_number == 2
        assert session.state.phase in (GamePhase.PROMPT, GamePhase.ACTIVE)
