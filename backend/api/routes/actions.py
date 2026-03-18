"""In-game action routes — join, start, answer, question, respond, nominate, vote."""

from __future__ import annotations

import asyncio
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
    count_expected_questions,
    count_responses,
    fill_missing_answers,
    fill_missing_responses,
    get_alive_players,
    get_player_by_id,
    get_question_target,
    is_question_eligible,
    is_response_eligible,
    max_votes_for_player,
    validate_player_alive,
)
from backend.services.transitions import (
    do_nominate_complete,
    do_prompt_complete,
    do_question_complete,
    do_respond_complete,
    initialize_and_start_game,
)
from schemas.aliases import generate_aliases, generate_player_id
from schemas.api_models import (
    AnswerSubmittedEvent,
    CastComedyVoteRequest,
    CastVoteRequest,
    JoinGameRequest,
    JoinGameResponse,
    NominateRequest,
    NominationCastEvent,
    PlayerJoinedEvent,
    QuestionSubmittedEvent,
    ResponseSubmittedEvent,
    SendDiscussionMessageRequest,
    StartGameRequest,
    StatusResponse,
    SubmitAnswerRequest,
    SubmitBrainTestAnswerRequest,
    SubmitMatchupVoteRequest,
    SubmitQuestionRequest,
    SubmitResponseRequest,
    VoteCastEvent,
)
from schemas.constants import MISSING_ALIAS, NO_RESPONSE
from schemas.game_state import GamePhase, Player, PlayerRole, QuestionEntry

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

        result = validate_player_alive(state, req.player_id)
        if isinstance(result, str):
            raise HTTPException(status_code=400, detail=result)

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

        alive = get_alive_players(state)
        answer_count = len(round_state.answers)
        total_count = len(alive)
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


@router.post("/{game_id}/nominate", response_model=StatusResponse)
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


@router.post("/{game_id}/question", response_model=StatusResponse)
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


@router.post("/{game_id}/respond", response_model=StatusResponse)
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


@router.post("/{game_id}/vote", response_model=StatusResponse)
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

        # Validate not self-voting and all targets are alive
        if req.player_id in req.target_ids:
            raise HTTPException(status_code=400, detail="Cannot vote for yourself")
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
            count=vote_count,
            total=total_count,
        )
        await cm.broadcast(game_id, event)
        log.info("vote_cast", player_id=req.player_id, count=vote_count, total=total_count)

        # NO early-complete for REVIEW — always runs full timer

    return {"status": "ok"}


@router.post("/{game_id}/comedy-vote", response_model=StatusResponse)
async def cast_comedy_vote(game_id: str, req: CastComedyVoteRequest):
    """Cast a comedy vote for the funniest answer (one vote, changeable)."""
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

        # Validate target is alive
        alive_ids = {p.id for p in state.players if p.is_alive}
        if req.target_id not in alive_ids:
            raise HTTPException(status_code=400, detail="Invalid comedy vote target")

        # Allow voting for self (comedy is comedy)
        round_state.comedy_votes[req.player_id] = req.target_id
        log.info(
            "comedy_vote_cast",
            player_id=req.player_id,
            target_id=req.target_id,
        )

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

        result = validate_player_alive(state, req.player_id)
        if isinstance(result, str):
            raise HTTPException(status_code=400, detail=result)

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
        if state.phase != GamePhase.MATCHUP:
            raise HTTPException(status_code=400, detail="Not in matchup phase")

        result = validate_player_alive(state, req.player_id)
        if isinstance(result, str):
            raise HTTPException(status_code=400, detail=result)

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


@router.post("/{game_id}/discussion-message", response_model=StatusResponse)
async def send_discussion_message(game_id: str, req: SendDiscussionMessageRequest):
    """Send a chat message during the DISCUSS sub-phase of REVIEW."""
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
        player = result

        message = req.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        if len(message) > 120:
            raise HTTPException(status_code=400, detail="Message too long (max 120 chars)")

        round_state = state.current_round
        if not round_state:
            raise HTTPException(status_code=400, detail="No active round")

        count = round_state.discussion_counts.get(req.player_id, 0)
        if count >= 3:
            raise HTTPException(status_code=400, detail="Message limit reached (max 3)")

        round_state.discussion_counts[req.player_id] = count + 1
        log.info(
            "discussion_message",
            player_id=req.player_id,
            msg_count=count + 1,
        )

    # Fire buffered broadcast + AI reaction pipeline (outside lock)
    from backend.services.ai_scheduler import on_discussion_message, register_task

    task = asyncio.create_task(on_discussion_message(game_id, req.player_id, player.alias, message))
    register_task(game_id, task)

    return {"status": "ok"}
