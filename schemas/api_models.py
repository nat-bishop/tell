"""API models — SSE events and request/response types."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from schemas.game_state import TellGameState

# --- Base event ---


class GameEvent(BaseModel):
    """Base SSE event with monotonic sequence number."""

    event_type: str
    seq: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# --- SSE Events ---


class StateSyncEvent(GameEvent):
    event_type: str = "state_sync"
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
    votes: dict[str, list[str]] = Field(default_factory=dict)
    phase_deadline: str | None = None
    winner: str | None = None
    is_host: bool = False
    my_answer: str | None = None


class PlayerJoinedEvent(GameEvent):
    event_type: str = "player_joined"
    player_id: str
    alias: str
    player_count: int


class PlayerDisconnectedEvent(GameEvent):
    event_type: str = "player_disconnected"
    player_id: str


class PlayerReconnectedEvent(GameEvent):
    event_type: str = "player_reconnected"
    player_id: str


class PhaseChangedEvent(GameEvent):
    event_type: str = "phase_changed"
    phase: str
    round_number: int
    prompt_text: str | None = None
    prompt_category: str | None = None
    phase_deadline: str | None = None
    answers: dict[str, str] = Field(default_factory=dict)
    round_type: str | None = None
    assignments: dict[str, str] = Field(default_factory=dict)
    nominated_id: str | None = None
    questions: list[dict] = Field(default_factory=list)
    synthesis: str | None = None


class AnswerSubmittedEvent(GameEvent):
    event_type: str = "answer_submitted"
    player_id: str
    answer_count: int
    total_count: int


class NominationCastEvent(GameEvent):
    event_type: str = "nomination_cast"
    voter_id: str
    count: int
    total: int


class NominatedEvent(GameEvent):
    event_type: str = "nominated"
    nominated_id: str
    nominated_alias: str


class QuestionSubmittedEvent(GameEvent):
    event_type: str = "question_submitted"
    count: int
    total: int


class ResponseSubmittedEvent(GameEvent):
    event_type: str = "response_submitted"
    target_id: str
    target_alias: str
    response: str
    count: int
    total: int


class SynthesisReadyEvent(GameEvent):
    event_type: str = "synthesis_ready"
    synthesis: str


class VerdictEvent(GameEvent):
    event_type: str = "verdict"
    verdict: str


class VoteCastEvent(GameEvent):
    event_type: str = "vote_cast"
    voter_id: str
    vote_count: int
    total_count: int


class VoteResultsEvent(GameEvent):
    event_type: str = "vote_results"
    votes: dict[str, list[str]]
    vote_tallies: dict[str, int]
    eliminated_id: str | None
    eliminated_alias: str | None
    was_human: bool | None
    tie: bool = False
    tie_message: str | None = None


class EliminationEvent(GameEvent):
    event_type: str = "elimination"
    eliminated_id: str | None
    eliminated_alias: str | None
    was_human: bool | None
    vote_count: int
    tie: bool = False
    tie_message: str | None = None
    no_votes: bool = False


class GameOverEvent(GameEvent):
    event_type: str = "game_over"
    winner: str
    players: list[dict]


class TimerTickEvent(GameEvent):
    event_type: str = "timer_tick"
    remaining_seconds: int


class HostChangedEvent(GameEvent):
    event_type: str = "host_changed"
    new_host_id: str
    new_host_alias: str


# --- POST Request models ---


class CreateGameRequest(BaseModel):
    ai_count: int = 2


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
    event_type: str = "lobby_status"
    human_count: int
    countdown_seconds: int | None = None
    message: str = ""


class GameAssignedEvent(GameEvent):
    event_type: str = "game_assigned"
    game_id: str


# --- Debug models ---


class SeedGameRequest(BaseModel):
    state: TellGameState
    start_timers: bool = True
    trigger_ai: bool = True
