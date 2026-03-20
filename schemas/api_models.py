"""API models — SSE events and request/response types."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.game_state import TellGameState

# --- Base event ---


class GameEvent(BaseModel):
    """Base SSE event with monotonic sequence number.

    Subclasses narrow event_type to Literal types for TypeScript discriminated unions.
    Pyright flags these as reportIncompatibleVariableOverride — this is a known
    Pydantic v2 pattern that works correctly at runtime and for OpenAPI codegen.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str
    seq: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# --- SSE Events ---


class StateSyncEvent(GameEvent):
    event_type: Literal["state_sync"] = "state_sync"
    game_id: str
    phase: str
    players: list[dict]
    round_number: int
    prompt_text: str | None = None
    prompt_category: str | None = None
    answers: dict[str, str] = Field(default_factory=dict)
    round_type: str | None = None
    phase_deadline: str | None = None
    phase_duration: int | None = None
    winner: str | None = None
    winner_ids: list[str] = Field(default_factory=list)
    is_host: bool = False
    my_answer: str | None = None
    scores: dict[str, int] = Field(default_factory=dict)
    total_rounds: int = 5
    # Gallery vote state (reconnection)
    my_vote: str | None = None
    # Generic reconnection state
    sub_round_index: int | None = None
    sub_round_payload: dict | None = None
    round_results_payload: dict | None = None
    round_scores: dict[str, int] | None = None


class PlayerJoinedEvent(GameEvent):
    event_type: Literal["player_joined"] = "player_joined"
    player_id: str
    alias: str
    player_count: int


class PlayerDisconnectedEvent(GameEvent):
    event_type: Literal["player_disconnected"] = "player_disconnected"
    player_id: str


class PlayerReconnectedEvent(GameEvent):
    event_type: Literal["player_reconnected"] = "player_reconnected"
    player_id: str


class PhaseChangedEvent(GameEvent):
    event_type: Literal["phase_changed"] = "phase_changed"
    phase: str
    round_number: int
    prompt_text: str | None = None
    prompt_category: str | None = None
    phase_deadline: str | None = None
    phase_duration: int | None = None
    answers: dict[str, str] = Field(default_factory=dict)
    round_type: str | None = None
    action_starts_at: str | None = None


class AnswerSubmittedEvent(GameEvent):
    event_type: Literal["answer_submitted"] = "answer_submitted"
    player_id: str
    count: int
    total: int


class GameOverEvent(GameEvent):
    event_type: Literal["game_over"] = "game_over"
    winner: str
    winner_ids: list[str] = Field(default_factory=list)
    players: list[dict]
    scores: dict[str, int] = Field(default_factory=dict)


class TimerTickEvent(GameEvent):
    event_type: Literal["timer_tick"] = "timer_tick"
    remaining_seconds: int


class HostChangedEvent(GameEvent):
    event_type: Literal["host_changed"] = "host_changed"
    new_host_id: str
    new_host_alias: str


class NarrationEvent(GameEvent):
    event_type: Literal["narration"] = "narration"
    text: str
    trigger: str


class SubRoundEvent(GameEvent):
    event_type: Literal["sub_round"] = "sub_round"
    round_type: str
    sub_round_index: int
    payload: dict = Field(default_factory=dict)
    sub_deadline: str | None = None
    phase_duration: int | None = None


class RoundResultsEvent(GameEvent):
    event_type: Literal["round_results"] = "round_results"
    round_type: str
    payload: dict = Field(default_factory=dict)
    scores: dict[str, int] = Field(default_factory=dict)


class VoteSubmittedEvent(GameEvent):
    event_type: Literal["vote_submitted"] = "vote_submitted"
    player_id: str
    vote_count: int  # how many have voted so far
    total: int  # total eligible voters


class FinalRevealEvent(GameEvent):
    event_type: Literal["final_reveal"] = "final_reveal"
    players: list[dict]  # [{id, alias, role, score}]
    winner_ids: list[str] = Field(default_factory=list)
    narrator_text: str | None = None


class SubmitVoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str
    voted_for_player_id: str


class SubmitBrainTestAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str
    selected_index: int
    challenge_index: int


# --- Response models ---


class StatusResponse(BaseModel):
    status: str = "ok"


class MatchmakingStatusResponse(BaseModel):
    human_count: int
    countdown_seconds: int | None = None
    message: str = ""


# --- POST Request models ---


class CreateGameResponse(BaseModel):
    game_id: str
    join_url: str


class JoinGameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_name: str


class JoinGameResponse(BaseModel):
    player_id: str
    alias: str
    game_id: str


class StartGameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str


class SubmitAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str
    answer: str = ""


class GameInfoResponse(BaseModel):
    game_id: str
    phase: str
    player_count: int
    max_players: int


# --- Matchmaking models ---


class MatchmakingJoinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_name: str


class MatchmakingJoinResponse(BaseModel):
    player_id: str
    alias: str
    position: int


class MatchmakingLeaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str


class LobbyStatusEvent(GameEvent):
    event_type: Literal["lobby_status"] = "lobby_status"
    human_count: int
    countdown_seconds: int | None = None
    message: str = ""


class GameAssignedEvent(GameEvent):
    event_type: Literal["game_assigned"] = "game_assigned"
    game_id: str


# --- Debug models ---


class SeedGameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: TellGameState
    start_timers: bool = True
    trigger_ai: bool = True
