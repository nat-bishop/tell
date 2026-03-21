"""Tests for backend/services/transitions.py — step-based transition sequences."""

from __future__ import annotations

from backend.api.deps import get_connection_manager, get_game_repository
from backend.services.game_repository import TellGameSession
from schemas.game_state import (
    GamePhase,
    RoundType,
)
from tests.factories import make_game_state, make_player, make_standard_game


def _make_session(phase, round_type=RoundType.TASK, current_step_index=None, **round_kwargs):
    """Create a game state + session at a given phase."""
    state, players = make_standard_game(
        phase=phase, round_type=round_type, current_step_index=current_step_index
    )
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
# try_advance_step — compose step early completion
# ---------------------------------------------------------------------------


class TestTryAdvanceStep:
    async def test_task_compose_early_complete(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import try_advance_step

        _state, session, _ = _make_session(
            GamePhase.ROUND,
            round_type=RoundType.TASK,
            current_step_index=1,  # compose step (after preroll)
            answers={
                "h1": "a",
                "h2": "b",
                "a1": "c",
                "a2": "d",
                "a3": "e",
                "a4": "f",
                "a5": "g",
                "a6": "h",
            },
        )
        game_id = _store_session(session)

        cm = get_connection_manager()
        lock = cm.get_lock(game_id)
        async with lock:
            await try_advance_step(game_id, session)

        # Should have advanced to vote step
        assert session.state.current_step_index == 2
        step = session.state.round_step_defs[2]
        assert step["name"] == "vote"


# ---------------------------------------------------------------------------
# _handle_step_expiry — scoring + results transition
# ---------------------------------------------------------------------------


class TestHandleStepExpiry:
    async def test_vote_expiry_scores_and_goes_to_results(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import _handle_step_expiry

        _state, session, _ = _make_session(
            GamePhase.ROUND,
            round_type=RoundType.TASK,
            current_step_index=2,  # vote step (after preroll + compose)
        )
        session.state.current_round.gallery_votes = {
            "h2": "h1",
            "a1": "h1",
            "a2": "h1",
        }
        session.state.round_number = 1
        session.state.total_rounds = 5
        session.state.round_types = [RoundType.TASK]
        game_id = _store_session(session)
        await _handle_step_expiry(game_id)

        # Should be on results step
        assert session.state.current_step_index == 3
        step = session.state.round_step_defs[3]
        assert step["name"] == "results"

        # Check scores: h1 got 3 votes = -300
        h1 = next(p for p in session.state.players if p.id == "h1")
        assert h1.score == -300

        events = _get_broadcast_events(game_id)
        event_types = [e.event_type for e in events]
        assert "round_results" in event_types


# ---------------------------------------------------------------------------
# Results step expiry — next round or game over
# ---------------------------------------------------------------------------


class TestResultsStepExpiry:
    async def test_starts_next_round(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import _handle_step_expiry

        _state, session, _ = _make_session(
            GamePhase.ROUND,
            round_type=RoundType.TASK,
            current_step_index=3,  # results step (after preroll + compose + vote)
        )
        session.state.round_number = 2
        session.state.total_rounds = 5
        session.state.round_types = [RoundType.TASK]
        game_id = _store_session(session)
        await _handle_step_expiry(game_id)

        assert session.state.phase == GamePhase.ROUND
        assert session.state.round_number == 3

    async def test_game_over_after_final_round(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import _handle_step_expiry

        _state, session, _ = _make_session(
            GamePhase.ROUND,
            round_type=RoundType.TASK,
            current_step_index=3,  # results step (after preroll + compose + vote)
        )
        session.state.round_number = 5
        session.state.total_rounds = 5
        session.state.players[0].score = 3  # h1 leading
        game_id = _store_session(session)
        await _handle_step_expiry(game_id)

        assert session.state.phase == GamePhase.GAME_OVER
        assert session.state.winner == "winners"
        assert "h1" in session.state.winner_ids


# ---------------------------------------------------------------------------
# Brain test scoring via step expiry
# ---------------------------------------------------------------------------


class TestBrainTestStepExpiry:
    async def test_scores_brain_test(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import _handle_step_expiry
        from schemas.game_state import BrainTestChallenge

        _state, session, _ = _make_session(
            GamePhase.ROUND,
            round_type=RoundType.BRAIN_TEST,
            current_step_index=5,  # last challenge step (challenge_4, after preroll)
        )
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
            BrainTestChallenge(
                challenge_type="t",
                question="Q3",
                options=["A", "B", "C", "D"],
                correct_index=0,
            ),
            BrainTestChallenge(
                challenge_type="t",
                question="Q4",
                options=["A", "B", "C", "D"],
                correct_index=0,
            ),
            BrainTestChallenge(
                challenge_type="t",
                question="Q5",
                options=["A", "B", "C", "D"],
                correct_index=0,
            ),
        ]
        game_id = _store_session(session)
        await _handle_step_expiry(game_id)

        # Should be on results step
        step = session.state.round_step_defs[session.state.current_step_index]
        assert step["name"] == "results"

        events = _get_broadcast_events(game_id)
        event_types = [e.event_type for e in events]
        assert "round_results" in event_types

        results_event = next(e for e in events if e.event_type == "round_results")
        assert results_event.scores is not None
        # h1 got both right = 200
        assert results_event.scores["h1"] == 200


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

        await initialize_and_start_game("init_test", 6)

        assert session.state.phase == GamePhase.ROUND
        assert len(session.state.players) == 8  # 2 human + 6 AI
        assert session.state.round_number == 1
        assert len(session.state.round_types) >= 1  # dynamically grown
        assert session.state.total_rounds == 5
        assert len(session.state.round_step_defs) > 0  # step defs populated

        mock_ai["assign_personalities"].assert_called_once()


# ---------------------------------------------------------------------------
# _start_next_round
# ---------------------------------------------------------------------------


class TestStartNextRound:
    async def test_advances_round_number(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import _start_next_round

        _state, session, _ = _make_session(
            GamePhase.ROUND,
            round_type=RoundType.TASK,
            current_step_index=3,  # results (after preroll + compose + vote)
        )
        session.state.round_types = [RoundType.TASK]
        session.state.round_number = 1
        game_id = _store_session(session)
        await _start_next_round(game_id, session)

        assert session.state.round_number == 2
        assert session.state.phase == GamePhase.ROUND
        assert session.state.current_step_index == 0
