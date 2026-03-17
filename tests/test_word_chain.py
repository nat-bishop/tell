"""Tests for schemas/word_chain.py — seed word selection and fallback associations."""

from __future__ import annotations

from schemas.word_chain import (
    FALLBACK_ASSOCIATIONS,
    SEED_WORDS,
    get_fallback_association,
    select_seed_word,
)


class TestSelectSeedWord:
    def test_returns_seed_word(self):
        word = select_seed_word()
        assert word in SEED_WORDS

    def test_avoids_used_seeds(self):
        used = SEED_WORDS[:5]
        for _ in range(20):
            word = select_seed_word(used)
            assert word not in used

    def test_fallback_when_all_used(self):
        """When every word is used, falls back to the full list."""
        word = select_seed_word(list(SEED_WORDS))
        assert word in SEED_WORDS

    def test_none_used_seeds(self):
        word = select_seed_word(None)
        assert word in SEED_WORDS

    def test_empty_used_seeds(self):
        word = select_seed_word([])
        assert word in SEED_WORDS


class TestGetFallbackAssociation:
    def test_known_seed(self):
        word = get_fallback_association("ocean")
        assert word in FALLBACK_ASSOCIATIONS["ocean"]

    def test_all_known_seeds(self):
        for seed, expected in FALLBACK_ASSOCIATIONS.items():
            result = get_fallback_association(seed)
            assert result in expected, f"Fallback for '{seed}' returned '{result}'"

    def test_unknown_seed(self):
        word = get_fallback_association("xylophone")
        assert word in ["thing", "place", "memory", "feeling", "sound"]
