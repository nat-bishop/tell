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
    do_active_complete,
    do_prompt_complete,
    initialize_and_start_game,
)
from schemas.aliases import generate_aliases, generate_player_id
from schemas.api_models import (
    AnswerSubmittedEvent,
    JoinGameRequest,
    JoinGameResponse,
    PlayerJoinedEvent,
    SignalPhraseResponse,
    StartGameRequest,
    StatusResponse,
    SubmitAnswerRequest,
    SubmitBrainTestAnswerRequest,
    SubmitSignalGuessRequest,
    SubmitVoteRequest,
    SubmitWagerBetRequest,
    SubmitWagerGuessRequest,
    VoteSubmittedEvent,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import GamePhase, Player, PlayerRole, RoundType

router = APIRouter()

log = structlog.get_logger(__name__)


@router.post("/{game_id}/join", response_model=JoinGameResponse)
async def join_game(game_id: str, req: JoinGameRequest) -> JoinGameResponse:
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
async def start_game(game_id: str, req: StartGameRequest) -> dict[str, str]:
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
async def submit_answer(game_id: str, req: SubmitAnswerRequest) -> dict[str, str]:
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
async def submit_vote(game_id: str, req: SubmitVoteRequest) -> dict[str, str]:
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
        if state.phase != GamePhase.ACTIVE:
            raise HTTPException(status_code=400, detail="Not in active phase")

        round_state = state.current_round
        if not round_state or round_state.round_type != RoundType.TASK:
            raise HTTPException(status_code=400, detail="Not a task round")

        player = get_player_by_id(state, req.player_id)
        if not player:
            raise HTTPException(status_code=400, detail="Player not found")

        if req.voted_for_player_id == req.player_id:
            raise HTTPException(status_code=400, detail="Cannot vote for yourself")

        target = get_player_by_id(state, req.voted_for_player_id)
        if not target:
            raise HTTPException(status_code=400, detail="Target player not found")

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
            await do_active_complete(game_id, session)

    return {"status": "ok"}


@router.post("/{game_id}/brain-test-answer", response_model=StatusResponse)
async def submit_brain_test_answer(
    game_id: str, req: SubmitBrainTestAnswerRequest
) -> dict[str, str]:
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

        round_state = state.current_round
        if not round_state or round_state.round_type != RoundType.BRAIN_TEST:
            raise HTTPException(status_code=400, detail="Not a brain test round")

        player = get_player_by_id(state, req.player_id)
        if not player:
            raise HTTPException(status_code=400, detail="Player not found")

        if not (0 <= req.challenge_index < len(round_state.brain_challenges)):
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


@router.post("/{game_id}/wager-guess", response_model=StatusResponse)
async def submit_wager_guess(game_id: str, req: SubmitWagerGuessRequest) -> dict[str, str]:
    """Submit a numerical guess for a wager question."""
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

        round_state = state.current_round
        if not round_state or round_state.round_type != RoundType.WAGER:
            raise HTTPException(status_code=400, detail="Not a wager round")

        player = get_player_by_id(state, req.player_id)
        if not player:
            raise HTTPException(status_code=400, detail="Player not found")

        if not (0 <= req.question_index < len(round_state.wager_questions)):
            raise HTTPException(status_code=400, detail="Invalid question index")

        # Validate sub-round: must be a guess sub-round for this question
        current_q_idx = round_state.current_sub_round // 2
        is_guess_phase = round_state.current_sub_round % 2 == 0
        if req.question_index != current_q_idx or not is_guess_phase:
            raise HTTPException(status_code=400, detail="Not in guess phase for this question")

        q = round_state.wager_questions[req.question_index]
        # Clamp value to range
        clamped = max(q.range_min, min(q.range_max, req.value))
        # Overwrite allowed
        q.guesses[req.player_id] = clamped

        log.info(
            "wager_guess_submitted",
            player_id=req.player_id,
            question_index=req.question_index,
            value=clamped,
        )

    return {"status": "ok"}


@router.post("/{game_id}/wager-bet", response_model=StatusResponse)
async def submit_wager_bet(game_id: str, req: SubmitWagerBetRequest) -> dict[str, str]:
    """Place a bet on whose guess is closest."""
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

        round_state = state.current_round
        if not round_state or round_state.round_type != RoundType.WAGER:
            raise HTTPException(status_code=400, detail="Not a wager round")

        player = get_player_by_id(state, req.player_id)
        if not player:
            raise HTTPException(status_code=400, detail="Player not found")

        if not (0 <= req.question_index < len(round_state.wager_questions)):
            raise HTTPException(status_code=400, detail="Invalid question index")

        # Validate sub-round: must be a bet sub-round for this question
        current_q_idx = round_state.current_sub_round // 2
        is_bet_phase = round_state.current_sub_round % 2 == 1
        if req.question_index != current_q_idx or not is_bet_phase:
            raise HTTPException(status_code=400, detail="Not in bet phase for this question")

        q = round_state.wager_questions[req.question_index]

        # Validate target exists in game
        target = get_player_by_id(state, req.target_player_id)
        if not target:
            raise HTTPException(status_code=400, detail="Target player not found")

        # Validate target has a guess for this question
        if req.target_player_id not in q.guesses:
            raise HTTPException(
                status_code=400, detail="Target player has no guess for this question"
            )

        # Self-bet IS allowed (unlike gallery vote)
        # Overwrite allowed
        q.bets[req.player_id] = req.target_player_id

        log.info(
            "wager_bet_submitted",
            player_id=req.player_id,
            question_index=req.question_index,
            target=req.target_player_id,
        )

    return {"status": "ok"}


@router.get("/{game_id}/signal-phrase", response_model=SignalPhraseResponse)
async def get_signal_phrase(game_id: str, player_id: str) -> SignalPhraseResponse:
    """Get the player's secret phrase and constraint for a Signal round."""
    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    state = session.state
    if state.phase != GamePhase.PROMPT:
        raise HTTPException(status_code=400, detail="Not in prompt phase")

    rs = state.current_round
    if not rs or rs.round_type != RoundType.SIGNAL:
        raise HTTPException(status_code=400, detail="Not a signal round")

    phrase = rs.signal_phrases.get(player_id)
    if not phrase:
        raise HTTPException(status_code=400, detail="Player not in this round")

    return SignalPhraseResponse(phrase=phrase, constraint=rs.signal_constraint)


@router.post("/{game_id}/signal-guess", response_model=StatusResponse)
async def submit_signal_guess(game_id: str, req: SubmitSignalGuessRequest) -> dict[str, str]:
    """Submit a guess for the current Signal sub-round."""
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

        rs = state.current_round
        if not rs or rs.round_type != RoundType.SIGNAL:
            raise HTTPException(status_code=400, detail="Not a signal round")

        player = get_player_by_id(state, req.player_id)
        if not player:
            raise HTTPException(status_code=400, detail="Player not found")

        if req.sub_round_index != rs.current_sub_round:
            raise HTTPException(status_code=400, detail="Wrong sub-round")

        if req.sub_round_index >= len(rs.signal_player_order):
            raise HTTPException(status_code=400, detail="Invalid sub-round index")

        featured_pid = rs.signal_player_order[req.sub_round_index]

        if req.player_id == featured_pid:
            raise HTTPException(status_code=400, detail="Cannot guess your own phrase")

        guess_text = req.guess.strip()
        if not guess_text:
            raise HTTPException(status_code=400, detail="Guess cannot be empty")

        # Overwrite allowed (free revision)
        if featured_pid not in rs.signal_guesses:
            rs.signal_guesses[featured_pid] = {}
        rs.signal_guesses[featured_pid][req.player_id] = guess_text

        log.info(
            "signal_guess_submitted",
            player_id=req.player_id,
            sub_round_index=req.sub_round_index,
        )

    return {"status": "ok"}
