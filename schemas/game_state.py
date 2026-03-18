"""Core game state models."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GamePhase(enum.StrEnum):
    LOBBY = "lobby"
    PROMPT = "prompt"
    GAME_OVER = "game_over"
    BRAIN_TEST = "brain_test"
    BRAIN_TEST_RESULTS = "brain_test_results"
    MATCHUP = "matchup"


class RoundType(enum.StrEnum):
    TASK = "task"
    BRAIN_TEST = "brain_test"


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


class Matchup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair: list[str]  # [left_player_id, right_player_id]
    prompt_text: str
    prompt_category: str
    votes: dict[str, int] = Field(default_factory=dict)  # voter_id -> 0=left/1=right


class RoundState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    round_number: int
    prompt_text: str
    prompt_category: str
    round_type: RoundType
    answers: dict[str, str] = Field(default_factory=dict)
    # Reading period — when set, answers are not accepted until this time
    writing_begins_at: datetime | None = None
    # Brain Test
    current_sub_round: int = 0
    brain_challenges: list[BrainTestChallenge] = Field(default_factory=list)
    # Matchup (Task 1v1)
    matchups: list[Matchup] = Field(default_factory=list)
    current_matchup: int = 0
    bye_player_id: str | None = None


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
    used_task_prompt_indices: list[int] = Field(default_factory=list)
    last_task_prompt_category: str | None = None
    winner: str | None = None
    winner_ids: list[str] = Field(default_factory=list)
    phase_deadline: datetime | None = None
    narrator_context: list[NarratorEntry] = Field(default_factory=list)
