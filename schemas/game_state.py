"""Core game state models."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GamePhase(enum.StrEnum):
    LOBBY = "lobby"
    ROUND = "round"
    GAME_OVER = "game_over"


class RoundType(enum.StrEnum):
    TASK = "task"
    BRAIN_TEST = "brain_test"
    WAGER = "wager"
    SIGNAL = "signal"


class PlayerRole(enum.StrEnum):
    HUMAN = "human"
    AI = "ai"


class Player(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    alias: str
    role: PlayerRole
    is_host: bool = False
    is_connected: bool = True
    score: int = 0


class BrainTestChallenge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_type: str
    question: str
    options: list[str] = Field(default_factory=list)  # 4 choices
    correct_index: int = 0
    responses: dict[str, int] = Field(default_factory=dict)  # player_id -> selected index


class WagerQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    correct_answer: int
    range_min: int
    range_max: int
    unit: str
    category: str
    guesses: dict[str, int] = Field(default_factory=dict)  # player_id → value
    bets: dict[str, str] = Field(default_factory=dict)  # player_id → target_player_id


class RoundState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    round_number: int
    prompt_text: str
    prompt_category: str
    round_type: RoundType
    answers: dict[str, str] = Field(default_factory=dict)
    # Brain Test
    current_sub_round: int = 0
    brain_challenges: list[BrainTestChallenge] = Field(default_factory=list)
    # Gallery vote (Task rounds) — voter_id → voted_for_player_id
    gallery_votes: dict[str, str] = Field(default_factory=dict)
    # Wager
    wager_questions: list[WagerQuestion] = Field(default_factory=list)
    # Signal
    signal_player_order: list[str] = Field(default_factory=list)
    signal_phrases: dict[str, str] = Field(default_factory=dict)
    signal_guesses: dict[str, dict[str, str]] = Field(default_factory=dict)
    signal_judgments: dict[str, dict[str, int]] = Field(default_factory=dict)  # 0/1/2


class NarratorEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger: str
    text: str
    round_number: int = 0


class TellGameState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    game_id: str
    phase: GamePhase = GamePhase.LOBBY
    players: list[Player] = Field(default_factory=list)
    current_round: RoundState | None = None
    round_number: int = 0
    total_rounds: int = 5
    round_types: list[RoundType] = Field(default_factory=list)
    used_prompt_indices: list[int] = Field(default_factory=list)
    last_prompt_category: str | None = None
    used_signal_phrase_indices: list[int] = Field(default_factory=list)
    used_signal_constraint_indices: list[int] = Field(default_factory=list)
    used_signal_transmitter_ids: list[str] = Field(default_factory=list)
    winner: str | None = None
    winner_ids: list[str] = Field(default_factory=list)
    phase_deadline: datetime | None = None
    narrator_context: list[NarratorEntry] = Field(default_factory=list)
    # Step-based round state
    current_step_index: int = 0
    round_step_defs: list[dict] = Field(default_factory=list)
    # Debug: host-configured round sequence (empty = random)
    forced_round_sequence: list[RoundType] = Field(default_factory=list)
    # Debug: disable auto-expiring timers (host clicks "next" to advance)
    timers_disabled: bool = False
