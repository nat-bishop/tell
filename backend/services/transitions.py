"""Phase transition sequences — shared by route handlers and AI scheduler."""

from __future__ import annotations

import datetime as dt
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
    get_next_round_type,
    get_phase_duration,
    get_player_by_id,
    make_game_over_event,
    make_phase_changed_event,
    resolve_nominations,
    resolve_votes,
    select_chain_next_word,
    select_round_types,
    transition_to_elimination,
    transition_to_nominate,
    transition_to_prompt,
    transition_to_question,
    transition_to_respond,
    transition_to_review,
    transition_to_task_prompt,
    transition_to_word_chain,
)
from schemas.aliases import generate_aliases
from schemas.api_models import (
    ChainSeedEvent,
    NominatedEvent,
    PlayerJoinedEvent,
    SynthesisReadyEvent,
    VerdictEvent,
)
from schemas.constants import MISSING_ALIAS
from schemas.game_state import ChainRound, GamePhase, Player, PlayerRole, RoundType
from schemas.word_chain import select_seed_word

log = structlog.get_logger(__name__)


def _make_event(state, session, settings, **extra):
    """Build a PhaseChangedEvent with phase_duration computed from settings."""
    rs = state.current_round
    pd = get_phase_duration(settings, state.phase, rs.round_type if rs else None)
    # Include writing_begins_at for reading period
    if rs and rs.writing_begins_at and "writing_begins_at" not in extra:
        extra["writing_begins_at"] = rs.writing_begins_at.isoformat()
    return make_phase_changed_event(state, session.next_seq(), phase_duration=pd, **extra)


async def start_phase_timer(
    game_id: str, phase: GamePhase, round_type: RoundType | None = None
) -> None:
    """Start the timer for the current phase. On expiry, transition to next phase."""
    settings = get_settings()
    tm = get_timer_manager()

    duration = get_phase_duration(settings, phase, round_type)
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

        elif expired_phase == GamePhase.CHAIN:
            # Safety timer expired — transition to review
            await do_chain_complete(game_id, session)


async def do_prompt_complete(game_id: str, session) -> None:
    """PROMPT complete → depends on round type:
    - TASK: straight to REVIEW
    - INTERROGATION: NOMINATE
    - PROBE: QUESTION

    Assumes caller holds the game lock and has called fill_missing_answers.
    """
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state
    round_state = state.current_round

    if round_state and round_state.round_type == RoundType.TASK:
        # Task rounds skip question/respond — go straight to review
        transition_to_review(state, settings.review_duration)
        await cm.broadcast(
            game_id,
            _make_event(
                state,
                session,
                settings,
                answers=round_state.answers,
                round_type=round_state.round_type,
            ),
        )
        next_phase = GamePhase.REVIEW
    elif round_state and round_state.round_type == RoundType.INTERROGATION:
        transition_to_nominate(state, settings.nominate_duration)
        await cm.broadcast(
            game_id,
            _make_event(
                state,
                session,
                settings,
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
            _make_event(
                state,
                session,
                settings,
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
        _make_event(
            state,
            session,
            settings,
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
            _make_event(
                state,
                session,
                settings,
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
            _make_event(
                state,
                session,
                settings,
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
        _make_event(
            state,
            session,
            settings,
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
    """ELIMINATION complete → next round or GAME_OVER.

    Branch on next round type:
    - TASK: select task prompt → PROMPT (25s)
    - INTERROGATION/PROBE: select prompt → PROMPT (45s)
    - WORD_CHAIN: select seed → CHAIN (64s) + start chain loop

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
        if settings.record_games:
            from backend.services.recorder import save_recording

            save_recording(game_id, state, cm.pop_recording(game_id))
        from backend.services.ai_scheduler import cleanup_game as ai_cleanup

        ai_cleanup(game_id)
        cm.cleanup_game(game_id)
        return

    next_round_type = get_next_round_type(state)

    if next_round_type == RoundType.TASK:
        total_duration = get_phase_duration(settings, GamePhase.PROMPT, RoundType.TASK) or 35
        transition_to_task_prompt(state, total_duration, settings.prompt_reading_duration)
        round_state = state.current_round
        await cm.broadcast(
            game_id,
            _make_event(
                state,
                session,
                settings,
                prompt_text=round_state.prompt_text if round_state else None,
                prompt_category=round_state.prompt_category if round_state else None,
                round_type=round_state.round_type if round_state else RoundType.TASK,
            ),
        )
        await start_phase_timer(game_id, GamePhase.PROMPT, RoundType.TASK)
        from backend.services.ai_scheduler import on_phase_change as ai_on_phase_change

        await ai_on_phase_change(game_id, GamePhase.PROMPT)

    elif next_round_type == RoundType.WORD_CHAIN:
        seed = select_seed_word()
        transition_to_word_chain(state, seed, settings.chain_duration)
        round_state = state.current_round
        await cm.broadcast(
            game_id,
            _make_event(
                state,
                session,
                settings,
                round_type=RoundType.WORD_CHAIN,
            ),
        )
        # Start safety timer for the full chain duration
        await start_phase_timer(game_id, GamePhase.CHAIN)
        # Start the sub-round loop
        await _start_chain_loop(game_id, session)

    else:
        # INTERROGATION or PROBE
        total_duration = get_phase_duration(settings, GamePhase.PROMPT) or 55
        transition_to_prompt(state, total_duration, settings.prompt_reading_duration)
        round_state = state.current_round
        await cm.broadcast(
            game_id,
            _make_event(
                state,
                session,
                settings,
                prompt_text=round_state.prompt_text if round_state else None,
                prompt_category=round_state.prompt_category if round_state else None,
                round_type=round_state.round_type if round_state else RoundType.PROBE,
            ),
        )
        await start_phase_timer(game_id, GamePhase.PROMPT)
        from backend.services.ai_scheduler import on_phase_change as ai_on_phase_change

        await ai_on_phase_change(game_id, GamePhase.PROMPT)


async def do_chain_complete(game_id: str, session) -> None:
    """CHAIN complete → REVIEW. Called by safety timer or after all sub-rounds.

    Assumes caller holds the game lock.
    """
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state

    transition_to_review(state, settings.review_duration)
    await cm.broadcast(
        game_id,
        _make_event(
            state,
            session,
            settings,
            round_type=RoundType.WORD_CHAIN,
        ),
    )

    await start_phase_timer(game_id, GamePhase.REVIEW)
    from backend.services.ai_scheduler import on_phase_change as ai_on_phase_change

    await ai_on_phase_change(game_id, GamePhase.REVIEW)


async def _start_chain_loop(game_id: str, session) -> None:
    """Launch the async sub-round loop for Word Chain. Runs as a background task."""
    import asyncio

    async def _chain_loop():
        try:
            cm = get_connection_manager()
            settings = get_settings()
            repo = get_game_repository()
            sub_duration = settings.chain_sub_round_duration
            num_sub_rounds = settings.chain_sub_rounds

            # Broadcast the first seed
            lock = cm.get_lock(game_id)
            async with lock:
                session = repo.get(game_id)
                if not session or session.state.phase != GamePhase.CHAIN:
                    return
                state = session.state
                rs = state.current_round
                if not rs or not rs.chain_rounds:
                    return

                sub_deadline = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=sub_duration)
                state.phase_deadline = sub_deadline

                await cm.broadcast(
                    game_id,
                    ChainSeedEvent(
                        seq=session.next_seq(),
                        word=rs.chain_rounds[0].seed,
                        round_index=0,
                        sub_deadline=sub_deadline.isoformat(),
                        chain_so_far=[rs.chain_rounds[0].seed],
                        phase_duration=sub_duration,
                    ),
                )

            # Schedule AI for first sub-round
            from backend.services.ai_scheduler import on_chain_sub_round

            await on_chain_sub_round(game_id, 0)

            for sub_round in range(num_sub_rounds):
                await asyncio.sleep(sub_duration)

                async with lock:
                    session = repo.get(game_id)
                    if not session or session.state.phase != GamePhase.CHAIN:
                        return
                    state = session.state
                    rs = state.current_round
                    if not rs:
                        return

                    # Collect responses from current sub-round
                    current_cr = rs.chain_rounds[rs.current_sub_round]
                    responses = current_cr.responses

                    # Pick next seed
                    if responses:
                        chosen, chosen_pid = select_chain_next_word(responses)
                        current_cr.chosen_word = chosen
                        current_cr.chosen_player_id = chosen_pid
                    else:
                        # No responses — pick a random word
                        from schemas.word_chain import get_fallback_association

                        chosen = get_fallback_association(current_cr.seed)
                        current_cr.chosen_word = chosen

                    # Check if this was the last sub-round
                    if sub_round >= num_sub_rounds - 1:
                        # Done — transition to review
                        get_timer_manager().cancel_timer(game_id)
                        await do_chain_complete(game_id, session)
                        return

                    # Set up next sub-round
                    next_idx = sub_round + 1
                    rs.current_sub_round = next_idx
                    rs.chain_rounds.append(ChainRound(seed=chosen))

                    sub_deadline = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=sub_duration)
                    state.phase_deadline = sub_deadline

                    chain_so_far = [cr.seed for cr in rs.chain_rounds]

                    await cm.broadcast(
                        game_id,
                        ChainSeedEvent(
                            seq=session.next_seq(),
                            word=chosen,
                            round_index=next_idx,
                            sub_deadline=sub_deadline.isoformat(),
                            chain_so_far=chain_so_far,
                            phase_duration=sub_duration,
                        ),
                    )

                # Schedule AI for this sub-round
                await on_chain_sub_round(game_id, next_idx)

        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("chain_loop_error", game_id=game_id)

    task = asyncio.create_task(_chain_loop())
    from backend.services.ai_scheduler import register_task

    register_task(game_id, task)


async def initialize_and_start_game(game_id: str, ai_count: int) -> None:
    """Start a game — spawn AI, assign personalities, transition to first round.

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

        # Transition to first round based on round type
        first_round_type = state.round_types[0] if state.round_types else RoundType.TASK
        reading = settings.prompt_reading_duration
        if first_round_type == RoundType.TASK:
            total = get_phase_duration(settings, GamePhase.PROMPT, RoundType.TASK) or 35
            transition_to_task_prompt(state, total, reading)
        else:
            total = get_phase_duration(settings, GamePhase.PROMPT) or 55
            transition_to_prompt(state, total, reading)

        round_state = state.current_round
        pd = get_phase_duration(
            settings, state.phase, round_state.round_type if round_state else None
        )
        writing_begins_at = (
            round_state.writing_begins_at.isoformat()
            if round_state and round_state.writing_begins_at
            else None
        )
        await cm.broadcast(
            game_id,
            make_phase_changed_event(
                state,
                session.next_seq(),
                phase_duration=pd,
                prompt_text=round_state.prompt_text if round_state else None,
                prompt_category=round_state.prompt_category if round_state else None,
                round_type=round_state.round_type if round_state else RoundType.TASK,
                writing_begins_at=writing_begins_at,
            ),
        )

        # Capture for logging after lock release
        player_count = len(state.players)
        max_rounds = state.max_rounds

    await start_phase_timer(
        game_id, GamePhase.PROMPT, state.round_types[0] if state.round_types else None
    )
    await ai_on_phase_change(game_id, GamePhase.PROMPT)

    log.info(
        "game_started",
        game_id=game_id,
        player_count=player_count,
        ai_count=ai_count,
        max_rounds=max_rounds,
    )
