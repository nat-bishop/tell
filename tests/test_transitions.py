"""Tests for backend/services/transitions.py — async phase transition sequences."""

from __future__ import annotations

from backend.api.deps import get_connection_manager, get_game_repository
from backend.services.game_repository import TellGameSession
from schemas.game_state import (
    ChainRound,
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

        state, session, _ = _make_session(
            GamePhase.PROMPT,
            round_type=RoundType.TASK,
            answers={"h1": "a", "h2": "b", "a1": "c", "a2": "d"},
        )
        game_id = _store_session(session)
        await do_prompt_complete(game_id, session)

        assert session.state.phase == GamePhase.REVIEW

    async def test_interrogation_round_goes_to_nominate(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_prompt_complete

        state, session, _ = _make_session(
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

        state, session, _ = _make_session(
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

        state, session, _ = _make_session(
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
        state, session, _ = _make_session(
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

        state, session, _ = _make_session(
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

        state, session, _ = _make_session(
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

        state, session, _ = _make_session(GamePhase.ELIMINATION, round_type=RoundType.TASK)
        # Kill all AI to trigger game over
        for p in session.state.players:
            if p.role.value == "ai":
                p.is_alive = False
        game_id = _store_session(session)
        await do_after_elimination(game_id, session)

        assert session.state.phase == GamePhase.GAME_OVER
        assert session.state.winner == "humans"

    async def test_next_round_task(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_after_elimination

        state, session, _ = _make_session(GamePhase.ELIMINATION, round_type=RoundType.TASK)
        # Set up round_types so next round is TASK
        session.state.round_types = [RoundType.TASK, RoundType.TASK, RoundType.TASK]
        session.state.round_number = 1
        game_id = _store_session(session)
        await do_after_elimination(game_id, session)

        assert session.state.phase == GamePhase.PROMPT
        assert session.state.current_round.round_type == RoundType.TASK

    async def test_next_round_interrogation(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_after_elimination

        state, session, _ = _make_session(GamePhase.ELIMINATION, round_type=RoundType.TASK)
        session.state.round_types = [RoundType.TASK, RoundType.INTERROGATION, RoundType.WORD_CHAIN]
        session.state.round_number = 1
        game_id = _store_session(session)
        await do_after_elimination(game_id, session)

        assert session.state.phase == GamePhase.PROMPT
        assert session.state.current_round.round_type == RoundType.INTERROGATION

    async def test_next_round_word_chain(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_after_elimination

        state, session, _ = _make_session(GamePhase.ELIMINATION, round_type=RoundType.TASK)
        session.state.round_types = [
            RoundType.TASK,
            RoundType.TASK,
            RoundType.WORD_CHAIN,
        ]
        session.state.round_number = 2
        game_id = _store_session(session)
        await do_after_elimination(game_id, session)

        assert session.state.phase == GamePhase.CHAIN
        assert session.state.current_round.round_type == RoundType.WORD_CHAIN


# ---------------------------------------------------------------------------
# do_chain_complete
# ---------------------------------------------------------------------------


class TestDoChainComplete:
    async def test_goes_to_review(self, fresh_deps, mock_ai, mock_llm):
        from backend.services.transitions import do_chain_complete

        state, session, _ = _make_session(GamePhase.CHAIN, round_type=RoundType.WORD_CHAIN)
        session.state.current_round.chain_rounds = [ChainRound(seed="ocean")]
        session.state.current_round.current_sub_round = 0
        game_id = _store_session(session)
        await do_chain_complete(game_id, session)

        assert session.state.phase == GamePhase.REVIEW


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

        assert session.state.phase == GamePhase.PROMPT
        assert len(session.state.players) == 4  # 2 human + 2 AI
        assert session.state.round_number == 1
        assert len(session.state.round_types) == session.state.max_rounds

        mock_ai["assign_personalities"].assert_called_once()
