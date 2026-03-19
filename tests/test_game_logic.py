"""Tests for backend/services/game_logic.py — pure functions, no I/O."""

from __future__ import annotations

from types import SimpleNamespace

from backend.services.game_logic import (
    build_state_sync,
    check_game_over,
    fill_missing_answers,
    generate_matchup_pairs,
    get_final_rankings,
    get_next_round_type,
    get_phase_duration,
    make_game_over_event,
    make_phase_changed_event,
    resolve_matchup_votes,
    sanitize_players_for_client,
    score_brain_test,
    select_next_round_type,
    transition_to_task_matchup_prompt,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import (
    BrainTestChallenge,
    GamePhase,
    PlayerRole,
    RoundType,
)
from tests.factories import make_game_state, make_player, make_round_state, make_standard_game

# ---------------------------------------------------------------------------
# Player queries
# ---------------------------------------------------------------------------


class TestPlayerQueries:
    def test_get_player_by_id_found_and_missing(self):
        from backend.services.game_logic import get_player_by_id

        p = make_player(player_id="abc")
        state = make_game_state(players=[p])
        assert get_player_by_id(state, "abc") is p
        assert get_player_by_id(state, "nonexistent") is None


# ---------------------------------------------------------------------------
# Game over conditions (score-based)
# ---------------------------------------------------------------------------


class TestCheckGameOver:
    def test_game_over_when_rounds_complete(self):
        state, _ = make_standard_game()
        state.round_number = 5
        state.total_rounds = 5
        # Give h1 the highest score
        state.players[0].score = 3
        state.players[1].score = 1
        result = check_game_over(state)
        assert result is not None
        assert result[0] == "winners"
        assert "h1" in result[1]

    def test_game_continues_before_total_rounds(self):
        state, _ = make_standard_game()
        state.round_number = 3
        state.total_rounds = 5
        assert check_game_over(state) is None

    def test_game_over_tie(self):
        state, _ = make_standard_game()
        state.round_number = 5
        state.total_rounds = 5
        state.players[0].score = 2
        state.players[1].score = 2
        state.players[2].score = 1
        state.players[3].score = 0
        result = check_game_over(state)
        assert result is not None
        assert result[0] == "winners"
        assert set(result[1]) == {"h1", "h2"}

    def test_game_over_all_zero_scores(self):
        state, _ = make_standard_game()
        state.round_number = 5
        state.total_rounds = 5
        result = check_game_over(state)
        assert result is not None
        assert result[0] == "winners"
        # All tied at 0 — everyone is a winner
        assert len(result[1]) == 4


# ---------------------------------------------------------------------------
# Final rankings
# ---------------------------------------------------------------------------


class TestGetFinalRankings:
    def test_sorted_by_score_desc(self):
        state, _ = make_standard_game()
        state.players[0].score = 1
        state.players[1].score = 3
        state.players[2].score = 0
        state.players[3].score = 2
        rankings = get_final_rankings(state)
        assert rankings[0] == ("h2", 3)
        assert rankings[1] == ("a2", 2)
        assert rankings[2] == ("h1", 1)
        assert rankings[3] == ("a1", 0)

    def test_empty_players(self):
        state = make_game_state(players=[])
        assert get_final_rankings(state) == []

    def test_all_same_score(self):
        state, _ = make_standard_game()
        for p in state.players:
            p.score = 5
        rankings = get_final_rankings(state)
        assert all(score == 5 for _, score in rankings)


# ---------------------------------------------------------------------------
# Phase transitions
# ---------------------------------------------------------------------------


class TestPhaseTransitions:
    def test_select_next_round_type_no_repeat(self):
        for _ in range(50):
            rt = select_next_round_type(RoundType.TASK)
            assert rt != RoundType.TASK

    def test_select_next_round_type_no_repeat_brain_test(self):
        for _ in range(50):
            rt = select_next_round_type(RoundType.BRAIN_TEST)
            assert rt != RoundType.BRAIN_TEST

    def test_select_next_round_type_two_types_only(self):
        """Only Task and Brain Test exist."""
        results = set()
        for _ in range(200):
            rt = select_next_round_type(None)
            results.add(rt)
        assert results == {RoundType.TASK, RoundType.BRAIN_TEST}

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

    def test_fill_noop_without_round(self):
        state = make_game_state(current_round=None)
        fill_missing_answers(state)
        # No error raised

    def test_fill_missing_answers_noop_when_all_answered(self):
        state, _ = make_standard_game()
        state.current_round.answers = {"h1": "a", "h2": "b", "a1": "c", "a2": "d"}
        fill_missing_answers(state)
        assert state.current_round.answers == {"h1": "a", "h2": "b", "a1": "c", "a2": "d"}


# ---------------------------------------------------------------------------
# State sanitization
# ---------------------------------------------------------------------------


class TestStateSanitization:
    def test_sanitize_players_hides_roles_during_game(self):
        p1 = make_player(role=PlayerRole.HUMAN, player_id="h1")
        p2 = make_player(role=PlayerRole.AI, player_id="a1")
        state = make_game_state(players=[p1, p2])

        result = sanitize_players_for_client(state)
        assert "role" not in result[0]
        assert "role" not in result[1]

    def test_sanitize_players_reveals_roles_at_game_over(self):
        p1 = make_player(role=PlayerRole.HUMAN, player_id="h1")
        p2 = make_player(role=PlayerRole.AI, player_id="a1")
        state = make_game_state(players=[p1, p2], phase=GamePhase.GAME_OVER)

        result = sanitize_players_for_client(state)
        assert result[0]["role"] == "human"
        assert result[1]["role"] == "ai"

    def test_sanitize_players_includes_score(self):
        p1 = make_player(role=PlayerRole.HUMAN, player_id="h1", score=3)
        state = make_game_state(players=[p1])
        result = sanitize_players_for_client(state)
        assert result[0]["score"] == 3

    def test_build_state_sync_hides_answers_during_prompt(self):
        state, _ = make_standard_game(phase=GamePhase.PROMPT)
        state.current_round.answers = {"h1": "my answer", "h2": "other"}

        sync = build_state_sync(state, "h1", seq=1)
        assert sync["answers"] == {}  # all answers hidden during PROMPT
        assert sync["my_answer"] == "my answer"  # own answer visible

    def test_build_state_sync_shows_answers_in_active(self):
        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
        state.current_round.answers = {"h1": "my answer", "h2": "other"}

        sync = build_state_sync(state, "h1", seq=1)
        assert sync["answers"] == {"h1": "my answer", "h2": "other"}

    def test_build_state_sync_includes_scores(self):
        state, _ = make_standard_game(phase=GamePhase.PROMPT)
        state.players[0].score = 5
        sync = build_state_sync(state, "h1", seq=1)
        assert sync["scores"]["h1"] == 5

    def test_build_state_sync_includes_total_rounds(self):
        state, _ = make_standard_game(phase=GamePhase.PROMPT)
        sync = build_state_sync(state, "h1", seq=1)
        assert sync["total_rounds"] == 5

    def test_make_game_over_event_reveals_all(self):
        state, _ = make_standard_game()
        state.players[0].score = 3
        seq_n = 0

        def seq_fn():
            nonlocal seq_n
            seq_n += 1
            return seq_n

        event = make_game_over_event(state, "winners", ["h1"], seq_fn)
        assert event.winner == "winners"
        assert event.winner_ids == ["h1"]
        roles = {p["id"]: p["role"] for p in event.players}
        assert roles["h1"] == "human"
        assert roles["a1"] == "ai"
        assert event.scores["h1"] == 3

    def test_make_phase_changed_event(self):
        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
        event = make_phase_changed_event(state, seq=5)
        assert event.phase == "active"
        assert event.round_number == 1
        assert event.seq == 5


# ---------------------------------------------------------------------------
# Task prompt selection
# ---------------------------------------------------------------------------


class TestTaskPrompts:
    def test_task_prompt_indices_tracked(self):
        """Task prompts track used indices separately."""
        state, _ = make_standard_game()
        state.round_number = 0

        result = transition_to_task_matchup_prompt(state, 25)
        assert len(result.used_task_prompt_indices) >= 1


# ---------------------------------------------------------------------------
# get_phase_duration
# ---------------------------------------------------------------------------


def _mock_settings(**overrides):
    defaults = {
        "prompt_duration": 45,
        "task_prompt_duration": 25,
        "prompt_reading_duration": 10,
        "brain_test_duration": 85,
        "brain_test_results_duration": 15,
        "matchup_duration": 30,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestGetPhaseDuration:
    def test_prompt_default(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.PROMPT) == 55  # 45 + 10

    def test_prompt_task(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.PROMPT, RoundType.TASK) == 35  # 25 + 10

    def test_active_brain_test(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.ACTIVE, RoundType.BRAIN_TEST) == 85

    def test_active_task(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.ACTIVE, RoundType.TASK) == 30

    def test_results_brain_test(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.RESULTS, RoundType.BRAIN_TEST) == 15

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

    def test_empty_round_types_any_eligible(self):
        state, _ = make_standard_game()
        state.round_types = []
        rt = get_next_round_type(state)
        assert rt in list(RoundType)


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


# ---------------------------------------------------------------------------
# Scoring calculation
# ---------------------------------------------------------------------------


class TestScoringCalculation:
    def test_matchup_winner_gets_point(self):
        from schemas.game_state import Matchup

        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
        state.current_round.matchups = [
            Matchup(
                pair=["h1", "h2"],
                prompt_text="test",
                prompt_category="test",
                votes={"a1": 0, "a2": 0},  # both vote left (h1)
            ),
        ]

        state, _matchup_results, scores = resolve_matchup_votes(state)
        # h1 won (2-0), should get +1 score
        h1 = next(p for p in state.players if p.id == "h1")
        h2 = next(p for p in state.players if p.id == "h2")
        assert h1.score == 1
        assert h2.score == 0
        assert scores["h1"] == 1

    def test_tie_matchup_no_points(self):
        from schemas.game_state import Matchup

        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
        state.current_round.matchups = [
            Matchup(
                pair=["h1", "h2"],
                prompt_text="test",
                prompt_category="test",
                votes={"a1": 0, "a2": 1},  # tie
            ),
        ]

        state, _results, _scores = resolve_matchup_votes(state)
        h1 = next(p for p in state.players if p.id == "h1")
        h2 = next(p for p in state.players if p.id == "h2")
        assert h1.score == 0
        assert h2.score == 0

    def test_cumulative_scoring(self):
        from schemas.game_state import Matchup

        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
        state.players[0].score = 2  # h1 already had 2 points

        state.current_round.matchups = [
            Matchup(
                pair=["h1", "h2"],
                prompt_text="test",
                prompt_category="test",
                votes={"a1": 0, "a2": 0},  # h1 wins
            ),
        ]

        state, _results, scores = resolve_matchup_votes(state)
        h1 = next(p for p in state.players if p.id == "h1")
        assert h1.score == 3  # 2 + 1
        assert scores["h1"] == 3


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
        state = make_game_state(
            players=[
                make_player(player_id="p1"),
                make_player(player_id="p2"),
                make_player(player_id="p3"),
            ]
        )
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
    def test_winner_gets_score(self):
        from schemas.game_state import Matchup

        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
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
        state, _results, scores = resolve_matchup_votes(state)

        # h1 won matchup 1, a2 won matchup 2
        assert scores["h1"] == 1
        assert scores["h2"] == 0
        assert scores["a1"] == 0
        assert scores["a2"] == 1

    def test_results_include_matchup_details(self):
        from schemas.game_state import Matchup

        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
        state.current_round.matchups = [
            Matchup(
                pair=["h1", "h2"],
                prompt_text="test prompt",
                prompt_category="test",
                votes={"a1": 0, "a2": 1},  # 1 left, 1 right — tie
            ),
        ]
        state, matchup_results, _scores = resolve_matchup_votes(state)

        assert len(matchup_results) == 1
        mr = matchup_results[0]
        assert mr["left_player_id"] == "h1"
        assert mr["right_player_id"] == "h2"
        assert mr["left_votes"] == 1
        assert mr["right_votes"] == 1

    def test_bye_player_excluded_from_matchup(self):
        from schemas.game_state import Matchup

        state = make_game_state(
            phase=GamePhase.ACTIVE,
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
        state, _results, scores = resolve_matchup_votes(state)

        # p1 won (1-0)
        assert scores["p1"] == 1
        assert scores["p2"] == 0
