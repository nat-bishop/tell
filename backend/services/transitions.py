"""Phase transition sequences — shared by route handlers and AI scheduler."""

from __future__ import annotations

import asyncio
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
    check_game_over,
    fill_missing_answers,
    get_interstitial_hold,
    get_next_round_type,
    get_phase_duration,
    get_player_by_id,
    make_game_over_event,
    make_phase_changed_event,
    resolve_matchup_votes,
    score_brain_test,
    transition_to_brain_test,
    transition_to_brain_test_results,
    transition_to_matchup,
    transition_to_task_matchup_prompt,
)
from schemas.aliases import generate_aliases
from schemas.api_models import (
    BrainTestChallengeEvent,
    BrainTestResultsEvent,
    FinalRevealEvent,
    MatchupChallengeEvent,
    NarrationEvent,
    PlayerJoinedEvent,
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
        parts.append(f"Round type: {rs.round_type}.")
        if rs.prompt_text:
            parts.append(f'Prompt: "{rs.prompt_text}"')
        if rs.answers:
            alias_map = {p.id: p.alias for p in state.players}
            for pid, ans in rs.answers.items():
                alias = alias_map.get(pid, pid)
                parts.append(f'  {alias} answered: "{ans}"')
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
    # Interstitial hold is already baked into phase_deadline by transition functions,
    # so the timer must include it too to stay in sync with the deadline.
    duration += get_interstitial_hold(phase)

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

        elif expired_phase == GamePhase.REVIEW:
            # REVIEW timer expired — no votes to resolve in score-based model
            # (review is informational only between matchup rounds)
            pass

        elif expired_phase == GamePhase.MATCHUP:
            # Safety timer — resolve matchup votes
            await do_matchup_complete(game_id, session)

        elif expired_phase == GamePhase.BRAIN_TEST:
            # Safety timer — transition to results
            await do_brain_test_complete(game_id, session)

        elif expired_phase == GamePhase.BRAIN_TEST_RESULTS:
            # Results done — check game over or next round
            await do_after_brain_test(game_id, session)


async def do_prompt_complete(game_id: str, session) -> None:
    """PROMPT complete → TASK rounds go to MATCHUP.

    Assumes caller holds the game lock and has called fill_missing_answers.
    """
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state
    round_state = state.current_round

    # Fire narrator: post-submissions
    await _fire_narration(
        game_id,
        "post_submissions",
        "All answers are in. Comment briefly on what you notice.",
    )

    assert round_state, "No active round in PROMPT phase"

    # Task rounds → MATCHUP (1v1 pair voting)
    transition_to_matchup(state, settings.matchup_duration)
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
    next_phase = GamePhase.MATCHUP
    await start_phase_timer(game_id, next_phase)
    # Notify AI *before* starting the matchup loop — on_phase_change calls
    # cancel_all() which would kill the loop task if it were already registered.
    await _notify_ai(game_id, next_phase)
    # Start the matchup sub-round loop (registers its own task)
    await _start_matchup_loop(game_id, session)


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


async def do_matchup_complete(game_id: str, session) -> None:
    """All matchup sub-rounds done → resolve votes → check game over or next round.

    Assumes caller holds the game lock.
    """
    cm = get_connection_manager()
    state = session.state

    state, matchup_results_event = resolve_matchup_votes(state, session.next_seq)
    await cm.broadcast(game_id, matchup_results_event)
    log.info(
        "matchup_resolved",
        scores={p.id: p.score for p in state.players},
    )

    # Check game over
    result = check_game_over(state)
    if result:
        winner, winner_ids = result
        await _do_game_over(game_id, session, state, winner, winner_ids)
        return

    # Fire narrator: between rounds
    await _fire_narration(
        game_id,
        "between_rounds",
        "A round just ended. Comment on the state of play — scores, standout moments.",
    )

    await _start_next_round(game_id, session)


async def do_brain_test_complete(game_id: str, session) -> None:
    """Brain test challenges done → score, update player scores, show results."""
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state
    rs = state.current_round
    if not rs:
        return

    # Build results: player_id -> list of {question, options, selected_index, correct_index, ...}
    results: dict[str, list[dict]] = {}
    for p in state.players:
        player_results = []
        for ch in rs.brain_challenges:
            player_results.append(
                {
                    "question": ch.question,
                    "options": ch.options,
                    "selected_index": ch.responses.get(p.id, -1),
                    "correct_index": ch.correct_index,
                    "challenge_type": ch.challenge_type,
                }
            )
        results[p.id] = player_results

    # Score brain test
    bt_scores = score_brain_test(rs.brain_challenges)

    # Add brain test scores to each player's running total
    for p in state.players:
        p.score += bt_scores.get(p.id, 0)

    # Build running total scores for the event
    scores = {p.id: p.score for p in state.players}

    await cm.broadcast(
        game_id,
        BrainTestResultsEvent(
            seq=session.next_seq(),
            results=results,
            scores=scores,
        ),
    )

    transition_to_brain_test_results(state, settings.brain_test_results_duration)
    await cm.broadcast(
        game_id,
        _make_event(state, session, settings, round_type=RoundType.BRAIN_TEST),
    )
    await start_phase_timer(game_id, GamePhase.BRAIN_TEST_RESULTS)

    # Fire narrator
    await _fire_narration(
        game_id,
        "post_submissions",
        "Brain test results are in. Comment on notable performances.",
    )


async def do_after_brain_test(game_id: str, session) -> None:
    """Brain test results done → check game over or next round."""
    state = session.state

    # Check game over
    result = check_game_over(state)
    if result:
        winner, winner_ids = result
        await _do_game_over(game_id, session, state, winner, winner_ids)
        return

    await _start_next_round(game_id, session)


async def _start_next_round(game_id: str, session) -> None:
    """Route to the next round type — TASK or BRAIN_TEST.

    Assumes caller holds the game lock.
    """
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state

    next_round_type = get_next_round_type(state)
    state.round_types.append(next_round_type)

    if next_round_type == RoundType.TASK:
        total = get_phase_duration(settings, GamePhase.PROMPT, RoundType.TASK) or 35
        transition_to_task_matchup_prompt(state, total, settings.prompt_reading_duration)
        round_state = state.current_round
        # Build matchup data for PhaseChangedEvent so clients can look up their prompt
        matchup_data = None
        if round_state and round_state.matchups:
            player_map = {p.id: p for p in state.players}
            matchup_data = [
                {
                    "pair": m.pair,
                    "prompt_text": m.prompt_text,
                    "prompt_category": m.prompt_category,
                    "left_alias": player_map[m.pair[0]].alias if m.pair[0] in player_map else "",
                    "right_alias": player_map[m.pair[1]].alias if m.pair[1] in player_map else "",
                }
                for m in round_state.matchups
            ]
        await cm.broadcast(
            game_id,
            _make_event(
                state,
                session,
                settings,
                prompt_text=round_state.prompt_text if round_state else None,
                prompt_category=round_state.prompt_category if round_state else None,
                round_type=round_state.round_type if round_state else RoundType.TASK,
                matchups=matchup_data,
            ),
        )
        await start_phase_timer(game_id, GamePhase.PROMPT, RoundType.TASK)
        await _notify_ai(game_id, GamePhase.PROMPT)

    elif next_round_type == RoundType.BRAIN_TEST:
        from schemas.prompts import select_brain_test_challenges

        challenges = select_brain_test_challenges(settings.brain_test_challenges)
        transition_to_brain_test(state, challenges, settings.brain_test_duration)
        await cm.broadcast(
            game_id,
            _make_event(state, session, settings, round_type=RoundType.BRAIN_TEST),
        )
        await start_phase_timer(game_id, GamePhase.BRAIN_TEST)
        await _start_brain_test_loop(game_id, session)


async def _start_matchup_loop(game_id: str, session) -> None:
    """Launch the async sub-round loop for matchup challenges."""

    async def _matchup_loop():
        try:
            cm = get_connection_manager()
            settings = get_settings()
            repo = get_game_repository()
            sub_duration = settings.matchup_challenge_duration
            lock = cm.get_lock(game_id)

            async with lock:
                session = repo.get(game_id)
                if not session:
                    return
                rs = session.state.current_round
                if not rs:
                    return
                num_matchups = len(rs.matchups)

            for i in range(num_matchups):
                async with lock:
                    session = repo.get(game_id)
                    if not session:
                        return
                    state = session.state
                    if state.phase != GamePhase.MATCHUP:
                        return
                    rs = state.current_round
                    if not rs or i >= len(rs.matchups):
                        return

                    rs.current_matchup = i
                    m = rs.matchups[i]
                    left_id, right_id = m.pair[0], m.pair[1]

                    left_player = get_player_by_id(state, left_id)
                    right_player = get_player_by_id(state, right_id)
                    left_answer = rs.answers.get(left_id, "[no response]")
                    right_answer = rs.answers.get(right_id, "[no response]")

                    sub_deadline = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=sub_duration)
                    state.phase_deadline = sub_deadline

                    await cm.broadcast(
                        game_id,
                        MatchupChallengeEvent(
                            seq=session.next_seq(),
                            matchup_index=i,
                            left_player_id=left_id,
                            left_alias=left_player.alias if left_player else left_id,
                            left_answer=left_answer,
                            right_player_id=right_id,
                            right_alias=right_player.alias if right_player else right_id,
                            right_answer=right_answer,
                            prompt_text=m.prompt_text,
                            sub_deadline=sub_deadline.isoformat(),
                            phase_duration=sub_duration,
                        ),
                    )

                # Schedule AI votes for this matchup
                from backend.services.ai_scheduler import on_matchup_challenge

                await on_matchup_challenge(game_id, i)

                await asyncio.sleep(sub_duration)

            # All matchups done — transition to results
            async with lock:
                session = repo.get(game_id)
                if not session:
                    return
                if session.state.phase != GamePhase.MATCHUP:
                    return
                get_timer_manager().cancel_timer(game_id)
                await do_matchup_complete(game_id, session)

        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("matchup_loop_error", game_id=game_id)

    task = asyncio.create_task(_matchup_loop())
    from backend.services.ai_scheduler import register_task

    register_task(game_id, task)


async def _start_brain_test_loop(game_id: str, session) -> None:
    """Launch the async sub-round loop for Brain Test challenges."""

    async def _brain_loop():
        try:
            cm = get_connection_manager()
            settings = get_settings()
            repo = get_game_repository()
            sub_duration = settings.brain_test_challenge_duration
            num_challenges = settings.brain_test_challenges
            lock = cm.get_lock(game_id)

            for i in range(num_challenges):
                async with lock:
                    session = repo.get(game_id)
                    if not session:
                        return
                    state = session.state
                    if state.phase != GamePhase.BRAIN_TEST:
                        return
                    rs = state.current_round
                    if not rs or i >= len(rs.brain_challenges):
                        return

                    rs.current_sub_round = i
                    ch = rs.brain_challenges[i]

                    sub_deadline = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=sub_duration)
                    state.phase_deadline = sub_deadline

                    await cm.broadcast(
                        game_id,
                        BrainTestChallengeEvent(
                            seq=session.next_seq(),
                            challenge_index=i,
                            challenge_type=ch.challenge_type,
                            question=ch.question,
                            options=ch.options,
                            sub_deadline=sub_deadline.isoformat(),
                            phase_duration=sub_duration,
                        ),
                    )

                # Schedule AI for this challenge
                from backend.services.ai_scheduler import on_brain_test_challenge

                await on_brain_test_challenge(game_id, i)

                await asyncio.sleep(sub_duration)

            # All challenges done — transition to results
            async with lock:
                session = repo.get(game_id)
                if not session:
                    return
                if session.state.phase != GamePhase.BRAIN_TEST:
                    return
                get_timer_manager().cancel_timer(game_id)
                await do_brain_test_complete(game_id, session)

        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("brain_test_loop_error", game_id=game_id)

    task = asyncio.create_task(_brain_loop())
    from backend.services.ai_scheduler import register_task

    register_task(game_id, task)


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
        "The humans must find the AI. The AI must blend in.",
    )
