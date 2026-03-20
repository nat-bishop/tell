"""Tests for the Signal minigame handler."""

from __future__ import annotations

from types import SimpleNamespace

from backend.minigames.signal import NUM_TRANSMITTERS, SignalHandler
from schemas.game_state import GamePhase, RoundType
from tests.factories import make_standard_game


def _signal_settings():
    return SimpleNamespace(
        prompt_duration=45,
        signal_prompt_duration=20,
        signal_sub_round_duration=12,
        signal_safety_duration=120,
        signal_results_duration=15,
    )


class TestSignalSetupRound:
    def test_setup_round_basic(self):
        handler = SignalHandler()
        state, _ = make_standard_game()
        state.round_number = 0
        handler.setup_round(state, _signal_settings())

        assert state.round_number == 1
        rs = state.current_round
        assert rs is not None
        assert rs.round_type == RoundType.SIGNAL
        assert rs.prompt_category == "signal"
        assert rs.signal_constraint != ""
        assert len(rs.signal_phrases) == NUM_TRANSMITTERS
        assert len(rs.signal_player_order) == NUM_TRANSMITTERS

    def test_setup_round_only_transmitters_get_phrases(self):
        handler = SignalHandler()
        state, _ = make_standard_game()
        state.round_number = 0
        handler.setup_round(state, _signal_settings())

        rs = state.current_round
        for pid in rs.signal_player_order:
            assert pid in rs.signal_phrases
            assert rs.signal_phrases[pid] != ""
        # Non-transmitters should not have phrases
        all_ids = {p.id for p in state.players}
        non_tx = all_ids - set(rs.signal_player_order)
        for pid in non_tx:
            assert pid not in rs.signal_phrases

    def test_setup_round_tracks_used_indices(self):
        handler = SignalHandler()
        state, _ = make_standard_game()
        state.round_number = 0
        handler.setup_round(state, _signal_settings())

        assert len(state.used_signal_constraint_indices) == 1
        assert len(state.used_signal_phrase_indices) == NUM_TRANSMITTERS

    def test_setup_round_no_repeat_constraint(self):
        handler = SignalHandler()
        state, _ = make_standard_game()
        state.round_number = 0

        handler.setup_round(state, _signal_settings())
        first_constraint_idx = state.used_signal_constraint_indices[0]

        state.round_number = 0
        handler.setup_round(state, _signal_settings())
        second_constraint_idx = state.used_signal_constraint_indices[1]

        assert first_constraint_idx != second_constraint_idx

    def test_setup_round_avoids_repeat_transmitters(self):
        handler = SignalHandler()
        state, _ = make_standard_game()

        state.round_number = 0
        handler.setup_round(state, _signal_settings())
        first_tx = set(state.current_round.signal_player_order)

        state.round_number = 0
        handler.setup_round(state, _signal_settings())
        second_tx = set(state.current_round.signal_player_order)

        # No overlap (8 players, 3 per round)
        assert first_tx.isdisjoint(second_tx)

    def test_setup_round_resets_when_all_used(self):
        """When all players have been transmitters, tracking resets."""
        handler = SignalHandler()
        state, _ = make_standard_game()
        # Mark all players as used
        state.used_signal_transmitter_ids = [p.id for p in state.players]

        state.round_number = 0
        handler.setup_round(state, _signal_settings())
        # Should still work — resets tracking
        assert len(state.current_round.signal_player_order) == NUM_TRANSMITTERS


class TestSignalBuildResults:
    def _make_signal_state(self, guesses, judgments, phrases=None):
        """Build a game state with signal round data for testing build_results."""
        handler = SignalHandler()
        # Use ROUND phase with signal_guess step (step_index=1)
        state, _ = make_standard_game(
            phase=GamePhase.ROUND, round_type=RoundType.SIGNAL, current_step_index=1
        )

        rs = state.current_round
        rs.signal_constraint = "Only questions"
        rs.signal_player_order = ["h1", "h2", "a1"]
        rs.signal_phrases = phrases or {
            "h1": "a dog chasing a squirrel",
            "h2": "burning dinner",
            "a1": "stepping on a Lego",
        }
        rs.answers = {
            "h1": "What's running? Why the tree?",
            "h2": "Is that smoke?",
            "a1": "What hurts?",
        }
        rs.signal_guesses = guesses
        rs.signal_judgments = judgments

        return state, handler

    def test_guesser_scores_for_correct_guess(self):
        """Judge score 2 → guesser gets 100 pts."""
        guesses = {"h1": {"h2": "a dog chasing a squirrel"}}
        judgments = {"h1": {"h2": 2}}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas.get("h2", 0) == 100

    def test_guesser_scores_for_partial_guess(self):
        """Judge score 1 → guesser gets 50 pts."""
        guesses = {"h1": {"h2": "something close"}}
        judgments = {"h1": {"h2": 1}}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas.get("h2", 0) == 50

    def test_guesser_no_score_for_wrong_guess(self):
        """Judge score 0 → guesser gets 0 pts."""
        guesses = {"h1": {"h2": "something wrong"}}
        judgments = {"h1": {"h2": 0}}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas.get("h2", 0) == 0

    def test_transmitter_gets_avg_of_guesser_points(self):
        """Transmitter gets sum(guesser_pts) // num_guessers."""
        # 4 guessers: 2, 2, 1, 0 → pts: 100, 100, 50, 0 → avg: 250//4 = 62
        guesses = {"h1": {"h2": "g1", "a1": "g2", "a2": "g3", "a3": "g4"}}
        judgments = {"h1": {"h2": 2, "a1": 2, "a2": 1, "a3": 0}}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas.get("h1", 0) == 62  # 250 // 4

    def test_transmitter_zero_when_all_wrong(self):
        """All guessers score 0 → transmitter gets 0."""
        guesses = {"h1": {"h2": "g1", "a1": "g2"}}
        judgments = {"h1": {"h2": 0, "a1": 0}}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas.get("h1", 0) == 0

    def test_no_guesses_zero_scores(self):
        """No guesses submitted → all scores 0."""
        guesses = {}
        judgments = {}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas == {}

    def test_all_guesses_correct(self):
        """All guessers get 2 → each gets 100, transmitter gets 100."""
        guesses = {"h1": {"h2": "g1", "a1": "g2"}}
        judgments = {"h1": {"h2": 2, "a1": 2}}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas.get("h2", 0) == 100
        assert deltas.get("a1", 0) == 100
        assert deltas.get("h1", 0) == 100  # avg of [100, 100] = 100

    def test_results_payload_structure(self):
        guesses = {"h1": {"h2": "my guess"}}
        judgments = {"h1": {"h2": 2}}
        state, handler = self._make_signal_state(guesses, judgments)

        payload, _ = handler.build_results(state)
        assert "constraint" in payload
        assert "results" in payload
        result = payload["results"]["h1"]
        assert "original_phrase" in result
        assert "transformation" in result
        assert "guesses" in result
        assert "judgments" in result
        assert "transmitter_score" in result


class TestSignalPromptSelection:
    def test_select_signal_constraint_no_repeat(self):
        from schemas.prompts import select_signal_constraint

        used = []
        indices = set()
        for _ in range(5):
            idx, _c = select_signal_constraint(used)
            assert idx not in indices
            indices.add(idx)
            used.append(idx)

    def test_select_signal_phrases_unique(self):
        from schemas.prompts import select_signal_phrases

        results = select_signal_phrases(8, [])
        indices = [idx for idx, _ in results]
        assert len(set(indices)) == 8

    def test_select_signal_phrases_avoids_used(self):
        from schemas.prompts import select_signal_phrases

        used = [0, 1, 2, 3, 4]
        results = select_signal_phrases(3, used)
        indices = [idx for idx, _ in results]
        for idx in indices:
            assert idx not in used


class TestSignalStateSyncExtras:
    def test_compose_step_transmitter_returns_phrase(self):
        handler = SignalHandler()
        # Step 0 = compose for signal
        state, _ = make_standard_game(
            phase=GamePhase.ROUND, round_type=RoundType.SIGNAL, current_step_index=0
        )
        rs = state.current_round
        rs.signal_player_order = ["h1"]
        rs.signal_phrases = {"h1": "a dog chasing a squirrel"}

        extras = handler.build_state_sync_extras(state, "h1")
        assert extras.get("signal_phrase") == "a dog chasing a squirrel"
        assert extras.get("is_transmitter") is True

    def test_compose_step_non_transmitter(self):
        handler = SignalHandler()
        state, _ = make_standard_game(
            phase=GamePhase.ROUND, round_type=RoundType.SIGNAL, current_step_index=0
        )
        rs = state.current_round
        rs.signal_player_order = ["h1"]
        rs.signal_phrases = {"h1": "a dog chasing a squirrel"}

        extras = handler.build_state_sync_extras(state, "h2")
        assert "signal_phrase" not in extras
        assert extras.get("is_transmitter") is False

    def test_guess_step_returns_sub_round(self):
        handler = SignalHandler()
        # Step 1 = signal_guess_0
        state, _ = make_standard_game(
            phase=GamePhase.ROUND, round_type=RoundType.SIGNAL, current_step_index=1
        )
        rs = state.current_round
        rs.signal_player_order = ["h1", "h2"]
        rs.signal_constraint = "Only questions"
        rs.answers = {"h1": "What's running?"}
        rs.current_sub_round = 0

        extras = handler.build_state_sync_extras(state, "a1")
        assert extras["sub_round_index"] == 0
        assert extras["sub_round_payload"]["round_type"] == "signal"
        assert extras["sub_round_payload"]["featured_player_id"] == "h1"
        assert extras["sub_round_payload"]["total_transmitters"] == 2
