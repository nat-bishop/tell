"""Tests for backend/services/game_logic.py — pure functions, no I/O."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.services.game_logic import (
    assign_question_targets,
    build_state_sync,
    check_game_over,
    count_expected_questions,
    count_responses,
    fill_missing_answers,
    fill_missing_responses,
    get_next_round_type,
    get_phase_duration,
    is_question_eligible,
    is_response_eligible,
    make_game_over_event,
    make_phase_changed_event,
    max_votes_for_player,
    resolve_nominations,
    resolve_votes,
    sanitize_players_for_client,
    select_chain_next_word,
    select_round_types,
    transition_to_elimination,
    transition_to_nominate,
    transition_to_prompt,
    transition_to_question,
    transition_to_respond,
    transition_to_review,
    transition_to_task_prompt,
    transition_to_word_chain,
    validate_player_alive,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import (
    GamePhase,
    PlayerRole,
    QuestionEntry,
    RoundType,
)
from tests.factories import make_game_state, make_player, make_round_state, make_standard_game

# ---------------------------------------------------------------------------
# Player queries
# ---------------------------------------------------------------------------


class TestPlayerQueries:
    def test_get_alive_filters_correctly(self):
        from backend.services.game_logic import get_alive_ai, get_alive_humans, get_alive_players

        alive_h = make_player(role=PlayerRole.HUMAN, player_id="h1")
        alive_a = make_player(role=PlayerRole.AI, player_id="a1")
        dead_h = make_player(role=PlayerRole.HUMAN, player_id="h2", is_alive=False)
        state = make_game_state(players=[alive_h, alive_a, dead_h])

        assert get_alive_players(state) == [alive_h, alive_a]
        assert get_alive_humans(state) == [alive_h]
        assert get_alive_ai(state) == [alive_a]

    def test_get_player_by_id_found_and_missing(self):
        from backend.services.game_logic import get_player_by_id

        p = make_player(player_id="abc")
        state = make_game_state(players=[p])
        assert get_player_by_id(state, "abc") is p
        assert get_player_by_id(state, "nonexistent") is None

    def test_validate_player_alive(self):
        alive = make_player(player_id="a")
        dead = make_player(player_id="d", is_alive=False)
        state = make_game_state(players=[alive, dead])

        assert validate_player_alive(state, "a") is alive
        assert validate_player_alive(state, "d") == "Player has been eliminated"
        assert validate_player_alive(state, "x") == "Player not found"


# ---------------------------------------------------------------------------
# Round-robin assignment
# ---------------------------------------------------------------------------


class TestAssignQuestionTargets:
    def test_four_player_chain(self):
        state, players = make_standard_game()
        assignments = assign_question_targets(state)
        ids = [p.id for p in players]
        for i, pid in enumerate(ids):
            assert assignments[pid] == ids[(i + 1) % len(ids)]

    def test_two_player(self):
        p1 = make_player(player_id="p1")
        p2 = make_player(player_id="p2")
        state = make_game_state(players=[p1, p2])
        assignments = assign_question_targets(state)
        assert assignments["p1"] == "p2"
        assert assignments["p2"] == "p1"

    def test_skips_dead_players(self):
        alive1 = make_player(player_id="a1")
        alive2 = make_player(player_id="a2")
        dead = make_player(player_id="d1", is_alive=False)
        state = make_game_state(players=[alive1, dead, alive2])
        assignments = assign_question_targets(state)
        assert "d1" not in assignments
        assert assignments["a1"] == "a2"
        assert assignments["a2"] == "a1"


# ---------------------------------------------------------------------------
# Vote resolution
# ---------------------------------------------------------------------------


class TestResolveVotes:
    def _seq_fn(self):
        n = 0

        def fn():
            nonlocal n
            n += 1
            return n

        return fn

    def test_clear_winner(self):
        state, _ = make_standard_game(phase=GamePhase.REVIEW)
        state.current_round.votes = {"h1": ["a1"], "h2": ["a1"], "a1": ["h1"], "a2": ["a1"]}
        state, vote_results, elimination = resolve_votes(state, self._seq_fn())

        assert elimination.eliminated_id == "a1"
        assert elimination.was_human is False
        assert elimination.tie is False

        player_a1 = next(p for p in state.players if p.id == "a1")
        assert player_a1.is_alive is False
        assert player_a1.eliminated_round == state.round_number

    def test_tie_eliminates_one_of_tied(self):
        state, _ = make_standard_game(phase=GamePhase.REVIEW)
        state.current_round.votes = {"h1": ["a1"], "h2": ["a2"]}
        state, vote_results, elimination = resolve_votes(state, self._seq_fn())

        assert elimination.eliminated_id in ("a1", "a2")
        assert elimination.tie is True
        assert elimination.tie_message is not None

    def test_no_votes(self):
        state, _ = make_standard_game(phase=GamePhase.REVIEW)
        state.current_round.votes = {}
        state, vote_results, elimination = resolve_votes(state, self._seq_fn())

        assert elimination.eliminated_id is None
        assert elimination.no_votes is True

    def test_multi_vote_flattening(self):
        state, _ = make_standard_game(phase=GamePhase.REVIEW)
        state.current_round.votes = {"h1": ["a1", "a2", "h2"], "h2": ["a1", "a2"]}
        state, vote_results, elimination = resolve_votes(state, self._seq_fn())

        assert vote_results.vote_tallies["a1"] == 2
        assert vote_results.vote_tallies["a2"] == 2
        assert vote_results.vote_tallies["h2"] == 1

    def test_elimination_marks_player(self):
        state, _ = make_standard_game(phase=GamePhase.REVIEW)
        state.current_round.votes = {"h1": ["a1"], "h2": ["a1"]}
        state, _, elimination = resolve_votes(state, self._seq_fn())

        player = next(p for p in state.players if p.id == "a1")
        assert player.is_alive is False
        assert player.eliminated_round == 1

    @pytest.mark.parametrize(
        "alive_count,expected",
        [(2, 1), (3, 2), (4, 3), (5, 3), (10, 3)],
    )
    def test_max_votes_for_player(self, alive_count, expected):
        assert max_votes_for_player(alive_count) == expected

    def test_max_votes_edge_case_one_alive(self):
        assert max_votes_for_player(1) == 1


# ---------------------------------------------------------------------------
# Nomination resolution
# ---------------------------------------------------------------------------


class TestResolveNominations:
    def test_clear_winner(self):
        state, _ = make_standard_game()
        state.current_round.nominations = {"h1": "a1", "h2": "a1", "a1": "h1", "a2": "a1"}
        result = resolve_nominations(state)
        assert result == "a1"

    def test_tie_picks_one_of_tied(self):
        state, _ = make_standard_game()
        state.current_round.nominations = {"h1": "a1", "h2": "h1"}
        result = resolve_nominations(state)
        assert result in ("a1", "h1")

    def test_empty_nominations_picks_random_alive(self):
        state, _ = make_standard_game()
        state.current_round.nominations = {}
        alive_ids = {p.id for p in state.players if p.is_alive}
        result = resolve_nominations(state)
        assert result in alive_ids


# ---------------------------------------------------------------------------
# Game over conditions
# ---------------------------------------------------------------------------


class TestCheckGameOver:
    @pytest.mark.parametrize(
        "setup,expected",
        [
            ("all_humans_dead", "ai"),
            ("all_ai_dead", "humans"),
            ("two_left_with_human", "humans"),
            ("max_rounds", "humans"),
            ("game_continues", None),
        ],
    )
    def test_game_over_conditions(self, setup, expected):
        if setup == "all_humans_dead":
            players = [
                make_player(role=PlayerRole.HUMAN, is_alive=False, player_id="h1"),
                make_player(role=PlayerRole.HUMAN, is_alive=False, player_id="h2"),
                make_player(role=PlayerRole.AI, player_id="a1"),
            ]
            state = make_game_state(players=players)

        elif setup == "all_ai_dead":
            players = [
                make_player(role=PlayerRole.HUMAN, player_id="h1"),
                make_player(role=PlayerRole.AI, is_alive=False, player_id="a1"),
                make_player(role=PlayerRole.AI, is_alive=False, player_id="a2"),
            ]
            state = make_game_state(players=players)

        elif setup == "two_left_with_human":
            players = [
                make_player(role=PlayerRole.HUMAN, player_id="h1"),
                make_player(role=PlayerRole.AI, player_id="a1"),
                make_player(role=PlayerRole.HUMAN, is_alive=False, player_id="h2"),
            ]
            state = make_game_state(players=players)

        elif setup == "max_rounds":
            state, _ = make_standard_game()
            state.round_number = 3
            state.max_rounds = 3

        else:  # game_continues
            state, _ = make_standard_game()

        assert check_game_over(state) == expected


# ---------------------------------------------------------------------------
# Phase transitions
# ---------------------------------------------------------------------------


class TestPhaseTransitions:
    def test_transition_to_prompt(self):
        state, _ = make_standard_game()
        state.round_number = 0
        state.round_types = [RoundType.INTERROGATION, RoundType.TASK]

        result = transition_to_prompt(state, 45)
        assert result.phase == GamePhase.PROMPT
        assert result.round_number == 1
        assert result.current_round is not None
        assert result.current_round.round_type == RoundType.INTERROGATION
        assert result.phase_deadline is not None

    def test_transition_to_prompt_respects_round_types(self):
        state, _ = make_standard_game()
        state.round_number = 1
        state.round_types = [RoundType.TASK, RoundType.INTERROGATION, RoundType.WORD_CHAIN]

        result = transition_to_prompt(state, 45)
        assert result.round_number == 2
        assert result.current_round.round_type == RoundType.INTERROGATION

    @pytest.mark.parametrize(
        "transition_fn,expected_phase",
        [
            (transition_to_question, GamePhase.QUESTION),
            (transition_to_respond, GamePhase.RESPOND),
            (transition_to_review, GamePhase.REVIEW),
            (transition_to_elimination, GamePhase.ELIMINATION),
        ],
    )
    def test_simple_transitions(self, transition_fn, expected_phase):
        state, _ = make_standard_game()
        result = transition_fn(state, 30)
        assert result.phase == expected_phase
        assert result.phase_deadline is not None

    def test_select_round_types(self):
        types = select_round_types(6)
        assert types == [
            RoundType.TASK,
            RoundType.INTERROGATION,
            RoundType.WORD_CHAIN,
            RoundType.TASK,
            RoundType.INTERROGATION,
            RoundType.WORD_CHAIN,
        ]

    def test_transition_to_task_prompt(self):
        state, _ = make_standard_game()
        state.round_number = 0
        result = transition_to_task_prompt(state, 25)
        assert result.phase == GamePhase.PROMPT
        assert result.round_number == 1
        assert result.current_round is not None
        assert result.current_round.round_type == RoundType.TASK
        assert result.current_round.prompt_text is not None


# ---------------------------------------------------------------------------
# Fill functions
# ---------------------------------------------------------------------------


class TestFillFunctions:
    def test_fill_missing_answers(self):
        state, _ = make_standard_game()
        state.current_round.answers = {"h1": "my answer"}

        fill_missing_answers(state)

        assert state.current_round.answers["h1"] == "my answer"
        assert state.current_round.answers["h2"] == NO_RESPONSE
        assert state.current_round.answers["a1"] == NO_RESPONSE
        assert state.current_round.answers["a2"] == NO_RESPONSE

    def test_fill_missing_responses(self):
        q1 = QuestionEntry(
            questioner_id="h1", target_id="h2", target_alias="BOT-42", question="Why?"
        )
        q2 = QuestionEntry(
            questioner_id="h2",
            target_id="h1",
            target_alias="UNIT-01",
            question="How?",
            response="Because",
        )
        state, _ = make_standard_game()
        state.current_round.questions = [q1, q2]

        fill_missing_responses(state)

        assert q1.response == NO_RESPONSE
        assert q2.response == "Because"

    def test_fill_noop_without_round(self):
        state = make_game_state(current_round=None)
        fill_missing_answers(state)
        fill_missing_responses(state)
        # No error raised


# ---------------------------------------------------------------------------
# State sanitization
# ---------------------------------------------------------------------------


class TestStateSanitization:
    def test_sanitize_players_hides_alive_roles(self):
        alive = make_player(role=PlayerRole.HUMAN, player_id="h1")
        dead = make_player(role=PlayerRole.AI, player_id="a1", is_alive=False)
        state = make_game_state(players=[alive, dead])

        result = sanitize_players_for_client(state)
        assert "role" not in result[0]  # alive — role hidden
        assert result[1]["role"] == "ai"  # dead — role revealed

    def test_build_state_sync_hides_answers_during_prompt(self):
        state, _ = make_standard_game(phase=GamePhase.PROMPT)
        state.current_round.answers = {"h1": "my answer", "h2": "other"}

        sync = build_state_sync(state, "h1", seq=1)
        assert sync["answers"] == {}  # all answers hidden during PROMPT
        assert sync["my_answer"] == "my answer"  # own answer visible

    def test_build_state_sync_shows_answers_after_prompt(self):
        state, _ = make_standard_game(phase=GamePhase.QUESTION)
        state.current_round.answers = {"h1": "my answer", "h2": "other"}

        sync = build_state_sync(state, "h1", seq=1)
        assert sync["answers"] == {"h1": "my answer", "h2": "other"}

    def test_build_state_sync_includes_questioner_id(self):
        q = QuestionEntry(
            questioner_id="h1",
            target_id="h2",
            target_alias="BOT-42",
            question="Why?",
        )
        state, _ = make_standard_game(phase=GamePhase.QUESTION)
        state.current_round.questions = [q]

        sync = build_state_sync(state, "h2", seq=1)
        assert sync["questions"][0]["questioner_id"] == "h1"

    def test_make_game_over_event_reveals_all(self):
        state, _ = make_standard_game()
        seq_n = 0

        def seq_fn():
            nonlocal seq_n
            seq_n += 1
            return seq_n

        event = make_game_over_event(state, "humans", seq_fn)
        assert event.winner == "humans"
        roles = {p["id"]: p["role"] for p in event.players}
        assert roles["h1"] == "human"
        assert roles["a1"] == "ai"

    def test_make_phase_changed_event(self):
        state, _ = make_standard_game(phase=GamePhase.QUESTION)
        event = make_phase_changed_event(state, seq=5)
        assert event.phase == "question"
        assert event.round_number == 1
        assert event.seq == 5


# ---------------------------------------------------------------------------
# Question/response eligibility
# ---------------------------------------------------------------------------


class TestQuestionResponseEligibility:
    def test_is_question_eligible_interrogation(self):
        rs = make_round_state(round_type=RoundType.INTERROGATION, nominated_id="nominee")
        assert is_question_eligible(rs, "other") is True
        assert is_question_eligible(rs, "nominee") is False

    def test_is_response_eligible_interrogation(self):
        rs = make_round_state(round_type=RoundType.INTERROGATION, nominated_id="nominee")
        assert is_response_eligible(rs, "nominee") is True
        assert is_response_eligible(rs, "other") is False

    def test_count_expected_questions_interrogation(self):
        state, _ = make_standard_game()
        state.current_round.round_type = RoundType.INTERROGATION
        state.current_round.nominated_id = "h1"
        assert count_expected_questions(state) == 3  # all alive minus nominee

    def test_count_responses_interrogation(self):
        q1 = QuestionEntry(
            questioner_id="h1",
            target_id="nominee",
            target_alias="N",
            question="Q",
            response="R",
        )
        rs = make_round_state(
            round_type=RoundType.INTERROGATION,
            nominated_id="nominee",
            questions=[q1],
        )
        responded, total = count_responses(rs)
        assert responded == 1
        assert total == 1

    def test_count_responses_interrogation_no_response(self):
        q1 = QuestionEntry(questioner_id="h1", target_id="nominee", target_alias="N", question="Q")
        rs = make_round_state(
            round_type=RoundType.INTERROGATION,
            nominated_id="nominee",
            questions=[q1],
        )
        responded, total = count_responses(rs)
        assert responded == 0
        assert total == 1


# ---------------------------------------------------------------------------
# Word Chain seed selection
# ---------------------------------------------------------------------------


class TestSelectChainNextWord:
    def test_prefers_unique_word(self):
        responses = {"p1": "wave", "p2": "wave", "p3": "tide"}
        # "tide" is unique (only p3), should be preferred
        for _ in range(20):
            word, pid = select_chain_next_word(responses)
            assert word == "tide"
            assert pid == "p3"

    def test_all_same_word(self):
        responses = {"p1": "wave", "p2": "wave", "p3": "wave"}
        word, pid = select_chain_next_word(responses)
        assert word == "wave"
        assert pid in ("p1", "p2", "p3")

    def test_multiple_unique_words(self):
        responses = {"p1": "tide", "p2": "shore", "p3": "surf"}
        # All unique — should pick randomly among them
        word, pid = select_chain_next_word(responses)
        assert word in ("tide", "shore", "surf")

    def test_empty_responses(self):
        word, pid = select_chain_next_word({})
        assert word == ""
        assert pid is None

    def test_case_insensitive(self):
        responses = {"p1": "Wave", "p2": "WAVE", "p3": "tide"}
        word, pid = select_chain_next_word(responses)
        # "wave" appears twice (case-insensitive), "tide" is unique
        assert word == "tide"


# ---------------------------------------------------------------------------
# Task prompt selection
# ---------------------------------------------------------------------------


class TestTaskPrompts:
    def test_task_prompt_separate_from_interrogation(self):
        """Task and interrogation prompts use separate used_indices."""
        state, _ = make_standard_game()
        state.round_number = 0

        # Use task prompt
        result = transition_to_task_prompt(state, 25)
        assert len(result.used_task_prompt_indices) == 1
        assert len(result.used_prompt_indices) == 0  # regular prompts untouched

        # Use interrogation prompt
        result2 = transition_to_prompt(result, 45)
        assert len(result2.used_task_prompt_indices) == 1  # task indices untouched
        assert len(result2.used_prompt_indices) == 1


# ---------------------------------------------------------------------------
# get_phase_duration
# ---------------------------------------------------------------------------


def _mock_settings(**overrides):
    defaults = {
        "prompt_duration": 45,
        "task_prompt_duration": 25,
        "prompt_reading_duration": 10,
        "question_duration": 25,
        "respond_duration": 30,
        "review_duration": 40,
        "nominate_duration": 15,
        "elimination_duration": 8,
        "chain_duration": 64,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestGetPhaseDuration:
    def test_prompt_interrogation(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.PROMPT) == 55  # 45 + 10

    def test_prompt_task(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.PROMPT, RoundType.TASK) == 35  # 25 + 10

    def test_chain(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.CHAIN) == 64

    @pytest.mark.parametrize(
        "phase,attr",
        [
            (GamePhase.QUESTION, "question_duration"),
            (GamePhase.RESPOND, "respond_duration"),
            (GamePhase.REVIEW, "review_duration"),
            (GamePhase.NOMINATE, "nominate_duration"),
            (GamePhase.ELIMINATION, "elimination_duration"),
        ],
    )
    def test_simple_phases(self, phase, attr):
        s = _mock_settings()
        assert get_phase_duration(s, phase) == getattr(s, attr)

    def test_unknown_phase(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.LOBBY) is None


# ---------------------------------------------------------------------------
# get_next_round_type
# ---------------------------------------------------------------------------


class TestGetNextRoundType:
    def test_within_bounds(self):
        state, _ = make_standard_game()
        state.round_number = 0
        state.round_types = [RoundType.TASK, RoundType.INTERROGATION, RoundType.WORD_CHAIN]
        assert get_next_round_type(state) == RoundType.TASK

    def test_second_round(self):
        state, _ = make_standard_game()
        state.round_number = 1
        state.round_types = [RoundType.TASK, RoundType.INTERROGATION, RoundType.WORD_CHAIN]
        assert get_next_round_type(state) == RoundType.INTERROGATION

    def test_out_of_bounds_falls_back(self):
        state, _ = make_standard_game()
        state.round_number = 10
        state.round_types = [RoundType.TASK]
        assert get_next_round_type(state) == RoundType.TASK

    def test_empty_round_types(self):
        state, _ = make_standard_game()
        state.round_number = 0
        state.round_types = []
        assert get_next_round_type(state) == RoundType.TASK


# ---------------------------------------------------------------------------
# transition_to_word_chain
# ---------------------------------------------------------------------------


class TestTransitionToWordChain:
    def test_basic(self):
        state, _ = make_standard_game()
        state.round_number = 0
        result = transition_to_word_chain(state, "ocean", 64)

        assert result.phase == GamePhase.CHAIN
        assert result.round_number == 1
        assert result.current_round is not None
        assert result.current_round.round_type == RoundType.WORD_CHAIN
        assert result.current_round.current_sub_round == 0
        assert len(result.current_round.chain_rounds) == 1
        assert result.current_round.chain_rounds[0].seed == "ocean"
        assert result.phase_deadline is not None

    def test_prompt_is_word_chain(self):
        state, _ = make_standard_game()
        state.round_number = 0
        result = transition_to_word_chain(state, "bridge", 64)
        assert result.current_round.prompt_text == "word chain"
        assert result.current_round.prompt_category == "word_chain"


# ---------------------------------------------------------------------------
# transition_to_nominate (explicit)
# ---------------------------------------------------------------------------


class TestTransitionToNominate:
    def test_sets_phase_and_deadline(self):
        state, _ = make_standard_game()
        result = transition_to_nominate(state, 15)
        assert result.phase == GamePhase.NOMINATE
        assert result.phase_deadline is not None


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------


class TestFillFunctionsEdgeCases:
    def test_fill_missing_answers_noop_when_all_answered(self):
        state, _ = make_standard_game()
        state.current_round.answers = {"h1": "a", "h2": "b", "a1": "c", "a2": "d"}
        fill_missing_answers(state)
        assert state.current_round.answers == {"h1": "a", "h2": "b", "a1": "c", "a2": "d"}


class TestBuildStateSyncEdgeCases:
    def test_review_phase_includes_my_votes(self):
        state, _ = make_standard_game(phase=GamePhase.REVIEW)
        state.current_round.votes = {"h1": ["a1", "a2"]}
        sync = build_state_sync(state, "h1", seq=1)
        assert sync["my_votes"] == ["a1", "a2"]

    def test_non_review_phase_empty_my_votes(self):
        state, _ = make_standard_game(phase=GamePhase.QUESTION)
        state.current_round.votes = {"h1": ["a1"]}
        sync = build_state_sync(state, "h1", seq=1)
        assert sync["my_votes"] == []

    def test_chain_phase_includes_chain_rounds(self):
        state, _ = make_standard_game(phase=GamePhase.CHAIN)
        from schemas.game_state import ChainRound

        state.current_round.chain_rounds = [ChainRound(seed="ocean")]
        state.current_round.current_sub_round = 0
        sync = build_state_sync(state, "h1", seq=1)
        assert len(sync["chain_rounds"]) == 1
        assert sync["chain_rounds"][0]["seed"] == "ocean"
        assert sync["current_sub_round"] == 0
