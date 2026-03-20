"""Tests for schemas/ — Pydantic models, prompt selection, alias generation."""

from __future__ import annotations

import pytest

from schemas.aliases import generate_aliases
from schemas.api_models import (
    FinalRevealEvent,
    PlayerJoinedEvent,
    SubmitVoteRequest,
    SubmitWagerBetRequest,
    SubmitWagerGuessRequest,
)
from schemas.game_state import (
    GamePhase,
    Player,
    PlayerRole,
    RoundState,
    RoundType,
    TellGameState,
    WagerQuestion,
)
from schemas.prompts import DUEL_PROMPTS, select_duel_prompt, select_wager_questions

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
        assert rs.gallery_votes == {}
        assert rs.current_sub_round == 0


# ---------------------------------------------------------------------------
# Duel prompt selection
# ---------------------------------------------------------------------------


class TestDuelPromptSelection:
    def test_duel_prompts_exist(self):
        assert len(DUEL_PROMPTS) >= 35

    def test_no_repeats(self):
        used = []
        seen_indices = set()
        for _ in range(10):
            idx, _prompt = select_duel_prompt(used, None)
            assert idx not in seen_indices
            seen_indices.add(idx)
            used.append(idx)

    def test_avoids_same_category(self):
        _idx, prompt = select_duel_prompt([], "style_transfer")
        assert prompt.category.value != "style_transfer"


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

    def test_vote_request_validation(self):
        req = SubmitVoteRequest(player_id="p1", voted_for_player_id="p2")
        assert req.voted_for_player_id == "p2"

        with pytest.raises(ValueError):
            # Missing required field
            SubmitVoteRequest(player_id="p1")

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


# ---------------------------------------------------------------------------
# Wager models and question selection
# ---------------------------------------------------------------------------


class TestWagerModels:
    def test_wager_question_creation(self):
        q = WagerQuestion(
            question="How many bones?",
            correct_answer=206,
            range_min=0,
            range_max=500,
            unit="bones",
            category="science",
        )
        assert q.question == "How many bones?"
        assert q.guesses == {}
        assert q.bets == {}

    def test_wager_question_extra_forbid(self):
        with pytest.raises(ValueError):
            WagerQuestion(
                question="Q",
                correct_answer=1,
                range_min=0,
                range_max=10,
                unit="u",
                category="c",
                extra_field="bad",
            )

    def test_select_wager_questions_count(self):
        questions = select_wager_questions(3)
        assert len(questions) == 3

    def test_select_wager_questions_category_diversity(self):
        # With 3 questions and 6 categories, all 3 should be from different categories
        for _ in range(20):
            questions = select_wager_questions(3)
            categories = [q.category for q in questions]
            assert len(set(categories)) == 3

    def test_submit_wager_guess_request(self):
        req = SubmitWagerGuessRequest(player_id="p1", question_index=0, value=42)
        assert req.value == 42

    def test_submit_wager_bet_request(self):
        req = SubmitWagerBetRequest(player_id="p1", question_index=0, target_player_id="p2")
        assert req.target_player_id == "p2"

    def test_submit_wager_guess_request_extra_forbid(self):
        with pytest.raises(ValueError):
            SubmitWagerGuessRequest(player_id="p1", question_index=0, value=42, extra="bad")

    def test_submit_wager_bet_request_extra_forbid(self):
        with pytest.raises(ValueError):
            SubmitWagerBetRequest(
                player_id="p1", question_index=0, target_player_id="p2", extra="bad"
            )
