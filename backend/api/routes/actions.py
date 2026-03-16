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
    assign_question_targets,
    check_game_over,
    fill_missing_answers,
    fill_missing_responses,
    get_alive_players,
    get_player_by_id,
    make_game_over_event,
    make_phase_changed_event,
    max_votes_for_player,
    resolve_nominations,
    resolve_votes,
    select_round_types,
    transition_to_elimination,
    transition_to_nominate,
    transition_to_prompt,
    transition_to_question,
    transition_to_respond,
    transition_to_review,
    validate_player_alive,
)
from schemas.aliases import generate_aliases
from schemas.api_models import (
    AnswerSubmittedEvent,
    CastVoteRequest,
    JoinGameRequest,
    JoinGameResponse,
    NominatedEvent,
    NominateRequest,
    NominationCastEvent,
    PlayerJoinedEvent,
    QuestionSubmittedEvent,
    ResponseSubmittedEvent,
    StartGameRequest,
    SubmitAnswerRequest,
    SubmitQuestionRequest,
    SubmitResponseRequest,
    SynthesisReadyEvent,
    VerdictEvent,
    VoteCastEvent,
)
from schemas.constants import MISSING_ALIAS, NO_RESPONSE
from schemas.game_state import GamePhase, Player, PlayerRole, QuestionEntry, RoundType

router = APIRouter()

log = structlog.get_logger(__name__)


async def _start_phase_timer(game_id: str, phase: GamePhase) -> None:
    """Start the timer for the current phase. On expiry, transition to next phase."""
    settings = get_settings()
    tm = get_timer_manager()

    durations = {
        GamePhase.PROMPT: settings.prompt_duration,
        GamePhase.QUESTION: settings.question_duration,
        GamePhase.RESPOND: settings.respond_duration,
        GamePhase.REVIEW: settings.review_duration,
        GamePhase.NOMINATE: settings.nominate_duration,
        GamePhase.ELIMINATION: settings.elimination_duration,
    }
    duration = durations.get(phase)
    if not duration:
        return

    async def on_timer_expire():
        await _handle_phase_expiry(game_id, phase)

    tm.start_timer(game_id, duration, on_timer_expire)


async def _handle_phase_expiry(game_id: str, expired_phase: GamePhase) -> None:
    """Handle timer expiry — transition to next phase under lock."""
    cm = get_connection_manager()
    repo = get_game_repository()
    settings = get_settings()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session or session.state.phase != expired_phase:
            return

        state = session.state
        round_state = state.current_round

        if expired_phase == GamePhase.PROMPT:
            fill_missing_answers(state)

            if round_state and round_state.round_type == RoundType.INTERROGATION:
                # Interrogation: go to NOMINATE
                transition_to_nominate(state, settings.nominate_duration)
                await cm.broadcast(
                    game_id,
                    make_phase_changed_event(
                        state,
                        session.next_seq(),
                        answers=round_state.answers,
                        round_type=round_state.round_type,
                    ),
                )
                await _start_phase_timer(game_id, GamePhase.NOMINATE)
                await ai_on_phase_change(game_id, GamePhase.NOMINATE)
            else:
                # Probe: compute assignments and go to QUESTION
                if round_state:
                    round_state.assignments = assign_question_targets(state)
                transition_to_question(state, settings.question_duration)
                await cm.broadcast(
                    game_id,
                    make_phase_changed_event(
                        state,
                        session.next_seq(),
                        answers=round_state.answers if round_state else {},
                        round_type=round_state.round_type if round_state else RoundType.PROBE,
                        assignments=round_state.assignments if round_state else {},
                    ),
                )
                await _start_phase_timer(game_id, GamePhase.QUESTION)
                await ai_on_phase_change(game_id, GamePhase.QUESTION)

        elif expired_phase == GamePhase.NOMINATE:
            if round_state:
                nominated_id = resolve_nominations(state)
                round_state.nominated_id = nominated_id
                nominated_player = get_player_by_id(state, nominated_id)
                nominated_alias = nominated_player.alias if nominated_player else MISSING_ALIAS

                await cm.broadcast(
                    game_id,
                    NominatedEvent(
                        seq=session.next_seq(),
                        nominated_id=nominated_id,
                        nominated_alias=nominated_alias,
                    ),
                )

                transition_to_question(state, settings.question_duration)
                await cm.broadcast(
                    game_id,
                    make_phase_changed_event(
                        state,
                        session.next_seq(),
                        round_type=round_state.round_type,
                        nominated_id=nominated_id,
                    ),
                )
                await _start_phase_timer(game_id, GamePhase.QUESTION)
                await ai_on_phase_change(game_id, GamePhase.QUESTION)

        elif expired_phase == GamePhase.QUESTION:
            if round_state and round_state.round_type == RoundType.INTERROGATION:
                # Synthesize questions for the nominee
                await _synthesize_and_transition(game_id, session)
            else:
                # Probe: go to RESPOND
                transition_to_respond(state, settings.respond_duration)
                await cm.broadcast(
                    game_id,
                    make_phase_changed_event(
                        state,
                        session.next_seq(),
                        round_type=round_state.round_type if round_state else RoundType.PROBE,
                        questions=[q.model_dump() for q in round_state.questions]
                        if round_state
                        else [],
                    ),
                )
                await _start_phase_timer(game_id, GamePhase.RESPOND)
                await ai_on_phase_change(game_id, GamePhase.RESPOND)

        elif expired_phase == GamePhase.RESPOND:
            fill_missing_responses(state)

            transition_to_review(state, settings.review_duration)
            await cm.broadcast(
                game_id,
                make_phase_changed_event(
                    state,
                    session.next_seq(),
                    round_type=round_state.round_type if round_state else RoundType.PROBE,
                    questions=[q.model_dump() for q in round_state.questions]
                    if round_state
                    else [],
                    synthesis=round_state.synthesis if round_state else None,
                ),
            )
            await _start_phase_timer(game_id, GamePhase.REVIEW)
            await ai_on_phase_change(game_id, GamePhase.REVIEW)

        elif expired_phase == GamePhase.REVIEW:
            await _do_vote_resolution(game_id, session)

        elif expired_phase == GamePhase.ELIMINATION:
            await _after_elimination(game_id, session)


async def _synthesize_and_transition(game_id: str, session) -> None:
    """Synthesize questions (Interrogation) and transition to RESPOND."""
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state
    round_state = state.current_round

    synthesis = None
    if round_state and round_state.questions:
        try:
            from backend.llm.agents import synthesize_questions

            questions_text = [q.question for q in round_state.questions]
            target_player = get_player_by_id(state, round_state.nominated_id)
            target_alias = target_player.alias if target_player else MISSING_ALIAS
            target_answer = round_state.answers.get(round_state.nominated_id, "")
            synthesis = await synthesize_questions(
                questions_text,
                target_alias,
                target_answer,
                round_state.prompt_text,
            )
        except Exception:
            log.exception("synthesis_failed", game_id=game_id)
            # Fallback: numbered list
            questions_text = [q.question for q in round_state.questions]
            synthesis = "The group asks:\n" + "\n".join(
                f"{i + 1}. {q}" for i, q in enumerate(questions_text)
            )

    if round_state:
        round_state.synthesis = synthesis

    if synthesis:
        await cm.broadcast(
            game_id,
            SynthesisReadyEvent(
                seq=session.next_seq(),
                synthesis=synthesis,
            ),
        )

    transition_to_respond(state, settings.respond_duration)
    await cm.broadcast(
        game_id,
        make_phase_changed_event(
            state,
            session.next_seq(),
            round_type=round_state.round_type if round_state else RoundType.INTERROGATION,
            synthesis=synthesis,
            nominated_id=round_state.nominated_id if round_state else None,
        ),
    )
    await _start_phase_timer(game_id, GamePhase.RESPOND)
    await ai_on_phase_change(game_id, GamePhase.RESPOND)


async def _do_vote_resolution(game_id: str, session) -> None:
    """Resolve votes, generate verdict, show elimination."""
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state

    state, vote_results, elimination = resolve_votes(state, session.next_seq)
    await cm.broadcast(game_id, vote_results)

    # Generate verdict
    if elimination.eliminated_id and state.current_round:
        try:
            from backend.llm.agents import generate_verdict

            round_state = state.current_round
            verdict = await generate_verdict(
                alias=elimination.eliminated_alias or MISSING_ALIAS,
                was_human=elimination.was_human or False,
                prompt_text=round_state.prompt_text,
                answer=round_state.answers.get(elimination.eliminated_id, ""),
                vote_count=elimination.vote_count,
                round_number=round_state.round_number,
                max_rounds=state.max_rounds,
            )
            if verdict:
                round_state.verdict = verdict
                await cm.broadcast(
                    game_id,
                    VerdictEvent(
                        seq=session.next_seq(),
                        verdict=verdict,
                    ),
                )
        except Exception:
            log.exception("verdict_generation_failed", game_id=game_id)

    transition_to_elimination(state, settings.elimination_duration)
    await cm.broadcast(game_id, elimination)
    await _start_phase_timer(game_id, GamePhase.ELIMINATION)


async def _after_elimination(game_id: str, session) -> None:
    """After elimination reveal, check game over or start next round."""
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state

    winner = check_game_over(state)
    if winner:
        state.phase = GamePhase.GAME_OVER
        state.winner = winner
        state.phase_deadline = None
        event = make_game_over_event(state, winner, session.next_seq)
        await cm.broadcast(game_id, event)
        from backend.services.ai_scheduler import cleanup_game as ai_cleanup

        ai_cleanup(game_id)
        cm.cleanup_game(game_id)
        return

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
    await _start_phase_timer(game_id, GamePhase.PROMPT)
    await ai_on_phase_change(game_id, GamePhase.PROMPT)


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

    await _start_phase_timer(game_id, GamePhase.PROMPT)
    await ai_on_phase_change(game_id, GamePhase.PROMPT)

    return {"status": "started", "round": state.round_number}


@router.post("/{game_id}/answer")
async def submit_answer(game_id: str, req: SubmitAnswerRequest):
    """Submit an answer to the current prompt."""
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

        # Check if all answered — early transition
        if answer_count >= total_count:
            get_timer_manager().cancel_timer(game_id)

            fill_missing_answers(state)

            if round_state.round_type == RoundType.INTERROGATION:
                transition_to_nominate(state, settings.nominate_duration)
                await cm.broadcast(
                    game_id,
                    make_phase_changed_event(
                        state,
                        session.next_seq(),
                        answers=round_state.answers,
                        round_type=round_state.round_type,
                    ),
                )
                early_phase = GamePhase.NOMINATE
            else:
                round_state.assignments = assign_question_targets(state)
                transition_to_question(state, settings.question_duration)
                await cm.broadcast(
                    game_id,
                    make_phase_changed_event(
                        state,
                        session.next_seq(),
                        answers=round_state.answers,
                        round_type=round_state.round_type,
                        assignments=round_state.assignments,
                    ),
                )
                early_phase = GamePhase.QUESTION
        else:
            early_phase = None

    if early_phase:
        await _start_phase_timer(game_id, early_phase)
        await ai_on_phase_change(game_id, early_phase)

    return {"status": "ok"}


@router.post("/{game_id}/nominate")
async def nominate_player(game_id: str, req: NominateRequest):
    """Nominate a player for the hot seat (Interrogation only)."""
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
            nominated_id = resolve_nominations(state)
            round_state.nominated_id = nominated_id
            nominated_player = get_player_by_id(state, nominated_id)
            nominated_alias = nominated_player.alias if nominated_player else MISSING_ALIAS

            await cm.broadcast(
                game_id,
                NominatedEvent(
                    seq=session.next_seq(),
                    nominated_id=nominated_id,
                    nominated_alias=nominated_alias,
                ),
            )

            transition_to_question(state, settings.question_duration)
            await cm.broadcast(
                game_id,
                make_phase_changed_event(
                    state,
                    session.next_seq(),
                    round_type=round_state.round_type,
                    nominated_id=nominated_id,
                ),
            )
            early_transition = True
        else:
            early_transition = False

    if early_transition:
        await _start_phase_timer(game_id, GamePhase.QUESTION)
        await ai_on_phase_change(game_id, GamePhase.QUESTION)

    return {"status": "ok"}


@router.post("/{game_id}/question")
async def submit_question(game_id: str, req: SubmitQuestionRequest):
    """Submit a follow-up question during QUESTION phase."""
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
        if round_state.round_type == RoundType.INTERROGATION:
            # Hot-seated player cannot submit a question
            if req.player_id == round_state.nominated_id:
                raise HTTPException(
                    status_code=400, detail="Hot-seated player cannot submit questions"
                )
            target_id = round_state.nominated_id
        else:
            # Probe: target from assignments
            target_id = round_state.assignments.get(req.player_id)

        if not target_id:
            raise HTTPException(status_code=400, detail="No assignment found")

        target_player = get_player_by_id(state, target_id)
        target_alias = target_player.alias if target_player else MISSING_ALIAS

        entry = QuestionEntry(
            questioner_id=req.player_id,
            target_id=target_id,
            target_alias=target_alias,
            question=req.question.strip(),
            anonymous=round_state.round_type == RoundType.PROBE,
        )
        round_state.questions.append(entry)

        # Count expected questioners
        alive = get_alive_players(state)
        if round_state.round_type == RoundType.INTERROGATION:
            expected = len([p for p in alive if p.id != round_state.nominated_id])
        else:
            expected = len(alive)

        q_count = len(round_state.questions)

        await cm.broadcast(
            game_id,
            QuestionSubmittedEvent(
                seq=session.next_seq(),
                count=q_count,
                total=expected,
            ),
        )

        # Early-complete
        if q_count >= expected:
            get_timer_manager().cancel_timer(game_id)
            if round_state.round_type == RoundType.INTERROGATION:
                await _synthesize_and_transition(game_id, session)
                early_transition = False  # already handled
            else:
                transition_to_respond(state, settings.respond_duration)
                await cm.broadcast(
                    game_id,
                    make_phase_changed_event(
                        state,
                        session.next_seq(),
                        round_type=round_state.round_type,
                        questions=[q.model_dump() for q in round_state.questions],
                    ),
                )
                early_transition = True
        else:
            early_transition = False

    if early_transition:
        await _start_phase_timer(game_id, GamePhase.RESPOND)
        await ai_on_phase_change(game_id, GamePhase.RESPOND)

    return {"status": "ok"}


@router.post("/{game_id}/respond")
async def submit_response(game_id: str, req: SubmitResponseRequest):
    """Submit a response to a question during RESPOND phase."""
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
        if state.phase != GamePhase.RESPOND:
            raise HTTPException(status_code=400, detail="Not in respond phase")

        result = validate_player_alive(state, req.player_id)
        if isinstance(result, str):
            raise HTTPException(status_code=400, detail=result)

        round_state = state.current_round
        if not round_state:
            raise HTTPException(status_code=400, detail="No active round")

        if round_state.round_type == RoundType.INTERROGATION:
            # Only the nominated player can respond
            if req.player_id != round_state.nominated_id:
                raise HTTPException(
                    status_code=400, detail="Only the hot-seated player can respond"
                )
            # Find the question targeting them (synthesized — store as single entry)
            target_q = next(
                (
                    q
                    for q in round_state.questions
                    if q.target_id == req.player_id and q.response is None
                ),
                None,
            )
            if not target_q:
                # No question to respond to, or already responded
                raise HTTPException(
                    status_code=400, detail="No pending question or already responded"
                )
            target_q.response = req.response.strip()
        else:
            # Probe: find the question targeting this player
            target_q = next(
                (
                    q
                    for q in round_state.questions
                    if q.target_id == req.player_id and q.response is None
                ),
                None,
            )
            if not target_q:
                raise HTTPException(
                    status_code=400, detail="No pending question or already responded"
                )
            target_q.response = req.response.strip()

        player = get_player_by_id(state, req.player_id)
        player_alias = player.alias if player else MISSING_ALIAS

        # Count responses needed
        if round_state.round_type == RoundType.INTERROGATION:
            # Only one response needed (the nominee)
            responded_count = 1
            expected = 1
        else:
            # Probe: count players who have questions targeting them
            targets_with_questions = {q.target_id for q in round_state.questions}
            responded_count = sum(1 for q in round_state.questions if q.response is not None)
            expected = len(targets_with_questions)

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

        # Early-complete
        if responded_count >= expected:
            get_timer_manager().cancel_timer(game_id)
            fill_missing_responses(state)

            transition_to_review(state, settings.review_duration)
            await cm.broadcast(
                game_id,
                make_phase_changed_event(
                    state,
                    session.next_seq(),
                    round_type=round_state.round_type,
                    questions=[q.model_dump() for q in round_state.questions],
                    synthesis=round_state.synthesis,
                ),
            )
            early_transition = True
        else:
            early_transition = False

    if early_transition:
        await _start_phase_timer(game_id, GamePhase.REVIEW)
        await ai_on_phase_change(game_id, GamePhase.REVIEW)

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

        # NO early-complete for REVIEW — always runs full timer

    return {"status": "ok"}
