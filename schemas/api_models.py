"""API models — SSE events and request/response types."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

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
    players: list[dict]  # sanitized player list (no role for alive players)
    round_number: int
    prompt_text: str | None = None
    prompt_category: str | None = None
    answers: dict[str, str] = Field(default_factory=dict)  # only visible in chat/vote/elimination
    messages: list[dict] = Field(default_factory=list)
    votes: dict[str, str] = Field(default_factory=dict)  # only visible after vote
    phase_deadline: str | None = None  # ISO timestamp
    winner: str | None = None
    is_host: bool = False
    my_answer: str | None = None  # player's own answer (visible during prompt phase)


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
    answers: dict[str, str] = Field(default_factory=dict)  # included on chat phase transition


class ChatMessageEvent(GameEvent):
    event_type: str = "chat_message"
    player_id: str
    player_alias: str
    text: str
    is_answer: bool = False


class AnswerSubmittedEvent(GameEvent):
    event_type: str = "answer_submitted"
    player_id: str
    answer_count: int  # how many have answered
    total_count: int  # how many need to answer


class VoteCastEvent(GameEvent):
    event_type: str = "vote_cast"
    voter_id: str  # who voted (not who they voted for — secret until reveal)
    vote_count: int
    total_count: int


class VoteResultsEvent(GameEvent):
    event_type: str = "vote_results"
    votes: dict[str, str]  # voter_id -> target_id (all revealed)
    vote_tallies: dict[str, int]  # target_id -> count
    eliminated_id: str | None  # None if no consensus
    eliminated_alias: str | None
    was_human: bool | None  # True/False/None
    tie: bool = False
    tie_message: str | None = None  # e.g. "UNIT-7 and BOT-42 tied..."


class EliminationEvent(GameEvent):
    event_type: str = "elimination"
    eliminated_id: str | None
    eliminated_alias: str | None
    was_human: bool | None
    vote_count: int
    tie: bool = False
    tie_message: str | None = None
    no_votes: bool = False  # True if nobody voted


class GameOverEvent(GameEvent):
    event_type: str = "game_over"
    winner: str  # "humans" or "ai"
    players: list[dict]  # full player list with roles revealed


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
    player_name: str  # display name (will get a robot alias instead)


class JoinGameResponse(BaseModel):
    player_id: str
    alias: str
    game_id: str


class StartGameRequest(BaseModel):
    player_id: str
    ai_count: int = 2


class SubmitAnswerRequest(BaseModel):
    player_id: str
    answer: str = ""  # empty = "[no response]"


class SendChatRequest(BaseModel):
    player_id: str
    message: str


class CastVoteRequest(BaseModel):
    player_id: str
    target_id: str


class GameInfoResponse(BaseModel):
    game_id: str
    phase: str
    player_count: int
    max_players: int
