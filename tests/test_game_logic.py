"""Tests for backend/services/game_logic.py — pure functions, no I/O."""

from __future__ import annotations

from types import SimpleNamespace

from backend.minigames.brain_test import score_brain_test
from backend.minigames.wager import score_wager
from backend.services.game_logic import (
    build_state_sync,
    check_game_over,
    fill_missing_answers,
    get_final_rankings,
    get_next_round_type,
    get_phase_duration,
    make_game_over_event,
    make_phase_changed_event,
    sanitize_players_for_client,
    select_next_round_type,
    tally_gallery_votes,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import (
    BrainTestChallenge,
    GamePhase,
    PlayerRole,
    RoundType,
)
from tests.factories import make_game_state, make_player, make_standard_game, make_wager_question

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

    def test_select_next_round_type_all_types(self):
        """All registered round types can be selected."""
        results = set()
        for _ in range(300):
            rt = select_next_round_type(None)
            results.add(rt)
        assert results == {RoundType.TASK, RoundType.BRAIN_TEST, RoundType.WAGER, RoundType.SIGNAL}

    def test_select_next_round_type_no_repeat_signal(self):
        for _ in range(50):
            rt = select_next_round_type(RoundType.SIGNAL)
            assert rt != RoundType.SIGNAL

    def test_task_handler_setup_round(self):
        from backend.minigames.task import TaskHandler

        handler = TaskHandler()
        state, _ = make_standard_game()
        state.round_number = 0
        settings = SimpleNamespace(prompt_duration=45)
        handler.setup_round(state, settings)
        assert state.round_number == 1
        assert state.current_round is not None
        assert state.current_round.round_type == RoundType.TASK
        assert state.current_round.prompt_text is not None
        assert len(state.used_prompt_indices) >= 1


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

    def test_build_state_sync_shows_answers_in_active(self):
        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
        state.current_round.answers = {"h1": "my answer", "h2": "other"}

        sync = build_state_sync(state, "h1", seq=1)
        assert sync["answers"] == {"h1": "my answer", "h2": "other"}

    def test_build_state_sync_includes_my_vote_during_active_task(self):
        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
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
        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
        event = make_phase_changed_event(state, seq=5)
        assert event.phase == "active"
        assert event.round_number == 1
        assert event.seq == 5


# ---------------------------------------------------------------------------
# Duel prompt selection
# ---------------------------------------------------------------------------


class TestDuelPrompts:
    def test_duel_prompt_indices_tracked(self):
        from backend.minigames.task import TaskHandler

        handler = TaskHandler()
        state, _ = make_standard_game()
        state.round_number = 0
        settings = SimpleNamespace(prompt_duration=45)
        handler.setup_round(state, settings)
        assert len(state.used_prompt_indices) >= 1


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
        "wager_duration": 100,
        "wager_sub_round_duration": 15,
        "wager_questions": 3,
        "wager_results_duration": 15,
        "signal_prompt_duration": 20,
        "signal_safety_duration": 120,
        "signal_results_duration": 15,
        "signal_sub_round_duration": 12,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestGetPhaseDuration:
    def test_prompt(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.PROMPT) == 45

    def test_active_task(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.ACTIVE, RoundType.TASK) == 25

    def test_results_task(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.RESULTS, RoundType.TASK) == 8

    def test_active_brain_test(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.ACTIVE, RoundType.BRAIN_TEST) == 85

    def test_active_wager(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.ACTIVE, RoundType.WAGER) == 100

    def test_results_wager(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.RESULTS, RoundType.WAGER) == 15

    def test_prompt_signal(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.PROMPT, RoundType.SIGNAL) == 20

    def test_active_signal(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.ACTIVE, RoundType.SIGNAL) == 120

    def test_results_signal(self):
        s = _mock_settings()
        assert get_phase_duration(s, GamePhase.RESULTS, RoundType.SIGNAL) == 15

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
        assert totals["h1"] == 100
        assert totals["h2"] == 0
        assert totals["a1"] == 100

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
        assert totals["h1"] == 200
        assert totals["h2"] == 100

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
    def test_tally_gallery_votes_basic(self):
        """3 votes for player a1."""
        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
        state.current_round.gallery_votes = {"h1": "a1", "h2": "a1", "a2": "a1"}

        vote_counts = tally_gallery_votes(state)
        assert vote_counts["a1"] == 3

    def test_task_handler_build_results(self):
        """3 votes for player a1 → a1 gets -3."""
        from backend.minigames.task import TaskHandler

        handler = TaskHandler()
        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
        state.current_round.gallery_votes = {"h1": "a1", "h2": "a1", "a2": "a1"}

        payload, score_deltas = handler.build_results(state)
        assert payload["vote_counts"]["a1"] == 3
        assert score_deltas["a1"] == -300

    def test_tally_gallery_votes_no_votes(self):
        """Nobody voted → all counts 0."""
        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
        state.current_round.gallery_votes = {}

        vote_counts = tally_gallery_votes(state)
        for _pid, count in vote_counts.items():
            assert count == 0

    def test_task_handler_build_results_spread(self):
        """Votes spread across players."""
        from backend.minigames.task import TaskHandler

        handler = TaskHandler()
        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
        state.current_round.gallery_votes = {
            "h1": "a1",
            "h2": "a2",
            "a1": "h1",
            "a2": "h2",
        }

        _payload, score_deltas = handler.build_results(state)
        # Each got 1 vote = -100
        for pid in ("h1", "h2", "a1", "a2"):
            assert score_deltas[pid] == -100

    def test_task_handler_build_results_all_on_one(self):
        """7 votes on one player → -7."""
        from backend.minigames.task import TaskHandler

        handler = TaskHandler()
        state, _ = make_standard_game(phase=GamePhase.ACTIVE)
        other_ids = [p.id for p in state.players if p.id != "h1"]
        state.current_round.gallery_votes = dict.fromkeys(other_ids, "h1")

        payload, score_deltas = handler.build_results(state)
        assert payload["vote_counts"]["h1"] == 7
        assert score_deltas["h1"] == -700


# ---------------------------------------------------------------------------
# Wager scoring
# ---------------------------------------------------------------------------


class TestScoreWager:
    def test_closest_guess_scores_one(self):
        q = make_wager_question(correct_answer=50, guesses={"h1": 49, "h2": 30})
        totals = score_wager([q])
        assert totals["h1"] == 100
        assert totals.get("h2", 0) == 0

    def test_correct_bet_scores_one(self):
        q = make_wager_question(correct_answer=50, guesses={"h1": 49, "h2": 30}, bets={"h2": "h1"})
        totals = score_wager([q])
        assert totals["h1"] == 100  # closest guess
        assert totals["h2"] == 100  # correct bet

    def test_max_points_self_bet(self):
        q = make_wager_question(correct_answer=50, guesses={"h1": 50, "h2": 30}, bets={"h1": "h1"})
        totals = score_wager([q])
        assert totals["h1"] == 200  # closest guess + self-bet

    def test_tie_in_guesses(self):
        q = make_wager_question(correct_answer=50, guesses={"h1": 48, "h2": 52})
        totals = score_wager([q])
        assert totals["h1"] == 100
        assert totals["h2"] == 100

    def test_bet_on_tied_closest(self):
        q = make_wager_question(correct_answer=50, guesses={"h1": 48, "h2": 52}, bets={"a1": "h2"})
        totals = score_wager([q])
        assert totals["a1"] == 100  # bet on either tied guesser → +100

    def test_no_guesses_no_scores(self):
        q = make_wager_question(correct_answer=50, guesses={})
        totals = score_wager([q])
        assert totals == {}

    def test_no_bets_only_guess_points(self):
        q = make_wager_question(correct_answer=50, guesses={"h1": 50, "h2": 30})
        totals = score_wager([q])
        assert totals["h1"] == 100
        assert totals.get("h2", 0) == 0

    def test_multiple_questions_accumulate(self):
        q1 = make_wager_question(correct_answer=50, guesses={"h1": 50, "h2": 30}, bets={"h1": "h1"})
        q2 = make_wager_question(correct_answer=10, guesses={"h1": 20, "h2": 10}, bets={"h1": "h2"})
        q3 = make_wager_question(correct_answer=80, guesses={"h1": 80, "h2": 60}, bets={"h2": "h1"})
        totals = score_wager([q1, q2, q3])
        # q1: h1 closest (+100) + h1 self-bet (+100) = h1:200
        # q2: h2 closest (+100) + h1 bet on h2 (+100) = h2:100, h1:100
        # q3: h1 closest (+100) + h2 bet on h1 (+100) = h1:100, h2:100
        assert totals["h1"] == 400  # 200 + 100 + 100
        assert totals["h2"] == 200  # 100 + 100

    def test_bet_on_non_closest_scores_zero(self):
        q = make_wager_question(correct_answer=50, guesses={"h1": 50, "h2": 30}, bets={"a1": "h2"})
        totals = score_wager([q])
        assert totals.get("a1", 0) == 0

    def test_all_same_guess_all_closest(self):
        q = make_wager_question(correct_answer=50, guesses={"h1": 40, "h2": 40, "a1": 40})
        totals = score_wager([q])
        assert totals["h1"] == 100
        assert totals["h2"] == 100
        assert totals["a1"] == 100
