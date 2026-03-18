"""Tests for schemas/ — Pydantic models, prompt selection, alias generation."""

from __future__ import annotations

import pytest

from schemas.aliases import generate_aliases
from schemas.api_models import (
    FinalRevealEvent,
    PlayerJoinedEvent,
    SubmitMatchupVoteRequest,
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
            idx, _prompt = select_prompt(used, None, round_number=5)
            assert idx not in seen_indices
            seen_indices.add(idx)
            used.append(idx)

    def test_avoids_same_category(self):
        # With last_category set, should avoid that category
        _idx, prompt = select_prompt([], "emotional", round_number=5)
        assert prompt.category.value != "emotional"

    def test_min_round_filtering(self):
        # Round 1 should exclude social prompts (min_round=2)
        for _ in range(20):
            _idx, prompt = select_prompt([], None, round_number=1)
            assert prompt.min_round <= 1

    def test_fallback_when_constrained(self):
        # Use all non-social prompts, force round 1 (no social allowed)
        non_social = [i for i, p in enumerate(PROMPTS) if p.category != PromptCategory.SOCIAL]
        _idx, prompt = select_prompt(non_social, None, round_number=1)
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
        assert state.total_rounds == 5

    def test_player_defaults(self):
        player = Player(id="p1", alias="UNIT-1", role=PlayerRole.HUMAN)
        assert player.is_connected is True
        assert player.is_host is False
        assert player.score == 0

    def test_round_state_defaults(self):
        rs = RoundState(
            round_number=1, prompt_text="Test", prompt_category="logical", round_type=RoundType.TASK
        )
        assert rs.round_type == RoundType.TASK
        assert rs.answers == {}
        assert rs.matchups == []
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
            idx, _prompt = select_task_prompt(used, None)
            assert idx not in seen_indices
            seen_indices.add(idx)
            used.append(idx)

    def test_avoids_same_category(self):
        _idx, prompt = select_task_prompt([], "haiku")
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

    def test_matchup_vote_request_validation(self):
        req = SubmitMatchupVoteRequest(player_id="p1", matchup_index=0, choice=1)
        assert req.choice == 1

        with pytest.raises(ValueError):
            # Missing required field
            SubmitMatchupVoteRequest(matchup_index=0, choice=1)

    def test_final_reveal_event(self):
        event = FinalRevealEvent(
            seq=1,
            players=[
                {"id": "h1", "alias": "UNIT-01", "role": "human", "score": 3},
                {"id": "a1", "alias": "CORE-07", "role": "ai", "score": 1},
            ],
            winner_ids=["h1"],
            narrator_text="A dramatic conclusion.",
        )
        assert event.event_type == "final_reveal"
        assert len(event.players) == 2
        assert event.winner_ids == ["h1"]
        assert event.narrator_text == "A dramatic conclusion."

    def test_final_reveal_event_no_narrator(self):
        event = FinalRevealEvent(
            seq=1,
            players=[],
            winner_ids=[],
        )
        assert event.narrator_text is None
