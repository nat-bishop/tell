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
    determine_challenge_winner,
    fill_missing_answers,
    fill_missing_responses,
    generate_matchup_pairs,
    get_next_round_type,
    get_phase_duration,
    is_question_eligible,
    is_response_eligible,
    make_game_over_event,
    make_phase_changed_event,
    max_votes_for_player,
    resolve_matchup_votes,
    resolve_nominations,
    resolve_votes,
    sanitize_players_for_client,
    score_brain_test,
    select_next_round_type,
    transition_to_elimination,
    transition_to_nominate,
    transition_to_prompt,
    transition_to_question,
    transition_to_respond,
    transition_to_review,
    transition_to_task_matchup_prompt,
    validate_player_alive,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import (
    BrainTestChallenge,
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
        state, _vote_results, elimination = resolve_votes(state, self._seq_fn())

        assert elimination.eliminated_id == "a1"
        assert elimination.was_human is False
        assert elimination.tie is False

        player_a1 = next(p for p in state.players if p.id == "a1")
        assert player_a1.is_alive is False
        assert player_a1.eliminated_round == state.round_number

    def test_tie_eliminates_one_of_tied(self):
        state, _ = make_standard_game(phase=GamePhase.REVIEW)
        state.current_round.votes = {"h1": ["a1"], "h2": ["a2"]}
        state, _vote_results, elimination = resolve_votes(state, self._seq_fn())

        assert elimination.eliminated_id in ("a1", "a2")
        assert elimination.tie is True
        assert elimination.tie_message is not None

    def test_no_votes(self):
        state, _ = make_standard_game(phase=GamePhase.REVIEW)
        state.current_round.votes = {}
        state, _vote_results, elimination = resolve_votes(state, self._seq_fn())

        assert elimination.eliminated_id is None
        assert elimination.no_votes is True

    def test_multi_vote_flattening(self):
        state, _ = make_standard_game(phase=GamePhase.REVIEW)
        state.current_round.votes = {"h1": ["a1", "a2", "h2"], "h2": ["a1", "a2"]}
        state, vote_results, _elimination = resolve_votes(state, self._seq_fn())

        assert vote_results.vote_tallies["a1"] == 2
        assert vote_results.vote_tallies["a2"] == 2
        assert vote_results.vote_tallies["h2"] == 1

    def test_elimination_marks_player(self):
        state, _ = make_standard_game(phase=GamePhase.REVIEW)
        state.current_round.votes = {"h1": ["a1"], "h2": ["a1"]}
        state, _, _elimination = resolve_votes(state, self._seq_fn())

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
        "setup",
        [
            "all_humans_dead",
            "all_ai_dead",
            "two_left_with_human",
            "safety_cap",
            "game_continues",
        ],
    )
    def test_game_over_conditions(self, setup):
        if setup == "all_humans_dead":
            players = [
                make_player(role=PlayerRole.HUMAN, is_alive=False, player_id="h1"),
                make_player(role=PlayerRole.HUMAN, is_alive=False, player_id="h2"),
                make_player(role=PlayerRole.AI, player_id="a1"),
            ]
            state = make_game_state(players=players)
            result = check_game_over(state)
            assert result is not None
            assert result[0] == "ai"
            assert result[1] == []

        elif setup == "all_ai_dead":
            players = [
                make_player(role=PlayerRole.HUMAN, player_id="h1"),
                make_player(role=PlayerRole.AI, is_alive=False, player_id="a1"),
                make_player(role=PlayerRole.AI, is_alive=False, player_id="a2"),
            ]
            state = make_game_state(players=players)
            result = check_game_over(state)
            assert result is not None
            assert result[0] == "survivors"
            assert "h1" in result[1]

        elif setup == "two_left_with_human":
            players = [
                make_player(role=PlayerRole.HUMAN, player_id="h1"),
                make_player(role=PlayerRole.AI, player_id="a1"),
                make_player(role=PlayerRole.HUMAN, is_alive=False, player_id="h2"),
            ]
            state = make_game_state(players=players)
            result = check_game_over(state)
            assert result is not None
            assert result[0] == "survivors"
            assert set(result[1]) == {"h1", "a1"}

        elif setup == "safety_cap":
            state, _ = make_standard_game()
            state.round_number = 10
            state.max_rounds = 10
            result = check_game_over(state)
            assert result is not None
            assert result[0] == "survivors"

        else:  # game_continues
            state, _ = make_standard_game()
            assert check_game_over(state) is None


# ---------------------------------------------------------------------------
# Phase transitions
# ---------------------------------------------------------------------------


class TestPhaseTransitions:
    def test_transition_to_prompt(self):
        state, _ = make_standard_game()
        state.round_number = 0

        result = transition_to_prompt(state, 45)
        assert result.phase == GamePhase.PROMPT
        assert result.round_number == 1
        assert result.current_round is not None
        assert result.current_round.round_type == RoundType.INTERROGATION
        assert result.phase_deadline is not None

    def test_transition_to_prompt_always_interrogation(self):
        state, _ = make_standard_game()
        state.round_number = 1

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

    def test_select_next_round_type_no_repeat(self):
        for _ in range(50):
            rt = select_next_round_type(RoundType.TASK, 5)
            assert rt != RoundType.TASK

    def test_select_next_round_type_interrogation_needs_4(self):
        for _ in range(50):
            rt = select_next_round_type(None, 3)
            assert rt != RoundType.INTERROGATION

    def test_select_next_round_type_interrogation_eligible_with_4(self):
        results = {select_next_round_type(RoundType.TASK, 5) for _ in range(100)}
        assert RoundType.INTERROGATION in results

    def test_select_next_round_type_no_consecutive_non_eliminating(self):
        for _ in range(50):
            rt = select_next_round_type(RoundType.BRAIN_TEST, 5)
            assert rt != RoundType.BRAIN_TEST

    def test_select_next_round_type_three_types_only(self):
        """Only Task, Brain Test, and Interrogation exist."""
        results = set()
        for _ in range(200):
            rt = select_next_round_type(None, 5)
            results.add(rt)
        assert results == {RoundType.TASK, RoundType.BRAIN_TEST, RoundType.INTERROGATION}

    def test_transition_to_task_matchup_prompt(self):
        state, _ = make_standard_game()
        state.round_number = 0
        result = transition_to_task_matchup_prompt(state, 25)
        assert result.phase == GamePhase.PROMPT
        assert result.round_number == 1
        assert result.current_round is not None
        assert result.current_round.round_type == RoundType.TASK
        assert result.current_round.prompt_text is not None
        # Should have matchups
        assert len(result.current_round.matchups) > 0


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

        event = make_game_over_event(state, "survivors", ["h1", "h2"], seq_fn)
        assert event.winner == "survivors"
        assert event.winner_ids == ["h1", "h2"]
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
# Task prompt selection
# ---------------------------------------------------------------------------


class TestTaskPrompts:
    def test_task_prompt_separate_from_interrogation(self):
        """Task and interrogation prompts use separate used_indices."""
        state, _ = make_standard_game()
        state.round_number = 0

        # Use task matchup prompt (creates per-pair prompts)
        result = transition_to_task_matchup_prompt(state, 25)
        # Each matchup pair gets a prompt, so task indices should be populated
        assert len(result.used_task_prompt_indices) >= 1
        assert len(result.used_prompt_indices) == 0  # regular prompts untouched

        # Use interrogation prompt
        result2 = transition_to_prompt(result, 45)
        assert len(result2.used_task_prompt_indices) >= 1  # task indices untouched
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
        "brain_test_duration": 85,
        "brain_test_results_duration": 15,
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

    def test_brain_test(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.BRAIN_TEST) == 85

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
    def test_respects_last_round_type(self):
        state, _ = make_standard_game()
        state.round_types = [RoundType.TASK]
        for _ in range(50):
            rt = get_next_round_type(state)
            assert rt != RoundType.TASK

    def test_respects_alive_count(self):
        state, _ = make_standard_game()
        # Kill players to leave 3 alive — no interrogation
        state.players[3].is_alive = False
        state.round_types = [RoundType.BRAIN_TEST]
        for _ in range(50):
            rt = get_next_round_type(state)
            assert rt != RoundType.INTERROGATION

    def test_empty_round_types_any_eligible(self):
        state, _ = make_standard_game()
        state.round_types = []
        rt = get_next_round_type(state)
        assert rt in list(RoundType)


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


# ---------------------------------------------------------------------------
# Brain Test scoring
# ---------------------------------------------------------------------------


class TestScoreBrainTest:
    def test_correct_answers_score_one(self):
        ch = BrainTestChallenge(
            challenge_type="trick",
            question="What weighs more?",
            options=["Feathers", "Steel", "Same", "Depends"],
            correct_index=2,
            responses={"h1": 2, "h2": 0, "a1": 2},
        )
        totals = score_brain_test([ch])
        assert totals["h1"] == 1
        assert totals["h2"] == 0
        assert totals["a1"] == 1

    def test_multiple_challenges(self):
        ch1 = BrainTestChallenge(
            challenge_type="trick",
            question="Q1",
            options=["A", "B", "C", "D"],
            correct_index=1,
            responses={"h1": 1, "h2": 0},
        )
        ch2 = BrainTestChallenge(
            challenge_type="pattern",
            question="Q2",
            options=["X", "Y", "Z", "W"],
            correct_index=2,
            responses={"h1": 2, "h2": 2},
        )
        totals = score_brain_test([ch1, ch2])
        assert totals["h1"] == 2
        assert totals["h2"] == 1

    def test_empty_challenges(self):
        totals = score_brain_test([])
        assert totals == {}

    def test_no_responses(self):
        ch = BrainTestChallenge(
            challenge_type="trick",
            question="Q",
            options=["A", "B", "C", "D"],
            correct_index=0,
            responses={},
        )
        totals = score_brain_test([ch])
        assert totals == {}


class TestDetermineChallengeWinner:
    def test_clear_winner(self):
        result = determine_challenge_winner({"h1": 3, "h2": 1, "a1": 2})
        assert result is not None
        assert result[0] == "h1"

    def test_tie_returns_one(self):
        scores = {"h1": 2, "h2": 2}
        result = determine_challenge_winner(scores)
        assert result is not None
        assert result[0] in ("h1", "h2")

    def test_all_zeros_returns_none(self):
        result = determine_challenge_winner({"h1": 0, "h2": 0})
        assert result is None

    def test_empty_scores_returns_none(self):
        result = determine_challenge_winner({})
        assert result is None

    def test_single_player(self):
        result = determine_challenge_winner({"h1": 5})
        assert result is not None
        assert result[0] == "h1"


# ---------------------------------------------------------------------------
# Double-vote ability in resolve_votes
# ---------------------------------------------------------------------------


class TestResolveVotesDoubleVote:
    def _seq_fn(self):
        n = 0

        def fn():
            nonlocal n
            n += 1
            return n

        return fn

    def test_double_vote_doubles_holders_votes(self):
        from schemas.game_state import ActiveAbility

        state, _ = make_standard_game(phase=GamePhase.REVIEW)
        state.active_ability = ActiveAbility(
            holder_id="h1",
            holder_alias="UNIT-01",
            ability_type="double_vote",
        )
        # h1 votes for a1 (doubled to 2), h2 votes for a2 (1)
        state.current_round.votes = {"h1": ["a1"], "h2": ["a2"]}
        state, vote_results, elimination = resolve_votes(state, self._seq_fn())

        assert vote_results.vote_tallies["a1"] == 2
        assert vote_results.vote_tallies["a2"] == 1
        assert elimination.eliminated_id == "a1"

    def test_no_ability_normal_counting(self):
        state, _ = make_standard_game(phase=GamePhase.REVIEW)
        state.active_ability = None
        state.current_round.votes = {"h1": ["a1"], "h2": ["a2"]}
        state, vote_results, _elimination = resolve_votes(state, self._seq_fn())

        # Tied at 1 each — both should have tally 1
        assert vote_results.vote_tallies["a1"] == 1
        assert vote_results.vote_tallies["a2"] == 1

    def test_partial_scan_does_not_double_vote(self):
        from schemas.game_state import ActiveAbility

        state, _ = make_standard_game(phase=GamePhase.REVIEW)
        state.active_ability = ActiveAbility(
            holder_id="h1",
            holder_alias="UNIT-01",
            ability_type="partial_scan",
        )
        state.current_round.votes = {"h1": ["a1"], "h2": ["a2"]}
        state, vote_results, _elimination = resolve_votes(state, self._seq_fn())

        # partial_scan should NOT double — each target gets 1 vote
        assert vote_results.vote_tallies["a1"] == 1
        assert vote_results.vote_tallies["a2"] == 1


# ---------------------------------------------------------------------------
# Matchup pairing
# ---------------------------------------------------------------------------


class TestGenerateMatchupPairs:
    def test_even_count_no_bye(self):
        state, _ = make_standard_game()  # 4 players: h1, h2, a1, a2
        pairs, bye = generate_matchup_pairs(state)
        assert bye is None
        assert len(pairs) == 2
        all_ids = [pid for pair in pairs for pid in pair]
        assert len(set(all_ids)) == 4

    def test_odd_count_has_bye(self):
        state, _ = make_standard_game()
        # Kill one to leave 3 alive
        state.players[3].is_alive = False
        pairs, bye = generate_matchup_pairs(state)
        assert bye is not None
        assert len(pairs) == 1
        all_ids = [pid for pair in pairs for pid in pair]
        assert bye not in all_ids
        assert len(set(all_ids)) == 2

    def test_three_players(self):
        state = make_game_state(
            players=[
                make_player(player_id="p1"),
                make_player(player_id="p2"),
                make_player(player_id="p3"),
            ]
        )
        pairs, bye = generate_matchup_pairs(state)
        assert len(pairs) == 1
        assert bye is not None


# ---------------------------------------------------------------------------
# Matchup vote resolution
# ---------------------------------------------------------------------------


class TestResolveMatchupVotes:
    def _seq_fn(self):
        n = 0

        def fn():
            nonlocal n
            n += 1
            return n

        return fn

    def test_clear_loser_eliminated(self):
        from schemas.game_state import Matchup

        state, _ = make_standard_game(phase=GamePhase.MATCHUP)
        state.current_round.matchups = [
            Matchup(
                pair=["h1", "h2"],
                prompt_text="test",
                prompt_category="test",
                votes={"a1": 0, "a2": 0},  # both vote left (h1)
            ),
            Matchup(
                pair=["a1", "a2"],
                prompt_text="test2",
                prompt_category="test",
                votes={"h1": 1, "h2": 1},  # both vote right (a2)
            ),
        ]
        state, results_event, elimination = resolve_matchup_votes(state, self._seq_fn())

        # h1 won (2-0), h2 lost (0-2), a1 lost (0-2), a2 won (2-0)
        # h2 and a1 both lost by 2, random elimination
        assert elimination.eliminated_id in ("h2", "a1")

    def test_margins_computed_correctly(self):
        from schemas.game_state import Matchup

        state, _ = make_standard_game(phase=GamePhase.MATCHUP)
        state.current_round.matchups = [
            Matchup(
                pair=["h1", "h2"],
                prompt_text="test",
                prompt_category="test",
                votes={"a1": 0, "a2": 1},  # 1 left, 1 right — tie
            ),
            Matchup(
                pair=["a1", "a2"],
                prompt_text="test2",
                prompt_category="test",
                votes={"h1": 0, "h2": 0},  # both vote left (a1)
            ),
        ]
        state, results_event, elimination = resolve_matchup_votes(state, self._seq_fn())

        # h1/h2 matchup: tie (margin 0 for both)
        # a1/a2 matchup: a1 won 2-0, a2 lost 0-2
        assert results_event.margins["a2"] == 2  # lost by 2
        assert results_event.margins["a1"] == -2  # won by 2
        assert elimination.eliminated_id == "a2"

    def test_double_vote_in_matchup(self):
        from schemas.game_state import ActiveAbility, Matchup

        state, _ = make_standard_game(phase=GamePhase.MATCHUP)
        state.active_ability = ActiveAbility(
            holder_id="a1",
            holder_alias="BOT-01",
            ability_type="double_vote",
        )
        state.current_round.matchups = [
            Matchup(
                pair=["h1", "h2"],
                prompt_text="test",
                prompt_category="test",
                # a1 has double vote, votes left (h1) = 2 weight
                # a2 votes right (h2) = 1 weight
                votes={"a1": 0, "a2": 1},
            ),
        ]
        state, results_event, _elimination = resolve_matchup_votes(state, self._seq_fn())

        # h1 got 2 votes (a1 doubled), h2 got 1 vote
        assert results_event.margins["h1"] == -1  # won by 1
        assert results_event.margins["h2"] == 1  # lost by 1

    def test_bye_player_excluded(self):
        from schemas.game_state import Matchup

        state = make_game_state(
            phase=GamePhase.MATCHUP,
            players=[
                make_player(player_id="p1"),
                make_player(player_id="p2"),
                make_player(player_id="p3"),
            ],
            current_round=make_round_state(
                round_type=RoundType.TASK,
                matchups=[
                    Matchup(
                        pair=["p1", "p2"],
                        prompt_text="test",
                        prompt_category="test",
                        votes={"p3": 0},  # bye player votes left (p1)
                    ),
                ],
                bye_player_id="p3",
            ),
        )
        state, results_event, elimination = resolve_matchup_votes(state, self._seq_fn())

        # p1 won (1-0), p2 lost (0-1)
        assert elimination.eliminated_id == "p2"
        # Bye player (p3) is not in margins
        assert "p3" not in results_event.margins
