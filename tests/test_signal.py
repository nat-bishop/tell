"""Tests for the Signal minigame handler."""

from __future__ import annotations

from types import SimpleNamespace

from backend.minigames.signal import SignalHandler
from schemas.game_state import RoundType
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
        assert len(rs.signal_phrases) == len(state.players)
        assert len(rs.signal_player_order) == len(state.players)

    def test_setup_round_all_players_get_phrases(self):
        handler = SignalHandler()
        state, players = make_standard_game()
        state.round_number = 0
        handler.setup_round(state, _signal_settings())

        rs = state.current_round
        for p in players:
            assert p.id in rs.signal_phrases
            assert rs.signal_phrases[p.id] != ""

    def test_setup_round_tracks_used_indices(self):
        handler = SignalHandler()
        state, _ = make_standard_game()
        state.round_number = 0
        handler.setup_round(state, _signal_settings())

        assert len(state.used_signal_constraint_indices) == 1
        assert len(state.used_signal_phrase_indices) == len(state.players)

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


class TestSignalBuildResults:
    def _make_signal_state(self, guesses, judgments, phrases=None):
        """Build a game state with signal round data for testing build_results."""
        handler = SignalHandler()
        state, _ = make_standard_game(phase="active", round_type=RoundType.SIGNAL)

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
        guesses = {"h1": {"h2": "a dog chasing a squirrel"}}
        judgments = {"h1": {"h2": True}}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas.get("h2", 0) == 1  # guesser gets +1

    def test_guesser_no_score_for_wrong_guess(self):
        guesses = {"h1": {"h2": "something wrong"}}
        judgments = {"h1": {"h2": False}}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas.get("h2", 0) == 0

    def test_transmitter_bonus_half_correct(self):
        """Transmitter gets +1 when >= half of guessers are correct (2 of 4)."""
        guesses = {"h1": {"h2": "g1", "a1": "g2", "a2": "g3", "a3": "g4"}}
        judgments = {"h1": {"h2": True, "a1": True, "a2": False, "a3": False}}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas.get("h1", 0) == 1  # transmitter bonus

    def test_transmitter_no_bonus_less_than_half(self):
        """Transmitter gets no bonus when < half correct (1 of 4)."""
        guesses = {"h1": {"h2": "g1", "a1": "g2", "a2": "g3", "a3": "g4"}}
        judgments = {"h1": {"h2": True, "a1": False, "a2": False, "a3": False}}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas.get("h1", 0) == 0

    def test_transmitter_bonus_single_guesser_correct(self):
        """1 guesser, correct → transmitter gets bonus (1/1 >= 0.5)."""
        guesses = {"h1": {"h2": "a dog chasing a squirrel"}}
        judgments = {"h1": {"h2": True}}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas.get("h1", 0) == 1

    def test_no_guesses_zero_scores(self):
        """No guesses submitted → all scores 0."""
        guesses = {}
        judgments = {}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas == {}

    def test_all_guesses_correct(self):
        """All guessers correct → each gets +1, transmitter gets +1."""
        guesses = {"h1": {"h2": "g1", "a1": "g2"}}
        judgments = {"h1": {"h2": True, "a1": True}}
        state, handler = self._make_signal_state(guesses, judgments)

        _, deltas = handler.build_results(state)
        assert deltas.get("h2", 0) == 1
        assert deltas.get("a1", 0) == 1
        assert deltas.get("h1", 0) == 1  # transmitter bonus

    def test_results_payload_structure(self):
        guesses = {"h1": {"h2": "my guess"}}
        judgments = {"h1": {"h2": True}}
        state, handler = self._make_signal_state(guesses, judgments)

        payload, _ = handler.build_results(state)
        assert "constraint" in payload
        assert "results" in payload
        result = payload["results"]["h1"]
        assert "original_phrase" in result
        assert "transformation" in result
        assert "guesses" in result
        assert "judgments" in result
        assert "transmitter_bonus" in result


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
    def test_prompt_phase_returns_phrase(self):
        handler = SignalHandler()
        state, _ = make_standard_game(phase="prompt", round_type=RoundType.SIGNAL)
        rs = state.current_round
        rs.signal_phrases = {"h1": "a dog chasing a squirrel"}

        extras = handler.build_state_sync_extras(state, "h1")
        assert extras.get("signal_phrase") == "a dog chasing a squirrel"

    def test_active_phase_returns_sub_round(self):
        handler = SignalHandler()
        state, _ = make_standard_game(phase="active", round_type=RoundType.SIGNAL)
        rs = state.current_round
        rs.signal_player_order = ["h1", "h2"]
        rs.signal_constraint = "Only questions"
        rs.answers = {"h1": "What's running?"}
        rs.current_sub_round = 0

        extras = handler.build_state_sync_extras(state, "h2")
        assert extras["sub_round_index"] == 0
        assert extras["sub_round_payload"]["round_type"] == "signal"
        assert extras["sub_round_payload"]["featured_player_id"] == "h1"
