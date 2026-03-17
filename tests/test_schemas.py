"""Tests for schemas/ — Pydantic models, prompt selection, alias generation."""

from __future__ import annotations

import pytest

from schemas.aliases import generate_aliases
from schemas.api_models import (
    CastVoteRequest,
    PlayerJoinedEvent,
)
from schemas.game_state import (
    GamePhase,
    Player,
    PlayerRole,
    RoundState,
    RoundType,
    TellGameState,
)
from schemas.prompts import PROMPTS, TASK_PROMPTS, PromptCategory, select_prompt, select_task_prompt

# ---------------------------------------------------------------------------
# Prompt selection
# ---------------------------------------------------------------------------


class TestSelectPrompt:
    def test_no_repeats(self):
        used = []
        seen_indices = set()
        for _ in range(10):
            idx, prompt = select_prompt(used, None, round_number=5)
            assert idx not in seen_indices
            seen_indices.add(idx)
            used.append(idx)

    def test_avoids_same_category(self):
        # With last_category set, should avoid that category
        idx, prompt = select_prompt([], "emotional", round_number=5)
        assert prompt.category.value != "emotional"

    def test_min_round_filtering(self):
        # Round 1 should exclude social prompts (min_round=2)
        for _ in range(20):
            idx, prompt = select_prompt([], None, round_number=1)
            assert prompt.min_round <= 1

    def test_fallback_when_constrained(self):
        # Use all non-social prompts, force round 1 (no social allowed)
        non_social = [i for i, p in enumerate(PROMPTS) if p.category != PromptCategory.SOCIAL]
        idx, prompt = select_prompt(non_social, None, round_number=1)
        # Should still return something (fallback: any unused)
        assert prompt is not None


# ---------------------------------------------------------------------------
# Alias generation
# ---------------------------------------------------------------------------


class TestGenerateAliases:
    def test_correct_count(self):
        aliases = generate_aliases(5)
        assert len(aliases) == 5

    def test_no_duplicates(self):
        aliases = generate_aliases(10)
        assert len(aliases) == len(set(aliases))

    def test_respects_exclude(self):
        exclude = {"UNIT-1", "BOT-2", "CORE-3"}
        aliases = generate_aliases(5, exclude=exclude)
        for alias in aliases:
            assert alias not in exclude


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModelDefaults:
    def test_game_state_defaults(self):
        state = TellGameState(game_id="test")
        assert state.phase == GamePhase.LOBBY
        assert state.players == []
        assert state.current_round is None
        assert state.round_number == 0
        assert state.max_rounds == 3

    def test_player_defaults(self):
        player = Player(id="p1", alias="UNIT-1", role=PlayerRole.HUMAN)
        assert player.is_alive is True
        assert player.is_connected is True
        assert player.is_host is False
        assert player.eliminated_round is None

    def test_round_state_defaults(self):
        rs = RoundState(
            round_number=1, prompt_text="Test", prompt_category="logical", round_type=RoundType.TASK
        )
        assert rs.round_type == RoundType.TASK
        assert rs.answers == {}
        assert rs.questions == []
        assert rs.votes == {}
        assert rs.nominated_id is None
        assert rs.chain_rounds == []
        assert rs.current_sub_round == 0


# ---------------------------------------------------------------------------
# Task prompt selection
# ---------------------------------------------------------------------------


class TestTaskPromptSelection:
    def test_task_prompts_exist(self):
        assert len(TASK_PROMPTS) >= 40

    def test_no_repeats(self):
        used = []
        seen_indices = set()
        for _ in range(10):
            idx, prompt = select_task_prompt(used, None)
            assert idx not in seen_indices
            seen_indices.add(idx)
            used.append(idx)

    def test_avoids_same_category(self):
        idx, prompt = select_task_prompt([], "haiku")
        assert prompt.category.value != "haiku"


# ---------------------------------------------------------------------------
# Event serialization
# ---------------------------------------------------------------------------


class TestEventSerialization:
    def test_event_roundtrip(self):
        event = PlayerJoinedEvent(seq=1, player_id="p1", alias="UNIT-1", player_count=3)
        data = event.model_dump()
        restored = PlayerJoinedEvent.model_validate(data)
        assert restored.player_id == "p1"
        assert restored.event_type == "player_joined"
        assert restored.seq == 1

    def test_request_validation(self):
        req = CastVoteRequest(player_id="p1", target_ids=["t1", "t2"])
        assert req.target_ids == ["t1", "t2"]

        with pytest.raises(Exception):
            # Missing required field
            CastVoteRequest(target_ids=["t1"])
