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
    winner_ids: list[str] = Field(default_factory=list)
    is_host: bool = False
    my_answer: str | None = None
    # Reading period
    writing_begins_at: str | None = None


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
    action_starts_at: str | None = None
    # Discussion sub-phase timestamps (REVIEW only)
    discuss_starts_at: str | None = None
    vote_starts_at: str | None = None


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
    winner_ids: list[str] = Field(default_factory=list)
    players: list[dict]


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


class BrainTestChallengeEvent(GameEvent):
    event_type: Literal["brain_test_challenge"] = "brain_test_challenge"
    challenge_index: int
    challenge_type: str
    question: str
    options: list[str] = Field(default_factory=list)
    sub_deadline: str | None = None
    phase_duration: int | None = None


class BrainTestResultsEvent(GameEvent):
    event_type: Literal["brain_test_results"] = "brain_test_results"
    # player_id -> list of {question, options, selected_index, correct_index, challenge_type}
    results: dict[str, list[dict]]
    scores: dict[str, int] | None = None
    winner_id: str | None = None
    winner_alias: str | None = None
    ability_awarded: str | None = None


class DiscussionMessageEvent(GameEvent):
    event_type: Literal["discussion_message"] = "discussion_message"
    sender_id: str
    sender_alias: str
    message: str


class AbilityAwardedEvent(GameEvent):
    event_type: Literal["ability_awarded"] = "ability_awarded"
    holder_id: str
    holder_alias: str
    ability_type: str


class ScanResultEvent(GameEvent):
    event_type: Literal["scan_result"] = "scan_result"
    results: list[dict]  # [{player_id, alias, claimed_role}]


class SubmitBrainTestAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str
    selected_index: int
    challenge_index: int


class SendDiscussionMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str
    message: str  # max 120 chars


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
    ai_count: int = 2


class SubmitAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str
    answer: str = ""


class NominateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str
    target_id: str


class SubmitQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str
    question: str


class SubmitResponseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str
    response: str


class CastVoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str
    target_ids: list[str]


class CastComedyVoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_id: str
    target_id: str


class ComedyWinnerEvent(GameEvent):
    event_type: Literal["comedy_winner"] = "comedy_winner"
    winner_id: str
    winner_alias: str
    vote_count: int


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
