"""Core game state models."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class GamePhase(str, enum.Enum):
    LOBBY = "lobby"
    PROMPT = "prompt"
    NOMINATE = "nominate"
    QUESTION = "question"
    RESPOND = "respond"
    REVIEW = "review"
    ELIMINATION = "elimination"
    GAME_OVER = "game_over"
    CHAIN = "chain"


class RoundType(str, enum.Enum):
    INTERROGATION = "interrogation"
    TASK = "task"
    WORD_CHAIN = "word_chain"


class PlayerRole(str, enum.Enum):
    HUMAN = "human"
    AI = "ai"


class Player(BaseModel):
    id: str
    alias: str
    role: PlayerRole
    is_host: bool = False
    is_alive: bool = True
    is_connected: bool = True
    eliminated_round: int | None = None


class QuestionEntry(BaseModel):
    questioner_id: str
    target_id: str
    target_alias: str
    question: str
    response: str | None = None


class ChainRound(BaseModel):
    seed: str
    responses: dict[str, str] = Field(default_factory=dict)  # player_id -> word
    chosen_word: str | None = None
    chosen_player_id: str | None = None


class RoundState(BaseModel):
    round_number: int
    prompt_text: str
    prompt_category: str
    round_type: RoundType
    answers: dict[str, str] = Field(default_factory=dict)
    questions: list[QuestionEntry] = Field(default_factory=list)
    assignments: dict[str, str] = Field(default_factory=dict)  # questioner_id -> target_id
    nominated_id: str | None = None
    nominations: dict[str, str] = Field(default_factory=dict)  # voter_id -> target_id
    synthesis: str | None = None
    verdict: str | None = None
    votes: dict[str, list[str]] = Field(default_factory=dict)  # voter_id -> [target_ids]
    # Reading period — when set, answers are not accepted until this time
    writing_begins_at: datetime | None = None
    # Word Chain
    current_sub_round: int = 0
    chain_rounds: list[ChainRound] = Field(default_factory=list)


class TellGameState(BaseModel):
    game_id: str
    phase: GamePhase = GamePhase.LOBBY
    players: list[Player] = Field(default_factory=list)
    current_round: RoundState | None = None
    round_number: int = 0
    max_rounds: int = 3
    round_types: list[RoundType] = Field(default_factory=list)
    used_prompt_indices: list[int] = Field(default_factory=list)
    used_task_prompt_indices: list[int] = Field(default_factory=list)
    last_prompt_category: str | None = None
    last_task_prompt_category: str | None = None
    winner: str | None = None
    phase_deadline: datetime | None = None
