"""Tests for backend/services/game_logic.py — pure functions, no I/O."""

from __future__ import annotations

from types import SimpleNamespace

from backend.services.game_logic import (
    build_state_sync,
    check_game_over,
    fill_missing_answers,
    get_final_rankings,
    get_next_round_type,
    get_phase_duration,
    make_game_over_event,
    make_phase_changed_event,
    resolve_gallery_votes,
    sanitize_players_for_client,
    score_brain_test,
    select_next_round_type,
    transition_to_task_prompt,
    transition_to_vote,
    transition_to_vote_results,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import (
    BrainTestChallenge,
    GamePhase,
    PlayerRole,
    RoundType,
)
from tests.factories import make_game_state, make_player, make_standard_game

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
        assert len(result[1]) == 8


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

    def test_transition_to_task_prompt(self):
        state, _ = make_standard_game()
        state.round_number = 0
        result = transition_to_task_prompt(state, 45)
        assert result.phase == GamePhase.PROMPT
        assert result.round_number == 1
        assert result.current_round is not None
        assert result.current_round.round_type == RoundType.TASK
        assert result.current_round.prompt_text is not None
        assert len(result.used_prompt_indices) >= 1

    def test_transition_to_vote(self):
        state, _ = make_standard_game()
        result = transition_to_vote(state, 25)
        assert result.phase == GamePhase.VOTE
        assert result.phase_deadline is not None

    def test_transition_to_vote_results(self):
        state, _ = make_standard_game()
        result = transition_to_vote_results(state, 8)
        assert result.phase == GamePhase.VOTE_RESULTS
        assert result.phase_deadline is not None


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
        # All 8 players should have answers
        assert len(state.current_round.answers) == 8

    def test_fill_noop_without_round(self):
        state = make_game_state(current_round=None)
        fill_missing_answers(state)
        # No error raised

    def test_fill_missing_answers_noop_when_all_answered(self):
        state, _ = make_standard_game()
        all_answers = {p.id: f"answer-{p.id}" for p in state.players}
        state.current_round.answers = all_answers
        fill_missing_answers(state)
        assert len(state.current_round.answers) == 8


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

    def test_build_state_sync_shows_answers_in_vote(self):
        state, _ = make_standard_game(phase=GamePhase.VOTE)
        state.current_round.answers = {"h1": "my answer", "h2": "other"}

        sync = build_state_sync(state, "h1", seq=1)
        assert sync["answers"] == {"h1": "my answer", "h2": "other"}

    def test_build_state_sync_includes_my_vote_during_vote(self):
        state, _ = make_standard_game(phase=GamePhase.VOTE)
        state.current_round.gallery_votes = {"h1": "a1"}

        sync = build_state_sync(state, "h1", seq=1)
        assert sync["my_vote"] == "a1"

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
        state, _ = make_standard_game(phase=GamePhase.VOTE)
        event = make_phase_changed_event(state, seq=5)
        assert event.phase == "vote"
        assert event.round_number == 1
        assert event.seq == 5


# ---------------------------------------------------------------------------
# Duel prompt selection
# ---------------------------------------------------------------------------


class TestDuelPrompts:
    def test_duel_prompt_indices_tracked(self):
        state, _ = make_standard_game()
        state.round_number = 0
        result = transition_to_task_prompt(state, 45)
        assert len(result.used_prompt_indices) >= 1


# ---------------------------------------------------------------------------
# get_phase_duration
# ---------------------------------------------------------------------------


def _mock_settings(**overrides):
    defaults = {
        "prompt_duration": 45,
        "vote_duration": 25,
        "vote_results_duration": 8,
        "brain_test_duration": 85,
        "brain_test_results_duration": 15,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestGetPhaseDuration:
    def test_prompt(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.PROMPT) == 45

    def test_vote(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.VOTE) == 25

    def test_vote_results(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.VOTE_RESULTS) == 8

    def test_brain_test(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.BRAIN_TEST) == 85

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
# Gallery vote scoring
# ---------------------------------------------------------------------------


class TestGalleryVoteScoring:
    def _seq_fn(self):
        n = 0

        def fn():
            nonlocal n
            n += 1
            return n

        return fn

    def test_resolve_gallery_votes_basic(self):
        """3 votes for player a1 → a1 gets -3."""
        state, _ = make_standard_game(phase=GamePhase.VOTE)
        state.current_round.gallery_votes = {"h1": "a1", "h2": "a1", "a2": "a1"}

        state, results_event = resolve_gallery_votes(state, self._seq_fn())
        a1 = next(p for p in state.players if p.id == "a1")
        assert a1.score == -3
        assert results_event.vote_counts["a1"] == 3
        assert results_event.scores["a1"] == -3

    def test_resolve_gallery_votes_no_votes(self):
        """Nobody voted → no score changes."""
        state, _ = make_standard_game(phase=GamePhase.VOTE)
        state.current_round.gallery_votes = {}

        state, results_event = resolve_gallery_votes(state, self._seq_fn())
        for p in state.players:
            assert p.score == 0
        for _pid, count in results_event.vote_counts.items():
            assert count == 0

    def test_resolve_gallery_votes_spread(self):
        """Votes spread across players."""
        state, _ = make_standard_game(phase=GamePhase.VOTE)
        state.current_round.gallery_votes = {
            "h1": "a1",
            "h2": "a2",
            "a1": "h1",
            "a2": "h2",
        }

        state, _results_event = resolve_gallery_votes(state, self._seq_fn())
        # Each got 1 vote = -1
        for pid in ("h1", "h2", "a1", "a2"):
            p = next(pp for pp in state.players if pp.id == pid)
            assert p.score == -1

    def test_resolve_gallery_votes_all_on_one(self):
        """7 votes on one player → -7."""
        state, _ = make_standard_game(phase=GamePhase.VOTE)
        # All 7 other players vote for h1
        other_ids = [p.id for p in state.players if p.id != "h1"]
        state.current_round.gallery_votes = dict.fromkeys(other_ids, "h1")

        state, results_event = resolve_gallery_votes(state, self._seq_fn())
        h1 = next(p for p in state.players if p.id == "h1")
        assert h1.score == -7
        assert results_event.vote_counts["h1"] == 7
