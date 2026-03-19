"""In-game action routes — join, start, answer, vote, brain-test-answer."""

from __future__ import annotations

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
    do_vote_complete,
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
    SubmitVoteRequest,
    VoteSubmittedEvent,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import GamePhase, Player, PlayerRole

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
    """Start the game (host only). Spawns 6 AI players and begins round 1."""
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

    ai_count = settings.max_ai  # always 6
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

        if req.player_id in round_state.answers:
            raise HTTPException(status_code=400, detail="Already answered")

        answer_text = req.answer.strip() if req.answer.strip() else NO_RESPONSE
        round_state.answers[req.player_id] = answer_text

        answer_count = len(round_state.answers)
        total_count = len(state.players)

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


@router.post("/{game_id}/vote", response_model=StatusResponse)
async def submit_vote(game_id: str, req: SubmitVoteRequest):
    """Cast a gallery vote — who sounds most human?"""
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
        if state.phase != GamePhase.VOTE:
            raise HTTPException(status_code=400, detail="Not in vote phase")

        player = get_player_by_id(state, req.player_id)
        if not player:
            raise HTTPException(status_code=400, detail="Player not found")

        if req.voted_for_player_id == req.player_id:
            raise HTTPException(status_code=400, detail="Cannot vote for yourself")

        target = get_player_by_id(state, req.voted_for_player_id)
        if not target:
            raise HTTPException(status_code=400, detail="Target player not found")

        round_state = state.current_round
        if not round_state:
            raise HTTPException(status_code=400, detail="No active round")

        # Overwrite allowed (changeable vote)
        round_state.gallery_votes[req.player_id] = req.voted_for_player_id

        vote_count = len(round_state.gallery_votes)
        total = len(state.players)

        await cm.broadcast(
            game_id,
            VoteSubmittedEvent(
                seq=session.next_seq(),
                player_id=req.player_id,
                vote_count=vote_count,
                total=total,
            ),
        )
        log.info(
            "vote_cast",
            player_id=req.player_id,
            vote_count=vote_count,
            total=total,
        )

        # Early complete: all voted
        if vote_count >= total:
            get_timer_manager().cancel_timer(game_id)
            await do_vote_complete(game_id, session)

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
        if state.phase != GamePhase.BRAIN_TEST:
            raise HTTPException(status_code=400, detail="Not in brain test phase")

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
