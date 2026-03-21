"""Step-based transition system — generic step runner for all minigames."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict

import structlog

from backend.api.deps import (
    get_connection_manager,
    get_game_repository,
    get_settings,
    get_timer_manager,
)
from backend.minigames import get_handler
from backend.services.game_logic import (
    check_game_over,
    get_next_round_type,
    make_game_over_event,
    tally_gallery_votes,
    transition_to_step,
)
from backend.services.game_repository import TellGameSession
from schemas.aliases import generate_aliases
from schemas.api_models import (
    FinalRevealEvent,
    NarrationEvent,
    PlayerJoinedEvent,
    RoundResultsEvent,
    StepChangedEvent,
)
from schemas.game_state import (
    GamePhase,
    NarratorEntry,
    Player,
    PlayerRole,
    RoundType,
    TellGameState,
)

log = structlog.get_logger(__name__)

# prevent garbage collection of fire-and-forget narrator tasks
_background_tasks: set[asyncio.Task] = set()


def _role_label(role: PlayerRole) -> str:
    """Human-readable role for narrator context."""
    return "human" if role == PlayerRole.HUMAN else "AI"


def _detect_drama(players: list) -> str | None:
    """Detect score drama signals (tied, close race, runaway leader)."""
    sorted_players = sorted(players, key=lambda p: p.score, reverse=True)
    if len(sorted_players) < 2:
        return None
    gap = sorted_players[0].score - sorted_players[1].score
    if gap == 0:
        return f"Drama: tied at the top ({sorted_players[0].alias}, {sorted_players[1].alias})."
    if gap <= 100:
        return f"Drama: close race — {sorted_players[0].alias} leads by {gap}."
    if gap >= 300:
        return f"Drama: {sorted_players[0].alias} running away with it (+{gap})."
    return None


def _build_narrator_context(state: TellGameState) -> str:
    """Build a context string for the narrator from game state."""
    parts: list[str] = []
    n_players = len(state.players)
    rnd = state.round_number

    # Round progression
    progression = ""
    if rnd == 1:
        progression = " Opening round."
    elif rnd == state.total_rounds:
        progression = " Final round."
    parts.append(f"Round {rnd} of {state.total_rounds}.{progression} {n_players} players.")

    # Players with scores (narrator does NOT know roles during gameplay)
    score_parts = [f"{p.alias}: {p.score}" for p in state.players]
    parts.append(f"Players: {', '.join(score_parts)}.")

    drama = _detect_drama(state.players)
    if drama:
        parts.append(drama)

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
            undetected = [alias_map.get(pid, pid) for pid, cnt in vote_counts.items() if cnt == 0]
            if detected:
                parts.append("Votes received: " + ", ".join(f"{a}: {c}" for a, c in detected))
            if undetected:
                parts.append("Went undetected: " + ", ".join(undetected))
    return "\n".join(parts)


async def _fire_narration(game_id: str, trigger: str, extra_context: str = "") -> None:
    """Fire a narration call as a background task. Non-blocking, never fails the game flow."""

    async def _do_narrate():
        try:
            from backend.llm.agents import generate_narration

            cm = get_connection_manager()
            repo = get_game_repository()
            lock = cm.get_lock(game_id)

            # Build context under game lock
            async with lock:
                session = repo.get(game_id)
                if not session:
                    return
                context = _build_narrator_context(session.state)
                if extra_context:
                    context += f"\n\nTrigger: {trigger}. {extra_context}"
                else:
                    context += f"\n\nTrigger: {trigger}."

            # LLM call outside the game lock (narrator serializes via its own lock)
            text = await generate_narration(game_id, trigger, context)
            if not text:
                return

            # Write result + broadcast under game lock
            async with lock:
                session = repo.get(game_id)
                if not session:
                    return
                ctx = session.state.narrator_context
                ctx.append(
                    NarratorEntry(
                        trigger=trigger,
                        text=text,
                        round_number=session.state.round_number,
                    )
                )
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
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def _make_step_event(
    state: TellGameState, session: TellGameSession, step_index: int
) -> StepChangedEvent:
    """Build a StepChangedEvent from current state."""
    step = state.round_step_defs[step_index]
    rs = state.current_round
    handler = get_handler(rs.round_type) if rs else None
    payload = handler.step_event_extras(state, step_index) if handler else {}

    return StepChangedEvent(
        seq=session.next_seq(),
        phase=state.phase.value,
        step_name=step["name"],
        step_index=step_index,
        component=step["component"],
        round_number=state.round_number,
        round_type=rs.round_type if rs else "",
        deadline=state.phase_deadline.isoformat() if state.phase_deadline else None,
        duration=step["duration"],
        payload=payload,
    )


async def _advance_step(game_id: str, session: TellGameSession, step_index: int) -> None:
    """Advance to a specific step: set state, broadcast, start timer, notify handler.

    Assumes caller holds the game lock.
    """
    cm = get_connection_manager()
    state = session.state

    transition_to_step(state, step_index)
    event = _make_step_event(state, session, step_index)
    await cm.broadcast(game_id, event)

    step = state.round_step_defs[step_index]
    duration = step["duration"]

    # Start timer
    async def on_timer_expire():
        await _handle_step_expiry(game_id)

    get_timer_manager().start_timer(game_id, duration, on_timer_expire)

    # Notify handler
    rs = state.current_round
    if rs and not step.get("is_results"):
        handler = get_handler(rs.round_type)
        await handler.on_step_start(game_id, state, step_index)


async def _handle_step_expiry(game_id: str) -> None:
    """Handle timer expiry — advance to next step, score, or end game.

    Acquires lock. For finalize_round (Signal), releases lock during I/O.
    """
    cm = get_connection_manager()
    repo = get_game_repository()
    lock = cm.get_lock(game_id)

    need_finalize = False
    handler = None
    step_index = -1

    async with lock:
        session = repo.get(game_id)
        if not session:
            return
        state = session.state
        if state.phase != GamePhase.ROUND:
            return

        step_index = state.current_step_index
        steps = state.round_step_defs
        if step_index >= len(steps):
            return

        current_step = steps[step_index]
        rs = state.current_round
        if not rs:
            return

        handler = get_handler(rs.round_type)
        log.info("step_expired", step_name=current_step["name"], step_index=step_index)

        # Cleanup current step
        await handler.on_step_end(game_id, state, step_index)

        if current_step.get("is_results"):
            # Results step done — game over or next round
            result = check_game_over(state)
            if result:
                winner, winner_ids = result
                await _do_game_over(game_id, session, state, winner, winner_ids)
                return

            # Fire narration before next round
            await _fire_narration(
                game_id,
                "between_rounds",
                "Round complete. Comment on performance. One line.",
            )
            await _start_next_round(game_id, session)
            return

        next_index = step_index + 1
        if next_index >= len(steps):
            return

        next_step = steps[next_index]
        if next_step.get("is_results"):
            # Next step is results — need to finalize, score, then advance
            need_finalize = True
        else:
            # Normal advance
            await _advance_step(game_id, session, next_index)
            return

    # Outside lock: finalize_round (Signal LLM judging)
    if need_finalize and handler:
        await handler.finalize_round(game_id)

        async with lock:
            session = repo.get(game_id)
            if not session:
                return
            state = session.state
            if state.phase != GamePhase.ROUND:
                return
            # Verify still on expected step (no race)
            if state.current_step_index != step_index:
                return

            rs = state.current_round
            if not rs:
                return

            await _score_and_advance_to_results(game_id, session, handler, next_index)


async def _score_and_advance_to_results(
    game_id: str, session: TellGameSession, handler, next_index: int
) -> None:
    """Build results, apply scores, broadcast, fire narration, advance to results step.

    Assumes caller holds the game lock.
    """
    cm = get_connection_manager()
    state = session.state
    rs = state.current_round
    if not rs:
        return

    payload, score_deltas = handler.build_results(state)

    # Apply score deltas
    for p in state.players:
        p.score += score_deltas.get(p.id, 0)
    scores = {p.id: p.score for p in state.players}

    await cm.broadcast(
        game_id,
        RoundResultsEvent(
            seq=session.next_seq(),
            round_type=rs.round_type,
            payload=payload,
            scores=scores,
        ),
    )
    log.info("round_results", round_type=rs.round_type, scores=scores)

    # Fire narration for results
    round_type = rs.round_type
    if round_type == RoundType.TASK:
        alias_map = {p.id: p.alias for p in state.players}
        vote_counts = payload.get("vote_counts", {})
        most_voted = max(vote_counts, key=vote_counts.get, default=None)
        most_alias = alias_map.get(most_voted, "someone") if most_voted else "someone"
        most_count = vote_counts.get(most_voted, 0) if most_voted else 0
        zero_aliases = [alias_map.get(pid, pid) for pid, c in vote_counts.items() if c == 0]
        zero_str = ", ".join(zero_aliases) if zero_aliases else "no one"
        await _fire_narration(
            game_id,
            "vote_results",
            f"{most_alias} drew {most_count} votes. "
            f"{zero_str} went undetected. React to the vote results.",
        )
    else:
        await _fire_narration(
            game_id,
            "between_rounds",
            "Round scoring complete. Comment on who performed well or stumbled. One line.",
        )

    await _advance_step(game_id, session, next_index)


async def try_advance_step(game_id: str, session: TellGameSession) -> None:
    """Check if current step can end early. Called under lock by routes/AI tasks."""
    state = session.state
    if state.phase != GamePhase.ROUND:
        return

    step_index = state.current_step_index
    steps = state.round_step_defs
    if step_index >= len(steps):
        return

    rs = state.current_round
    if not rs:
        return

    handler = get_handler(rs.round_type)
    if not handler.check_early_complete(state, step_index):
        return

    # Early completion — cancel timer and process
    get_timer_manager().cancel_timer(game_id)

    log.info("step_early_complete", step_name=steps[step_index]["name"], step_index=step_index)

    await handler.on_step_end(game_id, state, step_index)

    current_step = steps[step_index]
    if current_step.get("is_results"):
        result = check_game_over(state)
        if result:
            winner, winner_ids = result
            await _do_game_over(game_id, session, state, winner, winner_ids)
            return
        await _start_next_round(game_id, session)
        return

    next_index = step_index + 1
    if next_index >= len(steps):
        return

    next_step = steps[next_index]
    if next_step.get("is_results"):
        # Score and advance to results — finalize is no-op for early-complete handlers
        await _score_and_advance_to_results(game_id, session, handler, next_index)
    else:
        await _advance_step(game_id, session, next_index)


async def _do_game_over(
    game_id: str,
    session: TellGameSession,
    state: TellGameState,
    winner: str,
    winner_ids: list[str],
) -> None:
    """Shared game-over flow: narration → FinalRevealEvent → GameOverEvent.

    Assumes caller holds the game lock.
    """
    cm = get_connection_manager()
    settings = get_settings()

    log.info("game_over", winner=winner, winner_ids=winner_ids)

    # Fire narrator: game over wrap-up (non-blocking background task).
    top_players = [p for p in state.players if p.id in winner_ids]
    top_info = ", ".join(f"{p.alias} ({_role_label(p.role)}, score {p.score})" for p in top_players)
    humans = [p for p in state.players if p.role == PlayerRole.HUMAN]
    human_summary = "; ".join(f"{p.alias}: {p.score}" for p in humans)
    narr_msg = (
        f"Winner: {top_info}. "
        f"Human performance: {human_summary}. "
        "Deliver a final verdict on this experiment."
    )
    await _fire_narration(game_id, "game_over", narr_msg)

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


async def _start_next_round(game_id: str, session: TellGameSession) -> None:
    """Start the next round using the handler registry.

    Assumes caller holds the game lock.
    """
    settings = get_settings()
    state = session.state

    next_round_type = get_next_round_type(state)
    handler = get_handler(next_round_type)

    handler.setup_round(state, settings)
    state.round_types.append(next_round_type)
    state.phase = GamePhase.ROUND

    # Store step defs for this round
    step_defs = handler.get_steps(state, settings)
    state.round_step_defs = [asdict(s) for s in step_defs]

    # Advance to first step
    await _advance_step(game_id, session, 0)

    # Fire narrator: round preview (round 2+)
    if state.round_number > 1:
        rnd = state.round_number
        total = state.total_rounds
        rt_label = "Task round" if next_round_type == RoundType.TASK else "Quick Draw"
        final = " Final round." if rnd == total else ""
        await _fire_narration(
            game_id,
            "round_preview",
            f"Round {rnd} of {total}. {rt_label}.{final} Set the stage — what's at stake now.",
        )


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
        f"The experiment begins. {player_count} subjects — "
        f"{human_count} human, {ai_count} machine. Announce the start of testing.",
    )
