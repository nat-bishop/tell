"""In-game action routes — join, start, answer, question, respond, nominate, vote."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException

from backend.api.deps import (
    get_connection_manager,
    get_game_repository,
    get_settings,
    get_timer_manager,
)
from backend.services.ai_scheduler import assign_personalities
from backend.services.ai_scheduler import on_phase_change as ai_on_phase_change
from backend.services.game_logic import (
    count_expected_questions,
    count_responses,
    fill_missing_answers,
    fill_missing_responses,
    get_alive_players,
    get_player_by_id,
    get_question_target,
    is_question_anonymous,
    is_question_eligible,
    is_response_eligible,
    make_phase_changed_event,
    max_votes_for_player,
    select_round_types,
    transition_to_prompt,
    validate_player_alive,
)
from backend.services.transitions import (
    do_nominate_complete,
    do_prompt_complete,
    do_question_complete,
    do_respond_complete,
    start_phase_timer,
)
from schemas.aliases import generate_aliases
from schemas.api_models import (
    AnswerSubmittedEvent,
    CastVoteRequest,
    JoinGameRequest,
    JoinGameResponse,
    NominateRequest,
    NominationCastEvent,
    PlayerJoinedEvent,
    QuestionSubmittedEvent,
    ResponseSubmittedEvent,
    StartGameRequest,
    SubmitAnswerRequest,
    SubmitQuestionRequest,
    SubmitResponseRequest,
    VoteCastEvent,
)
from schemas.constants import MISSING_ALIAS, NO_RESPONSE
from schemas.game_state import GamePhase, Player, PlayerRole, QuestionEntry, RoundType

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

        player_id = uuid.uuid4().hex[:12]
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


@router.post("/{game_id}/start")
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
            raise HTTPException(status_code=403, detail="Only the host can start the game")

        human_count = len([p for p in state.players if p.role == PlayerRole.HUMAN])
        if human_count < settings.min_humans:
            raise HTTPException(
                status_code=400,
                detail=f"Need at least {settings.min_humans} human players",
            )

        # Spawn AI players
        ai_count = min(max(req.ai_count, settings.min_ai), settings.max_ai)
        existing_aliases = {p.alias for p in state.players}
        ai_aliases = generate_aliases(ai_count, existing_aliases)

        for i in range(ai_count):
            ai_player = Player(
                id=f"ai-{uuid.uuid4().hex[:8]}",
                alias=ai_aliases[i],
                role=PlayerRole.AI,
                is_connected=True,
            )
            state.players.append(ai_player)

            event = PlayerJoinedEvent(
                seq=session.next_seq(),
                player_id=ai_player.id,
                alias=ai_player.alias,
                player_count=len(state.players),
            )
            await cm.broadcast(game_id, event)

        # Assign AI personalities
        ai_player_ids = [p.id for p in state.players if p.role == PlayerRole.AI]
        assign_personalities(game_id, ai_player_ids)

        # Calculate max rounds and generate round types
        state.max_rounds = max(3, human_count + 1)
        state.round_types = select_round_types(state.max_rounds)

        # Transition to first prompt
        transition_to_prompt(state, settings.prompt_duration)
        round_state = state.current_round
        await cm.broadcast(
            game_id,
            make_phase_changed_event(
                state,
                session.next_seq(),
                prompt_text=round_state.prompt_text if round_state else None,
                prompt_category=round_state.prompt_category if round_state else None,
                round_type=round_state.round_type if round_state else RoundType.PROBE,
            ),
        )

    await start_phase_timer(game_id, GamePhase.PROMPT)
    await ai_on_phase_change(game_id, GamePhase.PROMPT)

    log.info(
        "game_started",
        player_count=len(state.players),
        ai_count=ai_count,
        max_rounds=state.max_rounds,
    )
    return {"status": "started", "round": state.round_number}


@router.post("/{game_id}/answer")
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

        result = validate_player_alive(state, req.player_id)
        if isinstance(result, str):
            raise HTTPException(status_code=400, detail=result)

        round_state = state.current_round
        if not round_state:
            raise HTTPException(status_code=400, detail="No active round")

        if req.player_id in round_state.answers:
            raise HTTPException(status_code=400, detail="Already answered")

        answer_text = req.answer.strip() if req.answer.strip() else NO_RESPONSE
        round_state.answers[req.player_id] = answer_text

        alive = get_alive_players(state)
        answer_count = len(round_state.answers)
        total_count = len(alive)

        event = AnswerSubmittedEvent(
            seq=session.next_seq(),
            player_id=req.player_id,
            answer_count=answer_count,
            total_count=total_count,
        )
        await cm.broadcast(game_id, event)
        log.info(
            "answer_submitted",
            player_id=req.player_id,
            answer_count=answer_count,
            total_count=total_count,
        )

        # Check if all answered — early transition
        if answer_count >= total_count:
            get_timer_manager().cancel_timer(game_id)
            fill_missing_answers(state)
            await do_prompt_complete(game_id, session)

    return {"status": "ok"}


@router.post("/{game_id}/nominate")
async def nominate_player(game_id: str, req: NominateRequest):
    """Nominate a player for the hot seat (Interrogation only)."""
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
        if state.phase != GamePhase.NOMINATE:
            raise HTTPException(status_code=400, detail="Not in nominate phase")

        result = validate_player_alive(state, req.player_id)
        if isinstance(result, str):
            raise HTTPException(status_code=400, detail=result)

        round_state = state.current_round
        if not round_state:
            raise HTTPException(status_code=400, detail="No active round")

        # Validate target is alive
        target = next((p for p in state.players if p.id == req.target_id and p.is_alive), None)
        if not target:
            raise HTTPException(status_code=400, detail="Invalid nomination target")

        round_state.nominations[req.player_id] = req.target_id
        log.info(
            "nomination_cast",
            player_id=req.player_id,
            target_id=req.target_id,
        )

        alive = get_alive_players(state)
        nom_count = len(round_state.nominations)
        total_count = len(alive)

        await cm.broadcast(
            game_id,
            NominationCastEvent(
                seq=session.next_seq(),
                voter_id=req.player_id,
                count=nom_count,
                total=total_count,
            ),
        )

        # Early-complete: all alive nominated
        if nom_count >= total_count:
            get_timer_manager().cancel_timer(game_id)
            await do_nominate_complete(game_id, session)

    return {"status": "ok"}


@router.post("/{game_id}/question")
async def submit_question(game_id: str, req: SubmitQuestionRequest):
    """Submit a follow-up question during QUESTION phase."""
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
        if state.phase != GamePhase.QUESTION:
            raise HTTPException(status_code=400, detail="Not in question phase")

        result = validate_player_alive(state, req.player_id)
        if isinstance(result, str):
            raise HTTPException(status_code=400, detail=result)

        round_state = state.current_round
        if not round_state:
            raise HTTPException(status_code=400, detail="No active round")

        # Check if already submitted a question
        already_asked = any(q.questioner_id == req.player_id for q in round_state.questions)
        if already_asked:
            raise HTTPException(status_code=400, detail="Already submitted a question")

        # Determine target
        if not is_question_eligible(round_state, req.player_id):
            raise HTTPException(status_code=400, detail="Hot-seated player cannot submit questions")
        target_id = get_question_target(round_state, req.player_id)

        if not target_id:
            raise HTTPException(status_code=400, detail="No assignment found")

        target_player = get_player_by_id(state, target_id)
        target_alias = target_player.alias if target_player else MISSING_ALIAS

        entry = QuestionEntry(
            questioner_id=req.player_id,
            target_id=target_id,
            target_alias=target_alias,
            question=req.question.strip(),
            anonymous=is_question_anonymous(round_state.round_type),
        )
        round_state.questions.append(entry)

        expected = count_expected_questions(state)
        q_count = len(round_state.questions)

        await cm.broadcast(
            game_id,
            QuestionSubmittedEvent(
                seq=session.next_seq(),
                count=q_count,
                total=expected,
            ),
        )
        log.info("question_submitted", player_id=req.player_id, count=q_count, total=expected)

        # Early-complete
        if q_count >= expected:
            get_timer_manager().cancel_timer(game_id)
            await do_question_complete(game_id, session)

    return {"status": "ok"}


@router.post("/{game_id}/respond")
async def submit_response(game_id: str, req: SubmitResponseRequest):
    """Submit a response to a question during RESPOND phase."""
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
        if state.phase != GamePhase.RESPOND:
            raise HTTPException(status_code=400, detail="Not in respond phase")

        result = validate_player_alive(state, req.player_id)
        if isinstance(result, str):
            raise HTTPException(status_code=400, detail=result)

        round_state = state.current_round
        if not round_state:
            raise HTTPException(status_code=400, detail="No active round")

        if not is_response_eligible(round_state, req.player_id):
            raise HTTPException(status_code=400, detail="Only the hot-seated player can respond")

        target_q = next(
            (
                q
                for q in round_state.questions
                if q.target_id == req.player_id and q.response is None
            ),
            None,
        )
        if not target_q:
            raise HTTPException(status_code=400, detail="No pending question or already responded")
        target_q.response = req.response.strip()

        player = get_player_by_id(state, req.player_id)
        player_alias = player.alias if player else MISSING_ALIAS

        responded_count, expected = count_responses(round_state)

        await cm.broadcast(
            game_id,
            ResponseSubmittedEvent(
                seq=session.next_seq(),
                target_id=req.player_id,
                target_alias=player_alias,
                response=req.response.strip(),
                count=responded_count,
                total=expected,
            ),
        )
        log.info(
            "response_submitted", player_id=req.player_id, count=responded_count, total=expected
        )

        # Early-complete
        if responded_count >= expected:
            get_timer_manager().cancel_timer(game_id)
            fill_missing_responses(state)
            await do_respond_complete(game_id, session)

    return {"status": "ok"}


@router.post("/{game_id}/vote")
async def cast_vote(game_id: str, req: CastVoteRequest):
    """Cast votes for who you think is human (up to 3, changeable)."""
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
        if state.phase != GamePhase.REVIEW:
            raise HTTPException(status_code=400, detail="Not in review phase")

        result = validate_player_alive(state, req.player_id)
        if isinstance(result, str):
            raise HTTPException(status_code=400, detail=result)

        round_state = state.current_round
        if not round_state:
            raise HTTPException(status_code=400, detail="No active round")

        alive = get_alive_players(state)
        alive_others = [p for p in alive if p.id != req.player_id]
        max_v = max_votes_for_player(len(alive_others) + 1)  # +1 because voter is alive too

        if len(req.target_ids) > max_v:
            raise HTTPException(status_code=400, detail=f"Max {max_v} votes allowed")

        # Validate all targets are alive
        alive_ids = {p.id for p in alive}
        for tid in req.target_ids:
            if tid not in alive_ids:
                raise HTTPException(status_code=400, detail=f"Invalid vote target: {tid}")

        # Overwrite previous votes (changeable)
        round_state.votes[req.player_id] = req.target_ids

        vote_count = len(round_state.votes)
        total_count = len(alive)

        event = VoteCastEvent(
            seq=session.next_seq(),
            voter_id=req.player_id,
            vote_count=vote_count,
            total_count=total_count,
        )
        await cm.broadcast(game_id, event)
        log.info(
            "vote_cast", player_id=req.player_id, vote_count=vote_count, total_count=total_count
        )

        # NO early-complete for REVIEW — always runs full timer

    return {"status": "ok"}
