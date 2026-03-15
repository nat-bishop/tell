"""Core game state models."""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class GamePhase(str, enum.Enum):
    LOBBY = "lobby"
    PROMPT = "prompt"
    CHAT = "chat"
    VOTE = "vote"
    ELIMINATION = "elimination"
    GAME_OVER = "game_over"


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


class ChatMessage(BaseModel):
    player_id: str
    player_alias: str
    text: str
    is_answer: bool = False  # True for prompt answers, False for chat messages
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RoundState(BaseModel):
    round_number: int
    prompt_text: str
    prompt_category: str
    answers: dict[str, str] = Field(default_factory=dict)  # player_id -> answer text
    messages: list[ChatMessage] = Field(default_factory=list)
    votes: dict[str, str] = Field(default_factory=dict)  # voter_id -> target_id


class TellGameState(BaseModel):
    game_id: str
    phase: GamePhase = GamePhase.LOBBY
    players: list[Player] = Field(default_factory=list)
    current_round: RoundState | None = None
    round_number: int = 0
    max_rounds: int = 3  # calculated at game start: max(3, humanCount + 1)
    used_prompt_indices: list[int] = Field(default_factory=list)
    last_prompt_category: str | None = None
    winner: str | None = None  # "humans" or "ai" or None
    phase_deadline: datetime | None = None  # when current phase timer expires
