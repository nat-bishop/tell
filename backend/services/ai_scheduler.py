"""AI player scheduler — generates actions with random delays using generate-then-lock."""

from __future__ import annotations

import asyncio
import random

import structlog
from pydantic_ai.messages import ModelMessage

from backend.api.deps import get_connection_manager, get_game_repository, get_timer_manager
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
    max_votes_for_player,
)
from backend.services.transitions import (
    do_nominate_complete,
    do_prompt_complete,
    do_question_complete,
    do_respond_complete,
)
from schemas.api_models import (
    AnswerSubmittedEvent,
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

# Store conversation history per AI player: game_id -> {player_id -> messages}
_conversation_history: dict[str, dict[str, list[ModelMessage]]] = {}


def assign_personalities(game_id: str, ai_player_ids: list[str]) -> None:
    """Assign random personalities to AI players (no duplicates)."""
    personalities = random.sample(PERSONALITIES, min(len(ai_player_ids), len(PERSONALITIES)))
    _personality_map[game_id] = {
        pid: personalities[i % len(personalities)] for i, pid in enumerate(ai_player_ids)
    }
    _conversation_history[game_id] = {pid: [] for pid in ai_player_ids}
    log.info(
        "ai_personalities_assigned",
        game_id=game_id,
        assignments={pid: p.name for pid, p in _personality_map[game_id].items()},
    )


def get_personality(game_id: str, player_id: str) -> Personality:
    """Get the personality for an AI player."""
    return _personality_map.get(game_id, {}).get(player_id, PERSONALITIES[0])


def _get_history(game_id: str, player_id: str) -> list[ModelMessage]:
    """Get conversation history for an AI player."""
    return _conversation_history.get(game_id, {}).get(player_id, [])


def _set_history(game_id: str, player_id: str, history: list[ModelMessage]) -> None:
    """Store updated conversation history for an AI player."""
    if game_id in _conversation_history:
        _conversation_history[game_id][player_id] = history


# ---------------------------------------------------------------------------
# Build action prompts — the user message for each phase action
# ---------------------------------------------------------------------------


def _build_answer_prompt(deps: AIPlayerDeps) -> str:
    return (
        f'The prompt is: "{deps.current_prompt}"\n\n'
        "Respond in character. 1-3 sentences. Do not include your name."
    )


def _build_question_prompt(deps: AIPlayerDeps) -> str:
    target_alias = deps.assigned_target or deps.nominated_alias or "unknown"
    target_answer = deps.all_answers.get(target_alias, "")
    return (
        f'The prompt was: "{deps.current_prompt}"\n'
        f'{target_alias} answered: "{target_answer}"\n\n'
        f"Your questioning style: {deps.personality.question_style}\n\n"
        "Write ONE short follow-up question (1 sentence, max 120 characters). "
        "Probe for emotional authenticity, suspicious specificity, or logical gaps. "
        "Your question is anonymous — they won't know who asked.\n\n"
        "Respond with ONLY the question."
    )


def _build_response_prompt(deps: AIPlayerDeps, question: str) -> str:
    return (
        f'The prompt was: "{deps.current_prompt}"\n'
        f'Your answer was: "{deps.my_answer}"\n'
        f'Question you received: "{question}"\n\n'
        "Write a brief response (1-2 sentences). Elaborate on or defend your answer naturally. "
        "Robots don't get defensive or emotional — they clarify and compute.\n\n"
        "Respond with ONLY your response."
    )


def _build_nomination_prompt(deps: AIPlayerDeps) -> str:
    other_players = [a for a in deps.alive_players if a != deps.player_alias]
    answers_text = "\n".join(
        f"  {alias}: {answer}"
        for alias, answer in deps.all_answers.items()
        if alias != deps.player_alias
    )
    return (
        f"Choose one player to put on the hot seat for interrogation. "
        f"Pick the player whose answer is most worth scrutinizing.\n\n"
        f"{deps.personality.vote_strategy}\n\n"
        f"Answers this round:\n{answers_text}\n\n"
        f"Valid players: {', '.join(other_players)}\n"
        f"Respond with a JSON object containing target_alias and reasoning."
    )


def _build_vote_prompt(deps: AIPlayerDeps) -> str:
    other_players = [a for a in deps.alive_players if a != deps.player_alias]
    max_v = max_votes_for_player(len(deps.alive_players))
    return (
        f"Time to vote. Choose up to {max_v} players you suspect of being human.\n\n"
        f"{deps.personality.vote_strategy}\n\n"
        f"Valid players: {', '.join(other_players)}\n"
        f"Respond with a JSON object containing targets (list of aliases) and reasoning."
    )


# ---------------------------------------------------------------------------
# Build deps
# ---------------------------------------------------------------------------


def _build_deps(game_id: str, player_id: str, action_prompt: str = "") -> AIPlayerDeps | None:
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
        action_prompt=action_prompt,
    )


# ---------------------------------------------------------------------------
# Phase scheduling
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# AI task functions — generate-then-lock pattern with conversation history
# ---------------------------------------------------------------------------


async def _ai_answer_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player answers a prompt after a delay."""
    try:
        await asyncio.sleep(delay)

        history = _get_history(game_id, player_id)
        deps = _build_deps(game_id, player_id)
        if not deps:
            return
        deps.action_prompt = _build_answer_prompt(deps)
        answer_text, updated_history = await generate_answer(deps, history)

        cm = get_connection_manager()
        lock = cm.get_lock(game_id)

        async with lock:
            repo = get_game_repository()
            session = repo.get(game_id)
            if not session or session.state.phase != GamePhase.PROMPT:
                return

            state = session.state
            if not state.current_round or player_id in state.current_round.answers:
                return

            state.current_round.answers[player_id] = answer_text
            _set_history(game_id, player_id, updated_history)

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
                get_timer_manager().cancel_timer(game_id)
                fill_missing_answers(state)
                await do_prompt_complete(game_id, session)

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("ai_answer_task_error", game_id=game_id, player_id=player_id)


async def _ai_nominate_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player nominates after a delay (Interrogation)."""
    try:
        await asyncio.sleep(delay)

        history = _get_history(game_id, player_id)
        deps = _build_deps(game_id, player_id)
        if not deps:
            return
        deps.action_prompt = _build_nomination_prompt(deps)
        nominee_alias, updated_history = await generate_nomination(deps, history)

        cm = get_connection_manager()
        lock = cm.get_lock(game_id)

        async with lock:
            repo = get_game_repository()
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
            _set_history(game_id, player_id, updated_history)

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
                get_timer_manager().cancel_timer(game_id)
                await do_nominate_complete(game_id, session)

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("ai_nominate_task_error", game_id=game_id, player_id=player_id)


async def _ai_question_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player submits a question after a delay."""
    try:
        await asyncio.sleep(delay)

        # Check eligibility before generating (avoid wasted LLM call)
        repo = get_game_repository()
        session = repo.get(game_id)
        if not session:
            return
        round_state = session.state.current_round
        if round_state and not is_question_eligible(round_state, player_id):
            return

        history = _get_history(game_id, player_id)
        deps = _build_deps(game_id, player_id)
        if not deps:
            return
        deps.action_prompt = _build_question_prompt(deps)
        question_text, updated_history = await generate_question(deps, history)

        cm = get_connection_manager()
        lock = cm.get_lock(game_id)

        async with lock:
            repo = get_game_repository()
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

            target_id = get_question_target(round_state, player_id)
            if not target_id:
                return

            target_player = get_player_by_id(state, target_id)
            target_alias = target_player.alias if target_player else MISSING_ALIAS

            entry = QuestionEntry(
                questioner_id=player_id,
                target_id=target_id,
                target_alias=target_alias,
                question=question_text,
                anonymous=is_question_anonymous(round_state.round_type),
            )
            round_state.questions.append(entry)
            _set_history(game_id, player_id, updated_history)

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

            log.info("ai_question_submitted", game_id=game_id, player_id=player_id)

            if q_count >= expected:
                get_timer_manager().cancel_timer(game_id)
                await do_question_complete(game_id, session)

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

        # Check eligibility
        if not is_response_eligible(round_state, player_id):
            return

        pending_q = next(
            (q for q in round_state.questions if q.target_id == player_id and q.response is None),
            None,
        )
        # Use synthesis if available (interrogation), else direct question (probe)
        question_text = round_state.synthesis or (pending_q.question if pending_q else None)

        if not pending_q or not question_text:
            return

        history = _get_history(game_id, player_id)
        deps = _build_deps(game_id, player_id)
        if not deps:
            return
        deps.action_prompt = _build_response_prompt(deps, question_text)
        response_text, updated_history = await generate_question_response(
            deps, question_text, history
        )

        cm = get_connection_manager()
        lock = cm.get_lock(game_id)

        async with lock:
            repo = get_game_repository()
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
            _set_history(game_id, player_id, updated_history)

            player = get_player_by_id(state, player_id)
            player_alias = player.alias if player else MISSING_ALIAS

            responded_count, expected = count_responses(round_state)

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
                get_timer_manager().cancel_timer(game_id)
                fill_missing_responses(state)
                await do_respond_complete(game_id, session)

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("ai_respond_task_error", game_id=game_id, player_id=player_id)


async def _ai_vote_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player votes after a delay."""
    try:
        await asyncio.sleep(delay)

        history = _get_history(game_id, player_id)
        deps = _build_deps(game_id, player_id)
        if not deps:
            return
        deps.action_prompt = _build_vote_prompt(deps)
        vote_aliases, updated_history = await decide_vote(deps, history)

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
            _set_history(game_id, player_id, updated_history)

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
    _conversation_history.pop(game_id, None)
