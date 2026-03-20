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
    get_timer_manager,
)
from backend.llm.agents import (
    AIPlayerDeps,
    generate_answer,
)
from backend.llm.personalities import PERSONALITIES, Personality
from backend.llm.prompts import (
    build_answer_prompt,
    build_signal_transform_prompt,
)
from backend.services.game_logic import (
    fill_missing_answers,
    get_player_by_id,
)
from schemas.api_models import (
    AnswerSubmittedEvent,
    VoteSubmittedEvent,
)
from schemas.game_state import GamePhase, PlayerRole, RoundType

# Type alias for apply callbacks used in _run_ai_task
_ApplyFn = Callable[..., Coroutine[Any, Any, None]]

log = structlog.get_logger(__name__)

# Store personality assignments per game: game_id -> {player_id -> Personality}
_personality_map: dict[str, dict[str, Personality]] = {}

# Store active AI tasks per game
_ai_tasks: dict[str, list[asyncio.Task]] = {}

# Store conversation history per AI player: game_id -> {player_id -> messages}
_conversation_history: dict[str, dict[str, list[ModelMessage]]] = {}


def assign_personalities(game_id: str, ai_player_ids: list[str]) -> None:
    """Assign random personalities to AI players (no duplicates)."""
    from backend.llm.agents import init_narrator

    personalities = random.sample(PERSONALITIES, min(len(ai_player_ids), len(PERSONALITIES)))
    _personality_map[game_id] = {
        pid: personalities[i % len(personalities)] for i, pid in enumerate(ai_player_ids)
    }
    _conversation_history[game_id] = {pid: [] for pid in ai_player_ids}
    init_narrator(game_id)
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
    if not player:
        return None

    personality = get_personality(game_id, player_id)
    all_aliases = [p.alias for p in state.players]

    all_answers: dict[str, str] = {}
    current_prompt = ""
    round_type: RoundType = RoundType.TASK
    my_answer: str | None = None

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

    return AIPlayerDeps(
        personality=personality,
        player_alias=player.alias,
        current_prompt=current_prompt,
        all_answers=all_answers,
        players=all_aliases,
        round_number=state.round_number,
        round_type=round_type,
        my_answer=my_answer,
        action_prompt=action_prompt,
    )


# ---------------------------------------------------------------------------
# Phase scheduling
# ---------------------------------------------------------------------------


async def on_phase_change(game_id: str, phase: GamePhase) -> None:
    """Called when a phase changes. Schedules AI actions for the new phase.

    Only handles PROMPT (framework phase). ACTIVE phase AI is handled by
    minigame handlers via on_active_start().
    """
    cancel_all(game_id)

    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        return

    state = session.state
    ai_players = [p for p in state.players if p.role == PlayerRole.AI]

    if not ai_players:
        return

    tasks: list[asyncio.Task] = []

    if phase == GamePhase.PROMPT:
        for player in ai_players:
            delay = random.uniform(3, 20)
            tasks.append(asyncio.create_task(_ai_answer_task(game_id, player.id, delay)))

    _ai_tasks.setdefault(game_id, []).extend(tasks)


def register_task(game_id: str, task: asyncio.Task) -> None:
    """Register an external background task for cleanup tracking."""
    _ai_tasks.setdefault(game_id, []).append(task)


async def schedule_ai_votes(game_id: str) -> None:
    """Schedule AI vote tasks for a task/matchup round."""
    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        return

    ai_players = [p for p in session.state.players if p.role == PlayerRole.AI]
    if not ai_players:
        return

    tasks: list[asyncio.Task] = []
    for player in ai_players:
        delay = random.uniform(2, 8)
        tasks.append(asyncio.create_task(_ai_vote_task(game_id, player.id, delay)))
    _ai_tasks.setdefault(game_id, []).extend(tasks)


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

        if deps.round_type == RoundType.SIGNAL:
            # Signal: transform the secret phrase under the constraint
            repo = get_game_repository()
            session = repo.get(game_id)
            if not session or not session.state.current_round:
                return None
            rs = session.state.current_round
            phrase = rs.signal_phrases.get(player_id, "")
            constraint = rs.signal_constraint
            deps.action_prompt = build_signal_transform_prompt(phrase, constraint)
        else:
            deps.action_prompt = build_answer_prompt(deps)

        return await generate_answer(deps, history)

    async def apply(cm: Any, session: Any, result: Any) -> None:
        from backend.services.transitions import do_prompt_complete

        answer_text, updated_history = result
        state = session.state
        if not state.current_round or player_id in state.current_round.answers:
            return

        state.current_round.answers[player_id] = answer_text
        _set_history(game_id, player_id, updated_history)

        answer_count = len(state.current_round.answers)
        total_count = len(state.players)

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


async def _ai_vote_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player votes in gallery vote phase after a delay."""

    async def generate() -> str | None:
        """Try LLM vote, fall back to random."""
        repo = get_game_repository()
        session = repo.get(game_id)
        if not session:
            return None
        state = session.state
        if not state.current_round:
            return None

        # Build lookups in a single pass
        answers_by_alias: dict[str, str] = {}
        alias_to_id: dict[str, str] = {}
        other_ids: list[str] = []
        for p in state.players:
            alias_to_id[p.alias] = p.id
            if p.id != player_id:
                other_ids.append(p.id)
                answer = state.current_round.answers.get(p.id)
                if answer:
                    answers_by_alias[p.alias] = answer

        if not other_ids:
            return None

        # Try LLM vote
        try:
            from backend.llm.agents import decide_gallery_vote

            voted_alias = await decide_gallery_vote(
                state.current_round.prompt_text,
                answers_by_alias,
                game_id=game_id,
            )
            if voted_alias:
                voted_id = alias_to_id.get(voted_alias)
                if voted_id and voted_id != player_id:
                    return voted_id
        except Exception:
            log.warning("ai_vote_llm_fallback", game_id=game_id, player_id=player_id)

        # Fallback: random vote (any non-self player)
        return random.choice(other_ids)

    async def apply(cm: Any, session: Any, result: Any) -> None:
        from backend.services.transitions import do_active_complete

        voted_for_id = result
        state = session.state
        if not state.current_round:
            return

        state.current_round.gallery_votes[player_id] = voted_for_id

        vote_count = len(state.current_round.gallery_votes)
        total = len(state.players)

        await cm.broadcast(
            game_id,
            VoteSubmittedEvent(
                seq=session.next_seq(),
                player_id=player_id,
                vote_count=vote_count,
                total=total,
            ),
        )
        log.info(
            "ai_vote_cast",
            game_id=game_id,
            player_id=player_id,
            voted_for=voted_for_id,
        )

        # Early complete: all voted
        if vote_count >= total:
            get_timer_manager().cancel_timer(game_id)
            await do_active_complete(game_id, session)

    await _run_ai_task(game_id, player_id, delay, GamePhase.ACTIVE, generate, apply, "ai_vote_task")


async def _schedule_ai_sub_tasks(
    game_id: str,
    task_fn: Callable[..., Coroutine[Any, Any, None]],
    extra_args: tuple,
    delay_range: tuple[float, float],
) -> None:
    """Schedule per-AI-player tasks with random delays."""
    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        return
    ai_players = [p for p in session.state.players if p.role == PlayerRole.AI]
    if not ai_players:
        return
    tasks = [
        asyncio.create_task(task_fn(game_id, p.id, *extra_args, random.uniform(*delay_range)))
        for p in ai_players
    ]
    _ai_tasks.setdefault(game_id, []).extend(tasks)


async def on_brain_test_challenge(game_id: str, challenge_index: int) -> None:
    """Schedule AI answers for a brain test challenge."""
    await _schedule_ai_sub_tasks(game_id, _ai_brain_test_task, (challenge_index,), (2, 8))


async def _ai_brain_test_task(
    game_id: str, player_id: str, challenge_index: int, delay: float
) -> None:
    """AI player selects an option for a brain test challenge after a delay."""
    try:
        await asyncio.sleep(delay)

        repo = get_game_repository()
        session = repo.get(game_id)
        if not session or session.state.phase != GamePhase.ACTIVE:
            return

        state = session.state
        rs = state.current_round
        if not rs or challenge_index >= len(rs.brain_challenges):
            return

        ch = rs.brain_challenges[challenge_index]
        if player_id in ch.responses:
            return

        # AI selects from options via LLM
        from backend.llm.agents import generate_brain_test_answer

        selected = await generate_brain_test_answer(ch.question, ch.options, game_id=game_id)

        cm = get_connection_manager()
        lock = cm.get_lock(game_id)

        async with lock:
            session = repo.get(game_id)
            if not session or session.state.phase != GamePhase.ACTIVE:
                return
            rs = session.state.current_round
            if not rs or challenge_index >= len(rs.brain_challenges):
                return
            ch = rs.brain_challenges[challenge_index]
            if player_id in ch.responses:
                return
            ch.responses[player_id] = selected

            log.info(
                "ai_brain_test_answer",
                game_id=game_id,
                player_id=player_id,
                challenge_index=challenge_index,
                selected_index=selected,
            )

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception(
            "ai_brain_test_error",
            game_id=game_id,
            player_id=player_id,
        )


async def on_wager_guess(game_id: str, question_index: int) -> None:
    """Schedule AI guess tasks for a wager question."""
    await _schedule_ai_sub_tasks(game_id, _ai_wager_guess_task, (question_index,), (2, 10))


async def _ai_wager_guess_task(
    game_id: str, player_id: str, question_index: int, delay: float
) -> None:
    """AI player submits a guess for a wager question after a delay."""
    try:
        await asyncio.sleep(delay)

        repo = get_game_repository()
        session = repo.get(game_id)
        if not session or session.state.phase != GamePhase.ACTIVE:
            return

        state = session.state
        rs = state.current_round
        if not rs or rs.round_type != RoundType.WAGER:
            return
        if question_index >= len(rs.wager_questions):
            return

        q = rs.wager_questions[question_index]
        if player_id in q.guesses:
            return

        # Build deps and generate guess via character agent
        action_prompt = (
            f"Estimate: {q.question} (range {q.range_min}-{q.range_max} {q.unit}). "
            f"Give your best numerical estimate."
        )
        deps = _build_deps(game_id, player_id, action_prompt)
        if not deps:
            return

        history = _get_history(game_id, player_id)

        from backend.llm.agents import generate_wager_guess

        value, updated_history = await generate_wager_guess(
            deps, history, range_min=q.range_min, range_max=q.range_max
        )

        # Clamp to range
        value = max(q.range_min, min(q.range_max, value))

        cm = get_connection_manager()
        lock = cm.get_lock(game_id)

        async with lock:
            session = repo.get(game_id)
            if not session or session.state.phase != GamePhase.ACTIVE:
                return
            rs = session.state.current_round
            if not rs or rs.round_type != RoundType.WAGER:
                return
            if question_index >= len(rs.wager_questions):
                return
            q = rs.wager_questions[question_index]
            if player_id in q.guesses:
                return
            q.guesses[player_id] = value
            _set_history(game_id, player_id, updated_history)

            log.info(
                "ai_wager_guess",
                game_id=game_id,
                player_id=player_id,
                question_index=question_index,
                value=value,
            )

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception(
            "ai_wager_guess_error",
            game_id=game_id,
            player_id=player_id,
        )


async def on_wager_bet(game_id: str, question_index: int) -> None:
    """Schedule AI bet tasks for a wager question."""
    await _schedule_ai_sub_tasks(game_id, _ai_wager_bet_task, (question_index,), (1, 8))


async def _ai_wager_bet_task(
    game_id: str, player_id: str, question_index: int, delay: float
) -> None:
    """AI player places a bet on a wager question after a delay."""
    try:
        await asyncio.sleep(delay)

        repo = get_game_repository()
        session = repo.get(game_id)
        if not session or session.state.phase != GamePhase.ACTIVE:
            return

        state = session.state
        rs = state.current_round
        if not rs or rs.round_type != RoundType.WAGER:
            return
        if question_index >= len(rs.wager_questions):
            return

        q = rs.wager_questions[question_index]
        if player_id in q.bets:
            return

        # Build alias map and guesses-by-alias for the prompt
        alias_to_id: dict[str, str] = {}
        id_to_alias: dict[str, str] = {}
        for p in state.players:
            alias_to_id[p.alias] = p.id
            id_to_alias[p.id] = p.alias

        guesses_by_alias = {id_to_alias.get(pid, pid): val for pid, val in q.guesses.items()}
        guesses_text = ", ".join(f"{alias}: {val}" for alias, val in guesses_by_alias.items())

        action_prompt = (
            f"Question: {q.question} (range {q.range_min}-{q.range_max} {q.unit}). "
            f"Everyone's guesses: {guesses_text}. "
            f"Whose guess is closest to the truth? Reply with the alias."
        )
        deps = _build_deps(game_id, player_id, action_prompt)
        if not deps:
            return

        history = _get_history(game_id, player_id)

        from backend.llm.agents import generate_wager_bet

        target_alias, updated_history = await generate_wager_bet(deps, history)

        # Resolve alias → player_id (case-insensitive partial match)
        target_id: str | None = None
        if target_alias:
            stripped = target_alias.strip().upper()
            for alias, pid in alias_to_id.items():
                if alias.upper() in stripped or stripped in alias.upper():
                    target_id = pid
                    break

        # Validate target has a guess
        if not target_id or target_id not in q.guesses:
            # Fallback: random player who has a guess
            guessers = list(q.guesses.keys())
            if not guessers:
                return
            target_id = random.choice(guessers)

        cm = get_connection_manager()
        lock = cm.get_lock(game_id)

        async with lock:
            session = repo.get(game_id)
            if not session or session.state.phase != GamePhase.ACTIVE:
                return
            rs = session.state.current_round
            if not rs or rs.round_type != RoundType.WAGER:
                return
            if question_index >= len(rs.wager_questions):
                return
            q = rs.wager_questions[question_index]
            if player_id in q.bets:
                return
            if target_id not in q.guesses:
                return
            q.bets[player_id] = target_id
            _set_history(game_id, player_id, updated_history)

            log.info(
                "ai_wager_bet",
                game_id=game_id,
                player_id=player_id,
                question_index=question_index,
                target=target_id,
            )

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception(
            "ai_wager_bet_error",
            game_id=game_id,
            player_id=player_id,
        )


async def on_signal_sub_round(game_id: str, sub_round_index: int, featured_player_id: str) -> None:
    """Schedule AI guess tasks for a Signal sub-round."""
    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        return

    ai_players = [
        p for p in session.state.players if p.role == PlayerRole.AI and p.id != featured_player_id
    ]
    if not ai_players:
        return

    tasks: list[asyncio.Task] = []
    for player in ai_players:
        delay = random.uniform(2, 8)
        task = asyncio.create_task(
            _ai_signal_guess_task(game_id, player.id, featured_player_id, sub_round_index, delay)
        )
        tasks.append(task)
    _ai_tasks.setdefault(game_id, []).extend(tasks)


async def _ai_signal_guess_task(
    game_id: str,
    player_id: str,
    featured_player_id: str,
    sub_round_index: int,
    delay: float,
) -> None:
    """AI player guesses the original phrase in a Signal sub-round."""

    async def generate() -> str | None:
        repo = get_game_repository()
        session = repo.get(game_id)
        if not session:
            return None
        rs = session.state.current_round
        if not rs or rs.current_sub_round != sub_round_index:
            return None
        existing = rs.signal_guesses.get(featured_player_id, {})
        if player_id in existing:
            return None

        transformation = rs.answers.get(featured_player_id, "")
        constraint = rs.signal_constraint

        from backend.llm.agents import generate_signal_guess

        return await generate_signal_guess(transformation, constraint, game_id=game_id)

    async def apply(cm: Any, session: Any, result: Any) -> None:
        rs = session.state.current_round
        if not rs or rs.current_sub_round != sub_round_index:
            return
        if featured_player_id not in rs.signal_guesses:
            rs.signal_guesses[featured_player_id] = {}
        rs.signal_guesses[featured_player_id][player_id] = result
        log.info(
            "ai_signal_guess",
            game_id=game_id,
            player_id=player_id,
            sub_round_index=sub_round_index,
        )

    await _run_ai_task(
        game_id, player_id, delay, GamePhase.ACTIVE, generate, apply, "ai_signal_guess"
    )


def cleanup_game(game_id: str) -> None:
    """Clean up all AI state for a game."""
    from backend.llm.agents import cleanup_narrator

    cancel_all(game_id)
    _personality_map.pop(game_id, None)
    _conversation_history.pop(game_id, None)
    cleanup_narrator(game_id)
