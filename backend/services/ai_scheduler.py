"""AI player scheduler — generates actions with random delays using generate-then-lock."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable, Coroutine
from typing import Any

import structlog
from pydantic_ai.messages import ModelMessage

from backend.api.deps import (
    get_connection_manager,
    get_game_repository,
    get_settings,
    get_timer_manager,
)
from backend.llm.agents import (
    AIPlayerDeps,
    decide_vote,
    generate_answer,
    generate_association,
    generate_discussion_message,
    generate_nomination,
    generate_question,
    generate_question_response,
)
from backend.llm.personalities import PERSONALITIES, Personality
from backend.llm.prompts import (
    build_answer_prompt,
    build_discussion_prompt,
    build_nomination_prompt,
    build_question_prompt,
    build_response_prompt,
    build_vote_prompt,
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

# Type alias for apply callbacks used in _run_ai_task
_ApplyFn = Callable[..., Coroutine[Any, Any, None]]

log = structlog.get_logger(__name__)

# Store personality assignments per game: game_id -> {player_id -> Personality}
_personality_map: dict[str, dict[str, Personality]] = {}

# Store active AI tasks per game
_ai_tasks: dict[str, list[asyncio.Task]] = {}

# Store conversation history per AI player: game_id -> {player_id -> messages}
_conversation_history: dict[str, dict[str, list[ModelMessage]]] = {}

# Store narrator message history per game: game_id -> messages
_narrator_history: dict[str, list[ModelMessage]] = {}

# Track discussion messages per game for AI context: game_id -> [{alias, message}]
_discussion_messages: dict[str, list[dict]] = {}


def assign_personalities(game_id: str, ai_player_ids: list[str]) -> None:
    """Assign random personalities to AI players (no duplicates)."""
    personalities = random.sample(PERSONALITIES, min(len(ai_player_ids), len(PERSONALITIES)))
    _personality_map[game_id] = {
        pid: personalities[i % len(personalities)] for i, pid in enumerate(ai_player_ids)
    }
    _conversation_history[game_id] = {pid: [] for pid in ai_player_ids}
    _narrator_history[game_id] = []
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
    round_type: RoundType = RoundType.TASK
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

        # Assigned target
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


def record_discussion_message(game_id: str, alias: str, message: str) -> None:
    """Record a discussion message for AI context (called from route handler too)."""
    _discussion_messages.setdefault(game_id, []).append({"alias": alias, "message": message})


async def on_phase_change(game_id: str, phase: GamePhase) -> None:
    """Called when a phase changes. Schedules AI actions for the new phase."""
    cancel_all(game_id)
    # Clear discussion messages on any phase change
    _discussion_messages.pop(game_id, None)

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
        # Offset AI answer delays past the reading period
        reading = get_settings().prompt_reading_duration
        for player in ai_players:
            delay = random.uniform(reading + 3, reading + 15)
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
        # Discussion: AI sends 1-2 messages during DISCUSS window (8-26s into REVIEW)
        for player in ai_players:
            n_msgs = random.randint(1, 2)
            for i in range(n_msgs):
                delay = random.uniform(10, 22) + i * random.uniform(2, 5)
                tasks.append(asyncio.create_task(_ai_discussion_task(game_id, player.id, delay)))
        # Votes during VOTE window (26-40s into REVIEW)
        for player in ai_players:
            delay = random.uniform(28, 37)
            tasks.append(asyncio.create_task(_ai_vote_task(game_id, player.id, delay)))

    _ai_tasks[game_id] = tasks


def register_task(game_id: str, task: asyncio.Task) -> None:
    """Register an external background task for cleanup tracking."""
    _ai_tasks.setdefault(game_id, []).append(task)


def cancel_all(game_id: str) -> None:
    """Cancel all pending AI tasks for a game."""
    tasks = _ai_tasks.pop(game_id, [])
    for task in tasks:
        if not task.done():
            task.cancel()


# ---------------------------------------------------------------------------
# Generate-then-lock skeleton
# ---------------------------------------------------------------------------


async def _run_ai_task(
    game_id: str,
    player_id: str,
    delay: float,
    expected_phase: GamePhase,
    generate_fn: Callable[[], Coroutine[Any, Any, Any]],
    apply_fn: _ApplyFn,
    label: str,
) -> None:
    """Shared skeleton for AI task functions.

    1. Sleep for *delay* seconds.
    2. Call *generate_fn* outside the lock (LLM call). Return ``None`` to abort.
    3. Acquire the per-game lock, validate the phase hasn't changed.
    4. Call *apply_fn(cm, session, result)* to update state + broadcast.
    """
    try:
        await asyncio.sleep(delay)
        result = await generate_fn()
        if result is None:
            return

        cm = get_connection_manager()
        lock = cm.get_lock(game_id)
        async with lock:
            repo = get_game_repository()
            session = repo.get(game_id)
            if not session or session.state.phase != expected_phase:
                return
            await apply_fn(cm, session, result)
    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception(f"{label}_error", game_id=game_id, player_id=player_id)


# ---------------------------------------------------------------------------
# AI task functions — thin wrappers around _run_ai_task
# ---------------------------------------------------------------------------


async def _ai_answer_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player answers a prompt after a delay."""

    async def generate() -> tuple[str, list[ModelMessage]] | None:
        history = _get_history(game_id, player_id)
        deps = _build_deps(game_id, player_id)
        if not deps:
            return None
        deps.action_prompt = build_answer_prompt(deps)
        return await generate_answer(deps, history)

    async def apply(cm: Any, session: Any, result: Any) -> None:
        answer_text, updated_history = result
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
                count=answer_count,
                total=total_count,
            ),
        )
        log.info(
            "ai_answer_submitted",
            game_id=game_id,
            player_id=player_id,
            personality=get_personality(game_id, player_id).name,
        )
        if answer_count >= total_count:
            get_timer_manager().cancel_timer(game_id)
            fill_missing_answers(state)
            await do_prompt_complete(game_id, session)

    await _run_ai_task(
        game_id, player_id, delay, GamePhase.PROMPT, generate, apply, "ai_answer_task"
    )


async def _ai_nominate_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player nominates after a delay (Interrogation)."""

    async def generate() -> tuple[str, list[ModelMessage]] | None:
        history = _get_history(game_id, player_id)
        deps = _build_deps(game_id, player_id)
        if not deps:
            return None
        deps.action_prompt = build_nomination_prompt(deps)
        return await generate_nomination(deps, history)

    async def apply(cm: Any, session: Any, result: Any) -> None:
        nominee_alias, updated_history = result
        state = session.state
        round_state = state.current_round
        if not round_state or player_id in round_state.nominations:
            return

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
            "ai_nomination_cast",
            game_id=game_id,
            player_id=player_id,
            target=target.alias,
            personality=get_personality(game_id, player_id).name,
        )
        if nom_count >= total_count:
            get_timer_manager().cancel_timer(game_id)
            await do_nominate_complete(game_id, session)

    await _run_ai_task(
        game_id, player_id, delay, GamePhase.NOMINATE, generate, apply, "ai_nominate_task"
    )


async def _ai_question_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player submits a question after a delay."""

    async def generate() -> tuple[str, list[ModelMessage]] | None:
        # Check eligibility before generating (avoid wasted LLM call)
        repo = get_game_repository()
        session = repo.get(game_id)
        if not session:
            return None
        round_state = session.state.current_round
        if round_state and not is_question_eligible(round_state, player_id):
            return None

        history = _get_history(game_id, player_id)
        deps = _build_deps(game_id, player_id)
        if not deps:
            return None
        deps.action_prompt = build_question_prompt(deps)
        return await generate_question(deps, history)

    async def apply(cm: Any, session: Any, result: Any) -> None:
        question_text, updated_history = result
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
        log.info(
            "ai_question_submitted",
            game_id=game_id,
            player_id=player_id,
            personality=get_personality(game_id, player_id).name,
        )
        if q_count >= expected:
            get_timer_manager().cancel_timer(game_id)
            await do_question_complete(game_id, session)

    await _run_ai_task(
        game_id, player_id, delay, GamePhase.QUESTION, generate, apply, "ai_question_task"
    )


async def _ai_respond_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player responds to a question after a delay."""

    async def generate() -> tuple[str, list[ModelMessage]] | None:
        repo = get_game_repository()
        session = repo.get(game_id)
        if not session or session.state.phase != GamePhase.RESPOND:
            return None

        round_state = session.state.current_round
        if not round_state or not is_response_eligible(round_state, player_id):
            return None

        pending_q = next(
            (q for q in round_state.questions if q.target_id == player_id and q.response is None),
            None,
        )
        question_text = round_state.synthesis or (pending_q.question if pending_q else None)
        if not pending_q or not question_text:
            return None

        history = _get_history(game_id, player_id)
        deps = _build_deps(game_id, player_id)
        if not deps:
            return None
        deps.action_prompt = build_response_prompt(deps, question_text)
        response_text, updated_history = await generate_question_response(
            deps, question_text, history
        )
        return response_text, updated_history

    async def apply(cm: Any, session: Any, result: Any) -> None:
        response_text, updated_history = result
        state = session.state
        round_state = state.current_round
        if not round_state:
            return

        # Re-find the pending question under lock
        target_q = next(
            (q for q in round_state.questions if q.target_id == player_id and q.response is None),
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
        log.info(
            "ai_response_submitted",
            game_id=game_id,
            player_id=player_id,
            personality=get_personality(game_id, player_id).name,
        )
        if responded_count >= expected:
            get_timer_manager().cancel_timer(game_id)
            fill_missing_responses(state)
            await do_respond_complete(game_id, session)

    await _run_ai_task(
        game_id, player_id, delay, GamePhase.RESPOND, generate, apply, "ai_respond_task"
    )


async def _ai_discussion_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player sends a discussion message after a delay."""

    async def generate() -> tuple[str, list[ModelMessage]] | None:
        repo = get_game_repository()
        session = repo.get(game_id)
        if not session or session.state.phase != GamePhase.REVIEW:
            return None
        rs = session.state.current_round
        if not rs:
            return None
        # Check rate limit
        count = rs.discussion_counts.get(player_id, 0)
        if count >= 3:
            return None

        # Build chat context from discussion_messages tracked in-memory
        chat_so_far = _discussion_messages.get(game_id, [])

        history = _get_history(game_id, player_id)
        deps = _build_deps(game_id, player_id)
        if not deps:
            return None
        deps.action_prompt = build_discussion_prompt(deps, chat_so_far or None)
        return await generate_discussion_message(deps, history)

    async def apply(cm, session, result) -> None:
        message_text, updated_history = result
        if not message_text:
            return
        state = session.state
        rs = state.current_round
        if not rs:
            return
        count = rs.discussion_counts.get(player_id, 0)
        if count >= 3:
            return

        rs.discussion_counts[player_id] = count + 1
        _set_history(game_id, player_id, updated_history)

        player = get_player_by_id(state, player_id)
        player_alias = player.alias if player else MISSING_ALIAS

        from schemas.api_models import DiscussionMessageEvent

        msg = message_text[:120]
        await cm.broadcast(
            game_id,
            DiscussionMessageEvent(
                seq=session.next_seq(),
                sender_id=player_id,
                sender_alias=player_alias,
                message=msg,
            ),
        )
        record_discussion_message(game_id, player_alias, msg)
        log.info(
            "ai_discussion_message",
            game_id=game_id,
            player_id=player_id,
            personality=get_personality(game_id, player_id).name,
        )

    await _run_ai_task(
        game_id, player_id, delay, GamePhase.REVIEW, generate, apply, "ai_discussion_task"
    )


async def _ai_vote_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player votes after a delay."""

    async def generate() -> tuple[list[str], list[ModelMessage]] | None:
        history = _get_history(game_id, player_id)
        deps = _build_deps(game_id, player_id)
        if not deps:
            return None
        deps.action_prompt = build_vote_prompt(deps)
        return await decide_vote(deps, history)

    async def apply(cm: Any, session: Any, result: Any) -> None:
        vote_aliases, updated_history = result
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
                count=vote_count,
                total=total_count,
            ),
        )
        log.info(
            "ai_vote_cast",
            game_id=game_id,
            player_id=player_id,
            targets=vote_aliases,
            personality=get_personality(game_id, player_id).name,
        )
        # NO early-complete for REVIEW

    await _run_ai_task(game_id, player_id, delay, GamePhase.REVIEW, generate, apply, "ai_vote_task")


async def on_chain_sub_round(game_id: str, sub_round: int) -> None:
    """Schedule AI word associations for a chain sub-round."""
    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        return

    state = session.state
    ai_players = [p for p in state.players if p.role == PlayerRole.AI and p.is_alive]
    if not ai_players:
        return

    tasks: list[asyncio.Task] = []
    for player in ai_players:
        delay = random.uniform(1, 4)
        tasks.append(asyncio.create_task(_ai_chain_task(game_id, player.id, sub_round, delay)))

    _ai_tasks.setdefault(game_id, []).extend(tasks)


async def _ai_chain_task(game_id: str, player_id: str, sub_round: int, delay: float) -> None:
    """AI player submits a word association after a delay."""
    try:
        await asyncio.sleep(delay)

        repo = get_game_repository()
        session = repo.get(game_id)
        if not session or session.state.phase != GamePhase.CHAIN:
            return

        state = session.state
        rs = state.current_round
        if not rs or rs.current_sub_round != sub_round:
            return

        current_cr = rs.chain_rounds[sub_round]
        if player_id in current_cr.responses:
            return

        seed = current_cr.seed
        personality = get_personality(game_id, player_id)
        chain_history = [cr.seed for cr in rs.chain_rounds]

        # Generate association (lightweight LLM call)
        word = await generate_association(seed, personality, chain_history, game_id=game_id)

        cm = get_connection_manager()
        lock = cm.get_lock(game_id)

        async with lock:
            repo = get_game_repository()
            session = repo.get(game_id)
            if not session or session.state.phase != GamePhase.CHAIN:
                return

            state = session.state
            rs = state.current_round
            if not rs or rs.current_sub_round != sub_round:
                return

            current_cr = rs.chain_rounds[sub_round]
            if player_id in current_cr.responses:
                return

            current_cr.responses[player_id] = word.strip().lower()

            from schemas.api_models import ChainProgressEvent

            alive = get_alive_players(state)
            await cm.broadcast(
                game_id,
                ChainProgressEvent(
                    seq=session.next_seq(),
                    round_index=sub_round,
                    count=len(current_cr.responses),
                    total=len(alive),
                ),
            )

            log.info(
                "ai_chain_word_submitted",
                game_id=game_id,
                player_id=player_id,
                word=word,
                personality=get_personality(game_id, player_id).name,
            )

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("ai_chain_task_error", game_id=game_id, player_id=player_id)


async def on_brain_test_challenge(game_id: str, challenge_index: int) -> None:
    """Schedule AI answers for a brain test challenge."""
    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        return

    state = session.state
    ai_players = [p for p in state.players if p.role == PlayerRole.AI and p.is_alive]
    if not ai_players:
        return

    tasks: list[asyncio.Task] = []
    for player in ai_players:
        delay = random.uniform(1.5, 6)
        tasks.append(
            asyncio.create_task(_ai_brain_test_task(game_id, player.id, challenge_index, delay))
        )

    _ai_tasks.setdefault(game_id, []).extend(tasks)


async def _ai_brain_test_task(
    game_id: str, player_id: str, challenge_index: int, delay: float
) -> None:
    """AI player submits a brain test answer after a delay."""
    try:
        await asyncio.sleep(delay)

        repo = get_game_repository()
        session = repo.get(game_id)
        if not session or session.state.phase != GamePhase.BRAIN_TEST:
            return

        state = session.state
        rs = state.current_round
        if not rs or challenge_index >= len(rs.brain_challenges):
            return

        ch = rs.brain_challenges[challenge_index]
        if player_id in ch.responses:
            return

        personality = get_personality(game_id, player_id)

        from backend.llm.agents import generate_brain_test_answer

        answer = await generate_brain_test_answer(ch.question, personality.name, game_id=game_id)
        if not answer:
            answer = "I don't know"

        cm = get_connection_manager()
        lock = cm.get_lock(game_id)

        async with lock:
            session = repo.get(game_id)
            if not session or session.state.phase != GamePhase.BRAIN_TEST:
                return
            rs = session.state.current_round
            if not rs or challenge_index >= len(rs.brain_challenges):
                return
            ch = rs.brain_challenges[challenge_index]
            if player_id in ch.responses:
                return
            ch.responses[player_id] = answer.strip()

            log.info(
                "ai_brain_test_answer",
                game_id=game_id,
                player_id=player_id,
                challenge_index=challenge_index,
            )

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception(
            "ai_brain_test_error",
            game_id=game_id,
            player_id=player_id,
        )


def get_narrator_history(game_id: str) -> list[ModelMessage]:
    """Get narrator conversation history for a game."""
    return _narrator_history.get(game_id, [])


def set_narrator_history(game_id: str, history: list[ModelMessage]) -> None:
    """Store updated narrator conversation history for a game."""
    _narrator_history[game_id] = history


def cleanup_game(game_id: str) -> None:
    """Clean up all AI state for a game."""
    cancel_all(game_id)
    _personality_map.pop(game_id, None)
    _conversation_history.pop(game_id, None)
    _narrator_history.pop(game_id, None)
    _discussion_messages.pop(game_id, None)
