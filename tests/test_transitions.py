"""Tests for backend/services/transitions.py — async phase transition sequences."""

from __future__ import annotations

from backend.api.deps import get_connection_manager, get_game_repository
from backend.services.game_repository import TellGameSession
from schemas.game_state import (
    GamePhase,
    QuestionEntry,
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
    async def test_task_round_goes_to_review(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_prompt_complete

        _state, session, _ = _make_session(
            GamePhase.PROMPT,
            round_type=RoundType.TASK,
            answers={"h1": "a", "h2": "b", "a1": "c", "a2": "d"},
        )
        game_id = _store_session(session)
        await do_prompt_complete(game_id, session)

        assert session.state.phase == GamePhase.REVIEW

    async def test_interrogation_round_goes_to_nominate(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_prompt_complete

        _state, session, _ = _make_session(
            GamePhase.PROMPT,
            round_type=RoundType.INTERROGATION,
            answers={"h1": "a", "h2": "b", "a1": "c", "a2": "d"},
        )
        game_id = _store_session(session)
        await do_prompt_complete(game_id, session)

        assert session.state.phase == GamePhase.NOMINATE


# ---------------------------------------------------------------------------
# do_nominate_complete
# ---------------------------------------------------------------------------


class TestDoNominateComplete:
    async def test_resolves_and_goes_to_question(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_nominate_complete

        _state, session, _ = _make_session(
            GamePhase.NOMINATE,
            round_type=RoundType.INTERROGATION,
            nominations={"h1": "a1", "h2": "a1", "a1": "h1", "a2": "a1"},
        )
        game_id = _store_session(session)
        await do_nominate_complete(game_id, session)

        assert session.state.phase == GamePhase.QUESTION
        assert session.state.current_round.nominated_id == "a1"

        events = _get_broadcast_events(game_id)
        event_types = [e.event_type for e in events]
        assert "nominated" in event_types


# ---------------------------------------------------------------------------
# do_question_complete
# ---------------------------------------------------------------------------


class TestDoQuestionComplete:
    async def test_goes_to_respond_with_synthesis(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_question_complete

        _state, session, _ = _make_session(
            GamePhase.QUESTION,
            round_type=RoundType.INTERROGATION,
            nominated_id="h2",
            questions=[
                QuestionEntry(
                    questioner_id="h1",
                    target_id="h2",
                    target_alias="BOT-42",
                    question="Why did you say that?",
                )
            ],
            answers={"h2": "Because I'm creative"},
        )
        game_id = _store_session(session)
        await do_question_complete(game_id, session)

        assert session.state.phase == GamePhase.RESPOND
        assert session.state.current_round.synthesis is not None

    async def test_synthesis_failure_fallback(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_question_complete

        mock_llm["synthesize_questions"].side_effect = Exception("LLM timeout")
        _state, session, _ = _make_session(
            GamePhase.QUESTION,
            round_type=RoundType.INTERROGATION,
            nominated_id="h2",
            questions=[
                QuestionEntry(
                    questioner_id="h1",
                    target_id="h2",
                    target_alias="BOT-42",
                    question="Why?",
                )
            ],
            answers={"h2": "answer"},
        )
        game_id = _store_session(session)
        await do_question_complete(game_id, session)

        assert session.state.phase == GamePhase.RESPOND
        # Fallback: numbered list
        assert "The group asks:" in session.state.current_round.synthesis


# ---------------------------------------------------------------------------
# do_respond_complete
# ---------------------------------------------------------------------------


class TestDoRespondComplete:
    async def test_goes_to_review(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_respond_complete

        _state, session, _ = _make_session(
            GamePhase.RESPOND,
            round_type=RoundType.INTERROGATION,
            nominated_id="h2",
            questions=[
                QuestionEntry(
                    questioner_id="h1",
                    target_id="h2",
                    target_alias="BOT-42",
                    question="Why?",
                    response="Because",
                )
            ],
        )
        game_id = _store_session(session)
        await do_respond_complete(game_id, session)

        assert session.state.phase == GamePhase.REVIEW


# ---------------------------------------------------------------------------
# do_vote_resolution
# ---------------------------------------------------------------------------


class TestDoVoteResolution:
    async def test_resolves_votes_to_elimination(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_vote_resolution

        _state, session, _ = _make_session(
            GamePhase.REVIEW,
            round_type=RoundType.TASK,
            votes={"h1": ["a1"], "h2": ["a1"], "a1": ["h1"], "a2": ["a1"]},
        )
        game_id = _store_session(session)
        await do_vote_resolution(game_id, session)

        assert session.state.phase == GamePhase.ELIMINATION

        events = _get_broadcast_events(game_id)
        event_types = [e.event_type for e in events]
        assert "vote_results" in event_types
        assert "elimination" in event_types


# ---------------------------------------------------------------------------
# do_after_elimination
# ---------------------------------------------------------------------------


class TestDoAfterElimination:
    async def test_game_over(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_after_elimination

        _state, session, _ = _make_session(GamePhase.ELIMINATION, round_type=RoundType.TASK)
        # Kill all AI to trigger game over
        for p in session.state.players:
            if p.role.value == "ai":
                p.is_alive = False
        game_id = _store_session(session)
        await do_after_elimination(game_id, session)

        assert session.state.phase == GamePhase.GAME_OVER
        assert session.state.winner == "survivors"
        assert len(session.state.winner_ids) > 0

    async def test_next_round_advances(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_after_elimination

        _state, session, _ = _make_session(GamePhase.ELIMINATION, round_type=RoundType.TASK)
        session.state.round_types = [RoundType.TASK]
        session.state.round_number = 1
        game_id = _store_session(session)
        await do_after_elimination(game_id, session)

        # Should advance to a new round (dynamically selected)
        assert session.state.phase in (
            GamePhase.PROMPT,
            GamePhase.BRAIN_TEST,
        )
        assert session.state.round_number == 2


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
            GamePhase.BRAIN_TEST,
        )
        assert len(session.state.players) == 4  # 2 human + 2 AI
        assert session.state.round_number == 1
        assert len(session.state.round_types) >= 1  # dynamically grown
        assert session.state.max_rounds == 10  # safety cap

        mock_ai["assign_personalities"].assert_called_once()


# ---------------------------------------------------------------------------
# do_brain_test_complete — scoring + ability award
# ---------------------------------------------------------------------------


class TestDoBrainTestComplete:
    async def test_scores_and_awards_ability(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_brain_test_complete

        _state, session, _ = _make_session(GamePhase.BRAIN_TEST, round_type=RoundType.BRAIN_TEST)
        from schemas.game_state import BrainTestChallenge

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
        await do_brain_test_complete(game_id, session)

        assert session.state.phase == GamePhase.BRAIN_TEST_RESULTS

        events = _get_broadcast_events(game_id)
        event_types = [e.event_type for e in events]
        assert "brain_test_results" in event_types

        # Check scores in the results event
        results_event = next(e for e in events if e.event_type == "brain_test_results")
        assert results_event.scores is not None
        # h1 got both right = 2, h2 got 1, a1 got 1, a2 got 1
        assert results_event.scores["h1"] == 2

        # Winner should be h1 (highest score)
        assert results_event.winner_id == "h1"

        # Ability should be awarded
        assert results_event.ability_awarded in ("partial_scan", "double_vote")
        assert session.state.active_ability is not None
        assert session.state.active_ability.holder_id == "h1"

    async def test_no_winner_when_all_wrong(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_brain_test_complete

        _state, session, _ = _make_session(GamePhase.BRAIN_TEST, round_type=RoundType.BRAIN_TEST)
        from schemas.game_state import BrainTestChallenge

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
        await do_brain_test_complete(game_id, session)

        assert session.state.phase == GamePhase.BRAIN_TEST_RESULTS

        events = _get_broadcast_events(game_id)
        results_event = next(e for e in events if e.event_type == "brain_test_results")
        assert results_event.winner_id is None
        assert results_event.ability_awarded is None
        assert session.state.active_ability is None


# ---------------------------------------------------------------------------
# _trigger_ability_on_review
# ---------------------------------------------------------------------------


class TestTriggerAbilityOnReview:
    async def test_partial_scan_fires(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import _trigger_ability_on_review
        from schemas.game_state import ActiveAbility

        _state, session, _ = _make_session(GamePhase.REVIEW, round_type=RoundType.TASK)
        session.state.active_ability = ActiveAbility(
            holder_id="h1",
            holder_alias="UNIT-01",
            ability_type="partial_scan",
        )
        game_id = _store_session(session)
        # Connect as the holder so send_to can deliver the event
        cm = get_connection_manager()
        holder_queue = cm.connect(game_id, "h1")
        await _trigger_ability_on_review(game_id, session)

        # Scan result is sent only to the holder, not broadcast
        events = _get_broadcast_events(game_id)
        assert "scan_result" not in [e.event_type for e in events]

        # Check the holder's queue for the targeted event
        scan_event = holder_queue.get_nowait()
        assert scan_event.event_type == "scan_result"
        assert len(scan_event.results) == 2
        # Each result has player_id, alias, claimed_role
        for r in scan_event.results:
            assert "player_id" in r
            assert "alias" in r
            assert "claimed_role" in r

    async def test_double_vote_does_nothing(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import _trigger_ability_on_review
        from schemas.game_state import ActiveAbility

        _state, session, _ = _make_session(GamePhase.REVIEW, round_type=RoundType.TASK)
        session.state.active_ability = ActiveAbility(
            holder_id="h1",
            holder_alias="UNIT-01",
            ability_type="double_vote",
        )
        game_id = _store_session(session)
        await _trigger_ability_on_review(game_id, session)

        events = _get_broadcast_events(game_id)
        event_types = [e.event_type for e in events]
        # double_vote should not trigger scan
        assert "scan_result" not in event_types

    async def test_no_ability_does_nothing(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import _trigger_ability_on_review

        _state, session, _ = _make_session(GamePhase.REVIEW, round_type=RoundType.TASK)
        session.state.active_ability = None
        game_id = _store_session(session)
        await _trigger_ability_on_review(game_id, session)

        events = _get_broadcast_events(game_id)
        event_types = [e.event_type for e in events]
        assert "scan_result" not in event_types


# ---------------------------------------------------------------------------
# _start_next_round — clears active_ability
# ---------------------------------------------------------------------------


class TestStartNextRound:
    async def test_clears_active_ability(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import _start_next_round
        from schemas.game_state import ActiveAbility

        _state, session, _ = _make_session(GamePhase.ELIMINATION, round_type=RoundType.TASK)
        session.state.active_ability = ActiveAbility(
            holder_id="h1",
            holder_alias="UNIT-01",
            ability_type="partial_scan",
        )
        session.state.round_types = [RoundType.TASK]
        session.state.round_number = 1
        game_id = _store_session(session)
        await _start_next_round(game_id, session)

        assert session.state.active_ability is None
