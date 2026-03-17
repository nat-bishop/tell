"""Phase transition sequences — shared by route handlers and AI scheduler."""

from __future__ import annotations

import uuid

import structlog

from backend.api.deps import (
    get_connection_manager,
    get_game_repository,
    get_settings,
    get_timer_manager,
)
from backend.services.game_logic import (
    assign_question_targets,
    check_game_over,
    fill_missing_answers,
    fill_missing_responses,
    get_player_by_id,
    make_game_over_event,
    make_phase_changed_event,
    resolve_nominations,
    resolve_votes,
    select_round_types,
    transition_to_elimination,
    transition_to_nominate,
    transition_to_prompt,
    transition_to_question,
    transition_to_respond,
    transition_to_review,
)
from schemas.aliases import generate_aliases
from schemas.api_models import (
    NominatedEvent,
    PlayerJoinedEvent,
    SynthesisReadyEvent,
    VerdictEvent,
)
from schemas.constants import MISSING_ALIAS
from schemas.game_state import GamePhase, Player, PlayerRole, RoundType

log = structlog.get_logger(__name__)


async def start_phase_timer(game_id: str, phase: GamePhase) -> None:
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
        await handle_phase_expiry(game_id, phase)

    tm.start_timer(game_id, duration, on_timer_expire)


async def handle_phase_expiry(game_id: str, expired_phase: GamePhase) -> None:
    """Handle timer expiry — transition to next phase under lock."""
    cm = get_connection_manager()
    repo = get_game_repository()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session or session.state.phase != expired_phase:
            return

        log.info("phase_expired", phase=expired_phase.value)

        if expired_phase == GamePhase.PROMPT:
            fill_missing_answers(session.state)
            await do_prompt_complete(game_id, session)

        elif expired_phase == GamePhase.NOMINATE:
            await do_nominate_complete(game_id, session)

        elif expired_phase == GamePhase.QUESTION:
            await do_question_complete(game_id, session)

        elif expired_phase == GamePhase.RESPOND:
            fill_missing_responses(session.state)
            await do_respond_complete(game_id, session)

        elif expired_phase == GamePhase.REVIEW:
            await do_vote_resolution(game_id, session)

        elif expired_phase == GamePhase.ELIMINATION:
            await do_after_elimination(game_id, session)


async def do_prompt_complete(game_id: str, session) -> None:
    """PROMPT complete → NOMINATE (interrogation) or QUESTION (probe).

    Assumes caller holds the game lock and has called fill_missing_answers.
    """
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state
    round_state = state.current_round

    if round_state and round_state.round_type == RoundType.INTERROGATION:
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
        next_phase = GamePhase.NOMINATE
    else:
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
        next_phase = GamePhase.QUESTION

    await start_phase_timer(game_id, next_phase)
    from backend.services.ai_scheduler import on_phase_change as ai_on_phase_change

    await ai_on_phase_change(game_id, next_phase)


async def do_nominate_complete(game_id: str, session) -> None:
    """NOMINATE complete → resolve nominations → QUESTION.

    Assumes caller holds the game lock.
    """
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state
    round_state = state.current_round

    if not round_state:
        return

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

    await start_phase_timer(game_id, GamePhase.QUESTION)
    from backend.services.ai_scheduler import on_phase_change as ai_on_phase_change

    await ai_on_phase_change(game_id, GamePhase.QUESTION)


async def do_question_complete(game_id: str, session) -> None:
    """QUESTION complete → RESPOND (with optional synthesis for interrogation).

    Assumes caller holds the game lock.
    """
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state
    round_state = state.current_round

    if round_state and round_state.round_type == RoundType.INTERROGATION:
        # Synthesize questions for the nominee
        synthesis = None
        if round_state.questions:
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
                questions_text = [q.question for q in round_state.questions]
                synthesis = "The group asks:\n" + "\n".join(
                    f"{i + 1}. {q}" for i, q in enumerate(questions_text)
                )

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
                round_type=round_state.round_type,
                synthesis=synthesis,
                nominated_id=round_state.nominated_id,
            ),
        )
    else:
        # Probe: go directly to RESPOND
        transition_to_respond(state, settings.respond_duration)
        await cm.broadcast(
            game_id,
            make_phase_changed_event(
                state,
                session.next_seq(),
                round_type=round_state.round_type if round_state else RoundType.PROBE,
                questions=[q.model_dump() for q in round_state.questions] if round_state else [],
            ),
        )

    await start_phase_timer(game_id, GamePhase.RESPOND)
    from backend.services.ai_scheduler import on_phase_change as ai_on_phase_change

    await ai_on_phase_change(game_id, GamePhase.RESPOND)


async def do_respond_complete(game_id: str, session) -> None:
    """RESPOND complete → REVIEW.

    Assumes caller holds the game lock and has called fill_missing_responses.
    """
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state
    round_state = state.current_round

    transition_to_review(state, settings.review_duration)
    await cm.broadcast(
        game_id,
        make_phase_changed_event(
            state,
            session.next_seq(),
            round_type=round_state.round_type if round_state else RoundType.PROBE,
            questions=[q.model_dump() for q in round_state.questions] if round_state else [],
            synthesis=round_state.synthesis if round_state else None,
        ),
    )

    await start_phase_timer(game_id, GamePhase.REVIEW)
    from backend.services.ai_scheduler import on_phase_change as ai_on_phase_change

    await ai_on_phase_change(game_id, GamePhase.REVIEW)


async def do_vote_resolution(game_id: str, session) -> None:
    """REVIEW complete → resolve votes → generate verdict → ELIMINATION.

    Assumes caller holds the game lock.
    """
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state

    state, vote_results, elimination = resolve_votes(state, session.next_seq)
    await cm.broadcast(game_id, vote_results)
    log.info(
        "vote_resolved",
        eliminated_alias=elimination.eliminated_alias,
        was_human=elimination.was_human,
    )

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
    await start_phase_timer(game_id, GamePhase.ELIMINATION)


async def do_after_elimination(game_id: str, session) -> None:
    """ELIMINATION complete → next round (PROMPT) or GAME_OVER.

    Assumes caller holds the game lock.
    """
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state

    winner = check_game_over(state)
    if winner:
        log.info("game_over", winner=winner)
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

    await start_phase_timer(game_id, GamePhase.PROMPT)
    from backend.services.ai_scheduler import on_phase_change as ai_on_phase_change

    await ai_on_phase_change(game_id, GamePhase.PROMPT)


async def initialize_and_start_game(game_id: str, ai_count: int) -> None:
    """Start a game — spawn AI, assign personalities, transition to PROMPT.

    Reusable by both the host-triggered start and matchmaking auto-start.
    Caller must ensure the game exists and is in LOBBY phase.
    """
    from backend.services.ai_scheduler import assign_personalities
    from backend.services.ai_scheduler import on_phase_change as ai_on_phase_change

    cm = get_connection_manager()
    settings = get_settings()
    repo = get_game_repository()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session:
            return
        state = session.state

        # Spawn AI players
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
        human_count = len([p for p in state.players if p.role == PlayerRole.HUMAN])
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

        # Capture for logging after lock release
        player_count = len(state.players)
        max_rounds = state.max_rounds

    await start_phase_timer(game_id, GamePhase.PROMPT)
    await ai_on_phase_change(game_id, GamePhase.PROMPT)

    log.info(
        "game_started",
        game_id=game_id,
        player_count=player_count,
        ai_count=ai_count,
        max_rounds=max_rounds,
    )
