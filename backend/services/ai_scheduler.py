"""AI player scheduler — generates actions with random delays using generate-then-lock."""

from __future__ import annotations

import asyncio
import random

import structlog

from backend.api.deps import get_connection_manager, get_game_repository, get_settings
from backend.llm.agents import (
    AIPlayerDeps,
    decide_vote,
    generate_answer,
    generate_nomination,
    generate_question,
    generate_question_response,
)
from backend.llm.personalities import PERSONALITIES, Personality
from backend.services.game_logic import (
    fill_missing_responses,
    get_alive_players,
    get_player_by_id,
    make_phase_changed_event,
)
from schemas.api_models import (
    AnswerSubmittedEvent,
    NominatedEvent,
    NominationCastEvent,
    QuestionSubmittedEvent,
    ResponseSubmittedEvent,
    VoteCastEvent,
)
from schemas.constants import MISSING_ALIAS
from schemas.game_state import GamePhase, PlayerRole, QuestionEntry, RoundType

log = structlog.get_logger(__name__)

# Store personality assignments per game: game_id -> {player_id -> Personality}
_personality_map: dict[str, dict[str, Personality]] = {}

# Store active AI tasks per game
_ai_tasks: dict[str, list[asyncio.Task]] = {}


def assign_personalities(game_id: str, ai_player_ids: list[str]) -> None:
    """Assign random personalities to AI players (no duplicates)."""
    personalities = random.sample(PERSONALITIES, min(len(ai_player_ids), len(PERSONALITIES)))
    _personality_map[game_id] = {
        pid: personalities[i % len(personalities)] for i, pid in enumerate(ai_player_ids)
    }
    log.info(
        "ai_personalities_assigned",
        game_id=game_id,
        assignments={pid: p.name for pid, p in _personality_map[game_id].items()},
    )


def get_personality(game_id: str, player_id: str) -> Personality:
    """Get the personality for an AI player."""
    return _personality_map.get(game_id, {}).get(player_id, PERSONALITIES[0])


def _build_deps(game_id: str, player_id: str) -> AIPlayerDeps | None:
    """Build AIPlayerDeps from current game state (read without lock — snapshot)."""
    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        return None

    state = session.state
    player = get_player_by_id(state, player_id)
    if not player or not player.is_alive:
        return None

    personality = get_personality(game_id, player_id)
    alive = get_alive_players(state)
    alive_aliases = [p.alias for p in alive]

    all_answers: dict[str, str] = {}
    current_prompt = ""
    round_type: str = RoundType.PROBE
    assigned_target: str | None = None
    my_answer: str | None = None
    questions: list[dict] | None = None
    nominated_alias: str | None = None
    synthesis: str | None = None
    hot_seat_response: str | None = None

    if state.current_round:
        rs = state.current_round
        current_prompt = rs.prompt_text
        round_type = rs.round_type

        player_map = {p.id: p for p in state.players}
        for pid, answer in rs.answers.items():
            p = player_map.get(pid)
            if p:
                all_answers[p.alias] = answer

        my_answer = rs.answers.get(player_id)

        # Assigned target (Probe)
        target_id = rs.assignments.get(player_id)
        if target_id:
            target_p = player_map.get(target_id)
            if target_p:
                assigned_target = target_p.alias

        # Nominated (Interrogation)
        if rs.nominated_id:
            nom_p = player_map.get(rs.nominated_id)
            if nom_p:
                nominated_alias = nom_p.alias

        synthesis = rs.synthesis

        # Build questions context
        if rs.questions:
            questions = []
            for q in rs.questions:
                qd = {
                    "target_alias": q.target_alias,
                    "question": q.question,
                    "response": q.response,
                }
                questions.append(qd)

        # Hot seat response
        if rs.nominated_id:
            for q in rs.questions:
                if q.target_id == rs.nominated_id and q.response:
                    hot_seat_response = q.response
                    break

    return AIPlayerDeps(
        personality=personality,
        player_alias=player.alias,
        current_prompt=current_prompt,
        all_answers=all_answers,
        alive_players=alive_aliases,
        round_number=state.round_number,
        round_type=round_type,
        assigned_target=assigned_target,
        my_answer=my_answer,
        questions=questions,
        nominated_alias=nominated_alias,
        synthesis=synthesis,
        hot_seat_response=hot_seat_response,
    )


async def on_phase_change(game_id: str, phase: GamePhase) -> None:
    """Called when a phase changes. Schedules AI actions for the new phase."""
    cancel_all(game_id)

    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        return

    state = session.state
    ai_players = [p for p in state.players if p.role == PlayerRole.AI and p.is_alive]

    if not ai_players:
        return

    tasks: list[asyncio.Task] = []

    if phase == GamePhase.PROMPT:
        for player in ai_players:
            delay = random.uniform(3, 15)
            tasks.append(asyncio.create_task(_ai_answer_task(game_id, player.id, delay)))

    elif phase == GamePhase.NOMINATE:
        for player in ai_players:
            delay = random.uniform(2, 8)
            tasks.append(asyncio.create_task(_ai_nominate_task(game_id, player.id, delay)))

    elif phase == GamePhase.QUESTION:
        for player in ai_players:
            delay = random.uniform(3, 12)
            tasks.append(asyncio.create_task(_ai_question_task(game_id, player.id, delay)))

    elif phase == GamePhase.RESPOND:
        for player in ai_players:
            delay = random.uniform(2, 8)
            tasks.append(asyncio.create_task(_ai_respond_task(game_id, player.id, delay)))

    elif phase == GamePhase.REVIEW:
        for player in ai_players:
            delay = random.uniform(5, 15)
            tasks.append(asyncio.create_task(_ai_vote_task(game_id, player.id, delay)))

    _ai_tasks[game_id] = tasks


def cancel_all(game_id: str) -> None:
    """Cancel all pending AI tasks for a game."""
    tasks = _ai_tasks.pop(game_id, [])
    for task in tasks:
        if not task.done():
            task.cancel()


async def _ai_answer_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player answers a prompt after a delay."""
    try:
        await asyncio.sleep(delay)

        deps = _build_deps(game_id, player_id)
        if not deps:
            return
        answer_text = await generate_answer(deps)

        cm = get_connection_manager()
        repo = get_game_repository()
        settings = get_settings()
        lock = cm.get_lock(game_id)

        async with lock:
            session = repo.get(game_id)
            if not session or session.state.phase != GamePhase.PROMPT:
                return

            state = session.state
            if not state.current_round or player_id in state.current_round.answers:
                return

            state.current_round.answers[player_id] = answer_text

            alive = get_alive_players(state)
            answer_count = len(state.current_round.answers)
            total_count = len(alive)

            await cm.broadcast(
                game_id,
                AnswerSubmittedEvent(
                    seq=session.next_seq(),
                    player_id=player_id,
                    answer_count=answer_count,
                    total_count=total_count,
                ),
            )

            log.info("ai_answer_submitted", game_id=game_id, player_id=player_id)

            if answer_count >= total_count:
                from backend.api.deps import get_timer_manager

                get_timer_manager().cancel_timer(game_id)

                round_state = state.current_round
                if round_state.round_type == RoundType.INTERROGATION:
                    from backend.services.game_logic import transition_to_nominate

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
                    from backend.services.game_logic import (
                        assign_question_targets,
                        transition_to_question,
                    )

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
                    next_phase = GamePhase.QUESTION
            else:
                next_phase = None

        if next_phase:
            from backend.api.routes.actions import _start_phase_timer

            await _start_phase_timer(game_id, next_phase)
            await on_phase_change(game_id, next_phase)

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("ai_answer_task_error", game_id=game_id, player_id=player_id)


async def _ai_nominate_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player nominates after a delay (Interrogation)."""
    try:
        await asyncio.sleep(delay)

        deps = _build_deps(game_id, player_id)
        if not deps:
            return
        nominee_alias = await generate_nomination(deps)

        cm = get_connection_manager()
        repo = get_game_repository()
        settings = get_settings()
        lock = cm.get_lock(game_id)

        async with lock:
            session = repo.get(game_id)
            if not session or session.state.phase != GamePhase.NOMINATE:
                return

            state = session.state
            round_state = state.current_round
            if not round_state or player_id in round_state.nominations:
                return

            # Resolve alias to id
            target = next(
                (p for p in state.players if p.alias == nominee_alias and p.is_alive),
                None,
            )
            if not target:
                candidates = [p for p in state.players if p.is_alive and p.id != player_id]
                if not candidates:
                    return
                target = random.choice(candidates)

            round_state.nominations[player_id] = target.id

            alive = get_alive_players(state)
            nom_count = len(round_state.nominations)
            total_count = len(alive)

            await cm.broadcast(
                game_id,
                NominationCastEvent(
                    seq=session.next_seq(),
                    voter_id=player_id,
                    count=nom_count,
                    total=total_count,
                ),
            )

            log.info(
                "ai_nomination_cast", game_id=game_id, player_id=player_id, target=target.alias
            )

            if nom_count >= total_count:
                from backend.api.deps import get_timer_manager
                from backend.services.game_logic import resolve_nominations, transition_to_question

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
                need_timer = True
            else:
                need_timer = False

        if need_timer:
            from backend.api.routes.actions import _start_phase_timer

            await _start_phase_timer(game_id, GamePhase.QUESTION)
            await on_phase_change(game_id, GamePhase.QUESTION)

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("ai_nominate_task_error", game_id=game_id, player_id=player_id)


async def _ai_question_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player submits a question after a delay."""
    try:
        await asyncio.sleep(delay)

        # Check if this AI is the hot-seated player (can't ask questions)
        repo = get_game_repository()
        session = repo.get(game_id)
        if not session:
            return
        round_state = session.state.current_round
        if round_state and round_state.round_type == RoundType.INTERROGATION:
            if player_id == round_state.nominated_id:
                return  # Hot-seated player doesn't ask

        deps = _build_deps(game_id, player_id)
        if not deps:
            return
        question_text = await generate_question(deps)

        cm = get_connection_manager()
        settings = get_settings()
        lock = cm.get_lock(game_id)

        async with lock:
            session = repo.get(game_id)
            if not session or session.state.phase != GamePhase.QUESTION:
                return

            state = session.state
            round_state = state.current_round
            if not round_state:
                return

            already_asked = any(q.questioner_id == player_id for q in round_state.questions)
            if already_asked:
                return

            # Determine target
            if round_state.round_type == RoundType.INTERROGATION:
                target_id = round_state.nominated_id
            else:
                target_id = round_state.assignments.get(player_id)

            if not target_id:
                return

            target_player = get_player_by_id(state, target_id)
            target_alias = target_player.alias if target_player else MISSING_ALIAS

            entry = QuestionEntry(
                questioner_id=player_id,
                target_id=target_id,
                target_alias=target_alias,
                question=question_text,
                anonymous=round_state.round_type == RoundType.PROBE,
            )
            round_state.questions.append(entry)

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

            log.info("ai_question_submitted", game_id=game_id, player_id=player_id)

            if q_count >= expected:
                from backend.api.deps import get_timer_manager

                get_timer_manager().cancel_timer(game_id)

                if round_state.round_type == RoundType.INTERROGATION:
                    from backend.api.routes.actions import _synthesize_and_transition

                    await _synthesize_and_transition(game_id, session)
                    need_timer = False
                else:
                    from backend.services.game_logic import transition_to_respond

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
                    need_timer = True
            else:
                need_timer = False

        if need_timer:
            from backend.api.routes.actions import _start_phase_timer

            await _start_phase_timer(game_id, GamePhase.RESPOND)
            await on_phase_change(game_id, GamePhase.RESPOND)

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("ai_question_task_error", game_id=game_id, player_id=player_id)


async def _ai_respond_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player responds to a question after a delay."""
    try:
        await asyncio.sleep(delay)

        repo = get_game_repository()
        session = repo.get(game_id)
        if not session or session.state.phase != GamePhase.RESPOND:
            return

        state = session.state
        round_state = state.current_round
        if not round_state:
            return

        # Check if this AI has a pending question
        if round_state.round_type == RoundType.INTERROGATION:
            if player_id != round_state.nominated_id:
                return  # Only nominee responds
            pending_q = next(
                (
                    q
                    for q in round_state.questions
                    if q.target_id == player_id and q.response is None
                ),
                None,
            )
            question_text = round_state.synthesis or (pending_q.question if pending_q else None)
        else:
            pending_q = next(
                (
                    q
                    for q in round_state.questions
                    if q.target_id == player_id and q.response is None
                ),
                None,
            )
            question_text = pending_q.question if pending_q else None

        if not pending_q or not question_text:
            return

        deps = _build_deps(game_id, player_id)
        if not deps:
            return
        response_text = await generate_question_response(deps, question_text)

        cm = get_connection_manager()
        settings = get_settings()
        lock = cm.get_lock(game_id)

        async with lock:
            session = repo.get(game_id)
            if not session or session.state.phase != GamePhase.RESPOND:
                return

            state = session.state
            round_state = state.current_round
            if not round_state:
                return

            # Re-find the pending question under lock
            target_q = next(
                (
                    q
                    for q in round_state.questions
                    if q.target_id == player_id and q.response is None
                ),
                None,
            )
            if not target_q:
                return

            target_q.response = response_text

            player = get_player_by_id(state, player_id)
            player_alias = player.alias if player else MISSING_ALIAS

            if round_state.round_type == RoundType.INTERROGATION:
                responded_count = 1
                expected = 1
            else:
                targets_with_questions = {q.target_id for q in round_state.questions}
                responded_count = sum(1 for q in round_state.questions if q.response is not None)
                expected = len(targets_with_questions)

            await cm.broadcast(
                game_id,
                ResponseSubmittedEvent(
                    seq=session.next_seq(),
                    target_id=player_id,
                    target_alias=player_alias,
                    response=response_text,
                    count=responded_count,
                    total=expected,
                ),
            )

            log.info("ai_response_submitted", game_id=game_id, player_id=player_id)

            if responded_count >= expected:
                from backend.api.deps import get_timer_manager
                from backend.services.game_logic import transition_to_review

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
                need_timer = True
            else:
                need_timer = False

        if need_timer:
            from backend.api.routes.actions import _start_phase_timer

            await _start_phase_timer(game_id, GamePhase.REVIEW)
            await on_phase_change(game_id, GamePhase.REVIEW)

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("ai_respond_task_error", game_id=game_id, player_id=player_id)


async def _ai_vote_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player votes after a delay."""
    try:
        await asyncio.sleep(delay)

        deps = _build_deps(game_id, player_id)
        if not deps:
            return
        vote_aliases = await decide_vote(deps)

        cm = get_connection_manager()
        repo = get_game_repository()
        lock = cm.get_lock(game_id)

        async with lock:
            session = repo.get(game_id)
            if not session or session.state.phase != GamePhase.REVIEW:
                return

            state = session.state
            if not state.current_round:
                return

            # Resolve aliases to player_ids
            target_ids: list[str] = []
            for alias in vote_aliases:
                target = next(
                    (p for p in state.players if p.alias == alias and p.is_alive),
                    None,
                )
                if target and target.id != player_id:
                    target_ids.append(target.id)

            # Pad with random if empty
            if not target_ids:
                candidates = [p for p in state.players if p.is_alive and p.id != player_id]
                if candidates:
                    target_ids = [random.choice(candidates).id]

            state.current_round.votes[player_id] = target_ids

            alive = get_alive_players(state)
            vote_count = len(state.current_round.votes)
            total_count = len(alive)

            await cm.broadcast(
                game_id,
                VoteCastEvent(
                    seq=session.next_seq(),
                    voter_id=player_id,
                    vote_count=vote_count,
                    total_count=total_count,
                ),
            )

            log.info("ai_vote_cast", game_id=game_id, player_id=player_id, targets=vote_aliases)

            # NO early-complete for REVIEW

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("ai_vote_task_error", game_id=game_id, player_id=player_id)


def cleanup_game(game_id: str) -> None:
    """Clean up all AI state for a game."""
    cancel_all(game_id)
    _personality_map.pop(game_id, None)
