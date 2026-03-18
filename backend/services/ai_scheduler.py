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
    generate_answer,
)
from backend.llm.personalities import PERSONALITIES, Personality
from backend.llm.prompts import (
    build_answer_prompt,
)
from backend.services.game_logic import (
    fill_missing_answers,
    get_player_by_id,
)
from backend.services.transitions import (
    do_prompt_complete,
)
from schemas.api_models import (
    AnswerSubmittedEvent,
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

# Store narrator message history per game: game_id -> messages
_narrator_history: dict[str, list[ModelMessage]] = {}


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

        # For matchup Task rounds, use the player's specific matchup prompt
        if rs.matchups:
            for m in rs.matchups:
                if player_id in m.pair:
                    current_prompt = m.prompt_text
                    break

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
    """Called when a phase changes. Schedules AI actions for the new phase."""
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
        # Offset AI answer delays past the reading period
        reading = get_settings().prompt_reading_duration
        for player in ai_players:
            delay = random.uniform(reading + 5, reading + 25)
            tasks.append(asyncio.create_task(_ai_answer_task(game_id, player.id, delay)))

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
        # Skip bye players — they don't answer in matchup rounds
        repo = get_game_repository()
        session = repo.get(game_id)
        if (
            session
            and session.state.current_round
            and session.state.current_round.bye_player_id == player_id
        ):
            return None
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

        answer_count = len(state.current_round.answers)
        total_count = len(state.players)
        # Exclude bye player from total count in matchup rounds
        if state.current_round.bye_player_id:
            total_count -= 1

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


async def on_brain_test_challenge(game_id: str, challenge_index: int) -> None:
    """Schedule AI answers for a brain test challenge."""
    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        return

    state = session.state
    ai_players = [p for p in state.players if p.role == PlayerRole.AI]
    if not ai_players:
        return

    tasks: list[asyncio.Task] = []
    for player in ai_players:
        delay = random.uniform(2, 8)
        tasks.append(
            asyncio.create_task(_ai_brain_test_task(game_id, player.id, challenge_index, delay))
        )

    _ai_tasks.setdefault(game_id, []).extend(tasks)


async def _ai_brain_test_task(
    game_id: str, player_id: str, challenge_index: int, delay: float
) -> None:
    """AI player selects an option for a brain test challenge after a delay."""
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

        # AI selects from options via LLM
        from backend.llm.agents import generate_brain_test_answer

        selected = await generate_brain_test_answer(ch.question, ch.options, game_id=game_id)

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


async def on_matchup_challenge(game_id: str, matchup_index: int) -> None:
    """Schedule AI votes for a matchup challenge (non-pair AI players vote randomly)."""
    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        return

    state = session.state
    rs = state.current_round
    if not rs or matchup_index >= len(rs.matchups):
        return

    matchup = rs.matchups[matchup_index]
    pair_ids = set(matchup.pair)

    # AI players not in the pair can vote
    ai_voters = [p for p in state.players if p.role == PlayerRole.AI and p.id not in pair_ids]
    if not ai_voters:
        return

    tasks: list[asyncio.Task] = []
    for player in ai_voters:
        delay = random.uniform(2, 8)
        tasks.append(
            asyncio.create_task(_ai_matchup_vote_task(game_id, player.id, matchup_index, delay))
        )

    _ai_tasks.setdefault(game_id, []).extend(tasks)


async def _ai_matchup_vote_task(
    game_id: str, player_id: str, matchup_index: int, delay: float
) -> None:
    """AI player votes on a matchup after a delay."""
    try:
        await asyncio.sleep(delay)

        cm = get_connection_manager()
        lock = cm.get_lock(game_id)

        async with lock:
            repo = get_game_repository()
            session = repo.get(game_id)
            if not session or session.state.phase != GamePhase.MATCHUP:
                return
            rs = session.state.current_round
            if not rs or matchup_index >= len(rs.matchups):
                return
            matchup = rs.matchups[matchup_index]
            if player_id in matchup.votes:
                return

            # Random choice: 0=left, 1=right
            choice = random.randint(0, 1)
            matchup.votes[player_id] = choice

            log.info(
                "ai_matchup_vote",
                game_id=game_id,
                player_id=player_id,
                matchup_index=matchup_index,
                choice=choice,
            )

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception(
            "ai_matchup_vote_error",
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
