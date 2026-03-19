"""In-game action routes — join, start, answer, matchup-vote, brain-test-answer."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException

from backend.api.deps import (
    get_connection_manager,
    get_game_repository,
    get_settings,
    get_timer_manager,
)
from backend.services.game_logic import (
    fill_missing_answers,
    get_player_by_id,
)
from backend.services.transitions import (
    do_prompt_complete,
    initialize_and_start_game,
)
from schemas.aliases import generate_aliases, generate_player_id
from schemas.api_models import (
    AnswerSubmittedEvent,
    JoinGameRequest,
    JoinGameResponse,
    PlayerJoinedEvent,
    StartGameRequest,
    StatusResponse,
    SubmitAnswerRequest,
    SubmitBrainTestAnswerRequest,
    SubmitMatchupVoteRequest,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import GamePhase, Player, PlayerRole, RoundType

router = APIRouter()

log = structlog.get_logger(__name__)


@router.post("/{game_id}/join", response_model=JoinGameResponse)
async def join_game(game_id: str, req: JoinGameRequest):
    """Join a game lobby."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(game_id=game_id)
    cm = get_connection_manager()
    repo = get_game_repository()
    settings = get_settings()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="Game not found")

        state = session.state
        if state.phase != GamePhase.LOBBY:
            raise HTTPException(status_code=400, detail="Game already in progress")

        if len(state.players) >= settings.max_players:
            raise HTTPException(status_code=400, detail="Game is full")

        player_id = generate_player_id()
        existing_aliases = {p.alias for p in state.players}
        aliases = generate_aliases(1, existing_aliases)
        alias = aliases[0]

        is_host = len(state.players) == 0
        player = Player(
            id=player_id,
            alias=alias,
            role=PlayerRole.HUMAN,
            is_host=is_host,
        )
        state.players.append(player)

        event = PlayerJoinedEvent(
            seq=session.next_seq(),
            player_id=player_id,
            alias=alias,
            player_count=len(state.players),
        )
        await cm.broadcast(game_id, event)
        log.info("player_joined", alias=alias, player_count=len(state.players))

    return JoinGameResponse(player_id=player_id, alias=alias, game_id=game_id)


@router.post("/{game_id}/start", response_model=StatusResponse)
async def start_game(game_id: str, req: StartGameRequest):
    """Start the game (host only). Spawns AI players and begins round 1."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(game_id=game_id)
    cm = get_connection_manager()
    repo = get_game_repository()
    settings = get_settings()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="Game not found")

        state = session.state
        if state.phase != GamePhase.LOBBY:
            raise HTTPException(status_code=400, detail="Game already started")

        host = next((p for p in state.players if p.id == req.player_id and p.is_host), None)
        if not host:
            raise HTTPException(status_code=400, detail="Only the host can start the game")

        human_count = len([p for p in state.players if p.role == PlayerRole.HUMAN])
        if human_count < settings.min_humans:
            raise HTTPException(
                status_code=400,
                detail=f"Need at least {settings.min_humans} human players",
            )

    ai_count = min(max(req.ai_count, settings.min_ai), settings.max_ai)
    await initialize_and_start_game(game_id, ai_count)

    return {"status": "ok"}


@router.post("/{game_id}/answer", response_model=StatusResponse)
async def submit_answer(game_id: str, req: SubmitAnswerRequest):
    """Submit an answer to the current prompt."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(game_id=game_id)
    cm = get_connection_manager()
    repo = get_game_repository()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="Game not found")

        state = session.state
        if state.phase != GamePhase.PROMPT:
            raise HTTPException(status_code=400, detail="Not in prompt phase")

        player = get_player_by_id(state, req.player_id)
        if not player:
            raise HTTPException(status_code=400, detail="Player not found")

        round_state = state.current_round
        if not round_state:
            raise HTTPException(status_code=400, detail="No active round")

        # Reject answers during reading period
        if round_state.writing_begins_at and datetime.now(UTC) < round_state.writing_begins_at:
            raise HTTPException(status_code=400, detail="Reading period — answers not accepted yet")

        # Bye players can't submit answers
        if round_state.bye_player_id == req.player_id:
            raise HTTPException(status_code=400, detail="Bye player does not answer")

        if req.player_id in round_state.answers:
            raise HTTPException(status_code=400, detail="Already answered")

        answer_text = req.answer.strip() if req.answer.strip() else NO_RESPONSE
        round_state.answers[req.player_id] = answer_text

        answer_count = len(round_state.answers)
        total_count = len(state.players)
        # Exclude bye player from total in matchup rounds
        if round_state.bye_player_id:
            total_count -= 1

        event = AnswerSubmittedEvent(
            seq=session.next_seq(),
            player_id=req.player_id,
            count=answer_count,
            total=total_count,
        )
        await cm.broadcast(game_id, event)
        log.info(
            "answer_submitted",
            player_id=req.player_id,
            count=answer_count,
            total=total_count,
        )

        # Check if all answered — early transition
        if answer_count >= total_count:
            get_timer_manager().cancel_timer(game_id)
            fill_missing_answers(state)
            await do_prompt_complete(game_id, session)

    return {"status": "ok"}


@router.post("/{game_id}/brain-test-answer", response_model=StatusResponse)
async def submit_brain_test_answer(game_id: str, req: SubmitBrainTestAnswerRequest):
    """Submit an answer to a brain test challenge."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(game_id=game_id)
    cm = get_connection_manager()
    repo = get_game_repository()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="Game not found")

        state = session.state
        if state.phase != GamePhase.ACTIVE:
            raise HTTPException(status_code=400, detail="Not in active phase")

        round_state_check = state.current_round
        if not round_state_check or round_state_check.round_type != RoundType.BRAIN_TEST:
            raise HTTPException(status_code=400, detail="Not in brain test round")

        player = get_player_by_id(state, req.player_id)
        if not player:
            raise HTTPException(status_code=400, detail="Player not found")

        round_state = state.current_round
        if not round_state:
            raise HTTPException(status_code=400, detail="No active round")

        if req.challenge_index >= len(round_state.brain_challenges):
            raise HTTPException(status_code=400, detail="Invalid challenge index")

        if req.selected_index < 0 or req.selected_index > 3:
            raise HTTPException(status_code=400, detail="selected_index must be 0-3")

        ch = round_state.brain_challenges[req.challenge_index]
        if req.player_id in ch.responses:
            raise HTTPException(status_code=400, detail="Already answered")

        ch.responses[req.player_id] = req.selected_index
        log.info(
            "brain_test_answer",
            player_id=req.player_id,
            challenge_index=req.challenge_index,
        )

    return {"status": "ok"}


@router.post("/{game_id}/matchup-vote", response_model=StatusResponse)
async def submit_matchup_vote(game_id: str, req: SubmitMatchupVoteRequest):
    """Cast a vote in a matchup sub-round (LEFT=0 or RIGHT=1)."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(game_id=game_id)
    cm = get_connection_manager()
    repo = get_game_repository()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="Game not found")

        state = session.state
        if state.phase != GamePhase.ACTIVE:
            raise HTTPException(status_code=400, detail="Not in active phase")

        round_state_check = state.current_round
        if not round_state_check or round_state_check.round_type != RoundType.TASK:
            raise HTTPException(status_code=400, detail="Not in matchup round")

        player = get_player_by_id(state, req.player_id)
        if not player:
            raise HTTPException(status_code=400, detail="Player not found")

        round_state = state.current_round
        if not round_state:
            raise HTTPException(status_code=400, detail="No active round")

        if req.matchup_index >= len(round_state.matchups):
            raise HTTPException(status_code=400, detail="Invalid matchup index")

        if req.choice not in (0, 1):
            raise HTTPException(status_code=400, detail="Choice must be 0 (left) or 1 (right)")

        matchup = round_state.matchups[req.matchup_index]

        # Players in the pair can't vote on their own matchup
        if req.player_id in matchup.pair:
            raise HTTPException(status_code=400, detail="Cannot vote on your own matchup")

        # Overwrite previous vote (changeable)
        matchup.votes[req.player_id] = req.choice
        log.info(
            "matchup_vote_cast",
            player_id=req.player_id,
            matchup_index=req.matchup_index,
            choice=req.choice,
        )

    return {"status": "ok"}
