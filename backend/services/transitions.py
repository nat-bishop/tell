"""Phase transition sequences — shared by route handlers and AI scheduler."""

from __future__ import annotations

import asyncio
import uuid

import structlog

from backend.api.deps import (
    get_connection_manager,
    get_game_repository,
    get_settings,
    get_timer_manager,
)
from backend.minigames import get_handler
from backend.services.game_logic import (
    _transition_to_phase,
    check_game_over,
    fill_missing_answers,
    get_interstitial_hold,
    get_next_round_type,
    get_phase_duration,
    make_game_over_event,
    make_phase_changed_event,
    tally_gallery_votes,
)
from schemas.aliases import generate_aliases
from schemas.api_models import (
    FinalRevealEvent,
    NarrationEvent,
    PlayerJoinedEvent,
    RoundResultsEvent,
)
from schemas.game_state import (
    GamePhase,
    NarratorEntry,
    Player,
    PlayerRole,
    RoundType,
)

log = structlog.get_logger(__name__)


def _build_narrator_context(state) -> str:
    """Build a context string for the narrator from game state."""
    parts: list[str] = []
    n_players = len(state.players)
    rnd = state.round_number
    parts.append(f"Game: {n_players} players, round {rnd} of {state.total_rounds}.")

    # Score context
    score_parts = [f"{p.alias}: {p.score}" for p in state.players]
    parts.append(f"Scores: {', '.join(score_parts)}.")

    rs = state.current_round
    if rs:
        alias_map = {p.id: p.alias for p in state.players}
        if rs.prompt_text:
            parts.append(f'Prompt: "{rs.prompt_text}"')
        if rs.answers:
            for pid, ans in rs.answers.items():
                alias = alias_map.get(pid, pid)
                parts.append(f'  {alias} answered: "{ans}"')
        # Vote results context
        if rs.gallery_votes:
            vote_counts = tally_gallery_votes(state)
            detected = [
                (alias_map.get(pid, pid), cnt) for pid, cnt in vote_counts.items() if cnt > 0
            ]
            if detected:
                parts.append("Votes received: " + ", ".join(f"{a}: {c}" for a, c in detected))
    return "\n".join(parts)


async def _fire_narration(game_id: str, trigger: str, extra_context: str = "") -> None:
    """Fire a narration call as a background task. Non-blocking, never fails the game flow."""

    async def _do_narrate():
        try:
            from backend.llm.agents import generate_narration
            from backend.services.ai_scheduler import get_narrator_history, set_narrator_history

            cm = get_connection_manager()
            repo = get_game_repository()
            lock = cm.get_lock(game_id)

            # Build context + read history under lock
            async with lock:
                session = repo.get(game_id)
                if not session:
                    return
                context = _build_narrator_context(session.state)
                if extra_context:
                    context += f"\n\nTrigger: {trigger}. {extra_context}"
                else:
                    context += f"\n\nTrigger: {trigger}."
                history = get_narrator_history(game_id)

            # LLM call outside the lock
            text, updated_history = await generate_narration(
                trigger, context, game_id=game_id, message_history=history
            )
            if not text:
                return

            # Write result under lock
            async with lock:
                session = repo.get(game_id)
                if not session:
                    return
                set_narrator_history(game_id, updated_history)
                ctx = session.state.narrator_context
                ctx.append(
                    NarratorEntry(
                        trigger=trigger,
                        text=text,
                        round_number=session.state.round_number,
                    )
                )
                # Keep only the last 5 entries for frontend display
                if len(ctx) > 5:
                    session.state.narrator_context = ctx[-5:]
                await cm.broadcast(
                    game_id,
                    NarrationEvent(
                        seq=session.next_seq(),
                        text=text,
                        trigger=trigger,
                    ),
                )
                log.info("narration_sent", trigger=trigger, text_len=len(text), game_id=game_id)
        except Exception:
            log.exception("narration_failed", trigger=trigger, game_id=game_id)

    task = asyncio.create_task(_do_narrate())
    task.add_done_callback(
        lambda t: t.result() if not t.cancelled() and not t.exception() else None
    )


async def _notify_ai(game_id: str, phase: GamePhase) -> None:
    """Notify the AI scheduler of a phase change (runtime import to avoid circular dep)."""
    from backend.services.ai_scheduler import on_phase_change

    await on_phase_change(game_id, phase)


def _make_event(state, session, settings, **extra):
    """Build a PhaseChangedEvent with phase_duration computed from settings."""
    rs = state.current_round
    pd = get_phase_duration(settings, state.phase, rs.round_type if rs else None)
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
    # Interstitial hold is already baked into phase_deadline by transition functions,
    # so the timer must include it too to stay in sync with the deadline.
    duration += get_interstitial_hold(phase, round_type)

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

        elif expired_phase == GamePhase.ACTIVE:
            await do_active_complete(game_id, session)

        elif expired_phase == GamePhase.RESULTS:
            await do_results_complete(game_id, session)


async def do_prompt_complete(game_id: str, session) -> None:
    """PROMPT complete → transition to ACTIVE phase.

    Assumes caller holds the game lock and has called fill_missing_answers.
    """
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state
    round_state = state.current_round

    assert round_state, "No active round in PROMPT phase"
    round_type = round_state.round_type
    handler = get_handler(round_type)

    # Transition to ACTIVE
    _transition_to_phase(state, GamePhase.ACTIVE, handler.get_active_duration(settings), round_type)
    extras = handler.active_event_extras(state)
    await cm.broadcast(
        game_id,
        _make_event(
            state,
            session,
            settings,
            round_type=round_type,
            **extras,
        ),
    )
    await start_phase_timer(game_id, GamePhase.ACTIVE, round_type)
    await handler.on_active_start(game_id)

    # Fire narrator: post-submissions
    await _fire_narration(
        game_id,
        "post_submissions",
        "All answers are in. Comment briefly on what you notice.",
    )


async def do_active_complete(game_id: str, session) -> None:
    """ACTIVE complete → score round via handler → RESULTS or next round.

    Assumes caller holds the game lock.
    """
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state
    rs = state.current_round
    if not rs:
        return

    round_type = rs.round_type
    handler = get_handler(round_type)
    payload, score_deltas = handler.build_results(state)

    # Apply score deltas
    for p in state.players:
        p.score += score_deltas.get(p.id, 0)
    scores = {p.id: p.score for p in state.players}

    await cm.broadcast(
        game_id,
        RoundResultsEvent(
            seq=session.next_seq(),
            round_type=round_type,
            payload=payload,
            scores=scores,
        ),
    )
    log.info("round_results", round_type=round_type, scores=scores)

    if handler.meta.has_results:
        _transition_to_phase(
            state, GamePhase.RESULTS, handler.get_results_duration(settings), round_type
        )
        await cm.broadcast(
            game_id,
            _make_event(state, session, settings, round_type=round_type),
        )
        await start_phase_timer(game_id, GamePhase.RESULTS, round_type)
    else:
        # Skip results phase
        result = check_game_over(state)
        if result:
            winner, winner_ids = result
            await _do_game_over(game_id, session, state, winner, winner_ids)
            return
        await _start_next_round(game_id, session)

    # Fire narrator: between rounds
    await _fire_narration(
        game_id,
        "between_rounds",
        "A round just ended. Comment on the state of play — scores, standout moments.",
    )


async def do_results_complete(game_id: str, session) -> None:
    """RESULTS done → check game over or next round.

    Assumes caller holds the game lock.
    """
    state = session.state

    result = check_game_over(state)
    if result:
        winner, winner_ids = result
        await _do_game_over(game_id, session, state, winner, winner_ids)
        return

    await _start_next_round(game_id, session)


async def _do_game_over(game_id: str, session, state, winner, winner_ids) -> None:
    """Shared game-over flow: narration → FinalRevealEvent → GameOverEvent.

    Assumes caller holds the game lock.
    """
    cm = get_connection_manager()
    settings = get_settings()

    log.info("game_over", winner=winner, winner_ids=winner_ids)

    # Fire narrator: game over wrap-up (non-blocking background task)
    top_aliases = [p.alias for p in state.players if p.id in winner_ids]
    narr_msg = (
        f"The game is over. Winners: {', '.join(top_aliases)}. "
        "Write a knockout wrap-up — "
        "the story of this game in 1-2 sentences. Reference specific moments."
    )
    await _fire_narration(game_id, "game_over", narr_msg)

    # Brief wait for narration to potentially resolve
    await asyncio.sleep(1.5)

    # Grab latest narrator text (if narration resolved in time)
    narrator_text = None
    if state.narrator_context:
        last_entry = state.narrator_context[-1]
        if last_entry.trigger == "game_over":
            narrator_text = last_entry.text

    # Broadcast FinalRevealEvent with all players revealed
    final_players = [
        {
            "id": p.id,
            "alias": p.alias,
            "role": p.role.value,
            "score": p.score,
        }
        for p in state.players
    ]
    await cm.broadcast(
        game_id,
        FinalRevealEvent(
            seq=session.next_seq(),
            players=final_players,
            winner_ids=winner_ids,
            narrator_text=narrator_text,
        ),
    )

    # Set game over state
    state.phase = GamePhase.GAME_OVER
    state.winner = winner
    state.winner_ids = winner_ids
    state.phase_deadline = None
    event = make_game_over_event(state, winner, winner_ids, session.next_seq)
    await cm.broadcast(game_id, event)

    if settings.record_games:
        from backend.services.recorder import save_recording

        save_recording(game_id, state, cm.pop_recording(game_id))
    from backend.services.ai_scheduler import cleanup_game as ai_cleanup

    ai_cleanup(game_id)
    cm.cleanup_game(game_id)


async def _start_next_round(game_id: str, session) -> None:
    """Start the next round using the handler registry.

    Assumes caller holds the game lock.
    """
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state

    next_round_type = get_next_round_type(state)
    handler = get_handler(next_round_type)

    handler.setup_round(state, settings)
    state.round_types.append(next_round_type)

    if handler.meta.has_prompt:
        _transition_to_phase(state, GamePhase.PROMPT, settings.prompt_duration)
        round_state = state.current_round
        await cm.broadcast(
            game_id,
            _make_event(
                state,
                session,
                settings,
                prompt_text=round_state.prompt_text if round_state else None,
                prompt_category=round_state.prompt_category if round_state else None,
                round_type=next_round_type,
            ),
        )
        await start_phase_timer(game_id, GamePhase.PROMPT)
        await _notify_ai(game_id, GamePhase.PROMPT)
    else:
        _transition_to_phase(
            state, GamePhase.ACTIVE, handler.get_active_duration(settings), next_round_type
        )
        await cm.broadcast(
            game_id,
            _make_event(state, session, settings, round_type=next_round_type),
        )
        await start_phase_timer(game_id, GamePhase.ACTIVE, next_round_type)
        await handler.on_active_start(game_id)


async def initialize_and_start_game(game_id: str, ai_count: int) -> None:
    """Start a game — spawn AI, assign personalities, transition to first round.

    Reusable by both the host-triggered start and matchmaking auto-start.
    Caller must ensure the game exists and is in LOBBY phase.
    """
    from backend.services.ai_scheduler import assign_personalities

    cm = get_connection_manager()
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

        # Capture for logging after lock release
        player_count = len(state.players)

    # Delegate first round setup to _start_next_round (handles all round types)
    async with lock:
        session = repo.get(game_id)
        if not session:
            return
        await _start_next_round(game_id, session)

    log.info(
        "game_started",
        game_id=game_id,
        player_count=player_count,
        ai_count=ai_count,
    )

    # Fire narrator: game start
    human_count = player_count - ai_count
    await _fire_narration(
        game_id,
        "game_start",
        f"{player_count} players assembled. {human_count} humans, {ai_count} AI. "
        "The humans hide among machines. Each trying to pass as AI.",
    )
