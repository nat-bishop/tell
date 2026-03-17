"""API models — SSE events and request/response types."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from schemas.game_state import TellGameState

# --- Base event ---


class GameEvent(BaseModel):
    """Base SSE event with monotonic sequence number.

    Subclasses narrow event_type to Literal types for TypeScript discriminated unions.
    Pyright flags these as reportIncompatibleVariableOverride — this is a known
    Pydantic v2 pattern that works correctly at runtime and for OpenAPI codegen.
    """

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
    questions: list[dict] = Field(default_factory=list)
    assignments: dict[str, str] = Field(default_factory=dict)
    nominated_id: str | None = None
    nominations: dict[str, str] = Field(default_factory=dict)
    synthesis: str | None = None
    verdict: str | None = None
    my_votes: list[str] = Field(default_factory=list)
    phase_deadline: str | None = None
    phase_duration: int | None = None
    winner: str | None = None
    is_host: bool = False
    my_answer: str | None = None
    # Reading period
    writing_begins_at: str | None = None
    # Word Chain
    chain_rounds: list[dict] = Field(default_factory=list)
    current_sub_round: int = 0


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
    assignments: dict[str, str] = Field(default_factory=dict)
    nominated_id: str | None = None
    questions: list[dict] = Field(default_factory=list)
    synthesis: str | None = None
    writing_begins_at: str | None = None


class AnswerSubmittedEvent(GameEvent):
    event_type: Literal["answer_submitted"] = "answer_submitted"
    player_id: str
    count: int
    total: int


class NominationCastEvent(GameEvent):
    event_type: Literal["nomination_cast"] = "nomination_cast"
    voter_id: str
    count: int
    total: int


class NominatedEvent(GameEvent):
    event_type: Literal["nominated"] = "nominated"
    nominated_id: str
    nominated_alias: str


class QuestionSubmittedEvent(GameEvent):
    event_type: Literal["question_submitted"] = "question_submitted"
    count: int
    total: int


class ResponseSubmittedEvent(GameEvent):
    event_type: Literal["response_submitted"] = "response_submitted"
    target_id: str
    target_alias: str
    response: str
    count: int
    total: int


class SynthesisReadyEvent(GameEvent):
    event_type: Literal["synthesis_ready"] = "synthesis_ready"
    synthesis: str


class VerdictEvent(GameEvent):
    event_type: Literal["verdict"] = "verdict"
    verdict: str


class VoteCastEvent(GameEvent):
    event_type: Literal["vote_cast"] = "vote_cast"
    voter_id: str
    count: int
    total: int


class VoteResultsEvent(GameEvent):
    event_type: Literal["vote_results"] = "vote_results"
    votes: dict[str, list[str]]
    vote_tallies: dict[str, int]
    eliminated_id: str | None
    eliminated_alias: str | None
    was_human: bool | None
    tie: bool = False
    tie_message: str | None = None


class EliminationEvent(GameEvent):
    event_type: Literal["elimination"] = "elimination"
    eliminated_id: str | None
    eliminated_alias: str | None
    was_human: bool | None
    vote_count: int
    tie: bool = False
    tie_message: str | None = None
    no_votes: bool = False


class GameOverEvent(GameEvent):
    event_type: Literal["game_over"] = "game_over"
    winner: str
    players: list[dict]


class TimerTickEvent(GameEvent):
    event_type: Literal["timer_tick"] = "timer_tick"
    remaining_seconds: int


class HostChangedEvent(GameEvent):
    event_type: Literal["host_changed"] = "host_changed"
    new_host_id: str
    new_host_alias: str


class ChainSeedEvent(GameEvent):
    event_type: Literal["chain_seed"] = "chain_seed"
    word: str
    round_index: int
    sub_deadline: str | None = None
    chain_so_far: list[str] = Field(default_factory=list)
    phase_duration: int | None = None


class ChainProgressEvent(GameEvent):
    event_type: Literal["chain_progress"] = "chain_progress"
    round_index: int
    count: int
    total: int


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
    player_name: str


class JoinGameResponse(BaseModel):
    player_id: str
    alias: str
    game_id: str


class StartGameRequest(BaseModel):
    player_id: str
    ai_count: int = 2


class SubmitAnswerRequest(BaseModel):
    player_id: str
    answer: str = ""


class NominateRequest(BaseModel):
    player_id: str
    target_id: str


class SubmitQuestionRequest(BaseModel):
    player_id: str
    question: str


class SubmitResponseRequest(BaseModel):
    player_id: str
    response: str


class CastVoteRequest(BaseModel):
    player_id: str
    target_ids: list[str]


class SubmitChainWordRequest(BaseModel):
    player_id: str
    word: str
    round_index: int


class GameInfoResponse(BaseModel):
    game_id: str
    phase: str
    player_count: int
    max_players: int


# --- Matchmaking models ---


class MatchmakingJoinRequest(BaseModel):
    player_name: str


class MatchmakingJoinResponse(BaseModel):
    player_id: str
    alias: str
    position: int


class MatchmakingLeaveRequest(BaseModel):
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
    state: TellGameState
    start_timers: bool = True
    trigger_ai: bool = True
