"""AI player scheduler — generates actions with random delays using generate-then-lock."""

from __future__ import annotations

import asyncio
import random

import structlog

from backend.api.deps import get_connection_manager, get_game_repository, get_settings
from backend.llm.agents import AIPlayerDeps, decide_vote, generate_answer, generate_chat_message
from backend.llm.personalities import PERSONALITIES, Personality
from backend.services.game_logic import get_alive_players, make_phase_changed_event
from schemas.api_models import AnswerSubmittedEvent, ChatMessageEvent, VoteCastEvent
from schemas.game_state import ChatMessage, GamePhase, PlayerRole

log = structlog.get_logger()

# Store personality assignments per game: game_id -> {player_id -> Personality}
_personality_map: dict[str, dict[str, Personality]] = {}

# Store active AI tasks per game
_ai_tasks: dict[str, list[asyncio.Task]] = {}


def assign_personalities(game_id: str, ai_player_ids: list[str]) -> None:
    """Assign random personalities to AI players (no duplicates)."""
    personalities = random.sample(PERSONALITIES, min(len(ai_player_ids), len(PERSONALITIES)))
    _personality_map[game_id] = {
        pid: personalities[i % len(personalities)]
        for i, pid in enumerate(ai_player_ids)
    }
    log.info(
        "ai_personalities_assigned", game_id=game_id,
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
    player = next((p for p in state.players if p.id == player_id), None)
    if not player or not player.is_alive:
        return None

    personality = get_personality(game_id, player_id)
    alive = get_alive_players(state)
    alive_aliases = [p.alias for p in alive]

    all_answers: dict[str, str] = {}
    chat_history: list[dict[str, str]] = []
    current_prompt = ""

    if state.current_round:
        current_prompt = state.current_round.prompt_text
        player_map = {p.id: p for p in state.players}
        for pid, answer in state.current_round.answers.items():
            p = player_map.get(pid)
            if p:
                all_answers[p.alias] = answer
        for msg in state.current_round.messages:
            chat_history.append({"alias": msg.player_alias, "text": msg.text})

    return AIPlayerDeps(
        personality=personality,
        player_alias=player.alias,
        current_prompt=current_prompt,
        all_answers=all_answers,
        chat_history=chat_history,
        alive_players=alive_aliases,
        round_number=state.round_number,
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

    elif phase == GamePhase.CHAT:
        for player in ai_players:
            num_messages = random.randint(2, 5)
            tasks.append(asyncio.create_task(_ai_chat_task(game_id, player.id, num_messages)))

    elif phase == GamePhase.VOTE:
        for player in ai_players:
            delay = random.uniform(2, 10)
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

            await cm.broadcast(game_id, AnswerSubmittedEvent(
                seq=session.next_seq(),
                player_id=player_id,
                answer_count=answer_count,
                total_count=total_count,
            ))

            log.info("ai_answer_submitted", game_id=game_id, player_id=player_id)

            # Check if all answered — trigger early transition
            if answer_count >= total_count:
                from backend.api.deps import get_timer_manager
                from backend.services.game_logic import transition_to_chat
                get_timer_manager().cancel_timer(game_id)
                transition_to_chat(state, settings.chat_duration)
                await cm.broadcast(game_id, make_phase_changed_event(
                    state, session.next_seq(), answers=state.current_round.answers,
                ))
                need_chat_timer = True
            else:
                need_chat_timer = False

        if need_chat_timer:
            from backend.api.routes.actions import _start_phase_timer
            await _start_phase_timer(game_id, GamePhase.CHAT)
            await on_phase_change(game_id, GamePhase.CHAT)

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("ai_answer_task_error", game_id=game_id, player_id=player_id)


async def _ai_chat_task(game_id: str, player_id: str, num_messages: int) -> None:
    """AI player sends chat messages at random intervals."""
    try:
        for i in range(num_messages):
            await asyncio.sleep(random.uniform(5, 25))

            deps = _build_deps(game_id, player_id)
            if not deps:
                return
            message_text = await generate_chat_message(deps)

            cm = get_connection_manager()
            repo = get_game_repository()
            lock = cm.get_lock(game_id)

            async with lock:
                session = repo.get(game_id)
                if not session or session.state.phase != GamePhase.CHAT:
                    return

                state = session.state
                if not state.current_round:
                    return

                player = next((p for p in state.players if p.id == player_id), None)
                if not player:
                    return

                state.current_round.messages.append(ChatMessage(
                    player_id=player_id,
                    player_alias=player.alias,
                    text=message_text,
                ))

                await cm.broadcast(game_id, ChatMessageEvent(
                    seq=session.next_seq(),
                    player_id=player_id,
                    player_alias=player.alias,
                    text=message_text,
                ))

                log.info("ai_chat_sent", game_id=game_id, player_id=player_id, msg_num=i + 1)

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("ai_chat_task_error", game_id=game_id, player_id=player_id)


async def _ai_vote_task(game_id: str, player_id: str, delay: float) -> None:
    """AI player votes after a delay."""
    try:
        await asyncio.sleep(delay)

        deps = _build_deps(game_id, player_id)
        if not deps:
            return
        vote_alias = await decide_vote(deps)

        cm = get_connection_manager()
        repo = get_game_repository()
        lock = cm.get_lock(game_id)

        async with lock:
            session = repo.get(game_id)
            if not session or session.state.phase != GamePhase.VOTE:
                return

            state = session.state
            if not state.current_round or player_id in state.current_round.votes:
                return

            # Resolve alias to player_id
            target = next(
                (p for p in state.players if p.alias == vote_alias and p.is_alive),
                None,
            )
            if not target:
                candidates = [p for p in state.players if p.is_alive and p.id != player_id]
                if not candidates:
                    return
                target = random.choice(candidates)

            state.current_round.votes[player_id] = target.id

            alive = get_alive_players(state)
            vote_count = len(state.current_round.votes)
            total_count = len(alive)

            await cm.broadcast(game_id, VoteCastEvent(
                seq=session.next_seq(),
                voter_id=player_id,
                vote_count=vote_count,
                total_count=total_count,
            ))

            log.info("ai_vote_cast", game_id=game_id, player_id=player_id, target=target.alias)

            if vote_count >= total_count:
                from backend.api.deps import get_timer_manager
                from backend.api.routes.actions import _do_vote_resolution
                get_timer_manager().cancel_timer(game_id)
                await _do_vote_resolution(game_id, session)

    except asyncio.CancelledError:
        pass
    except Exception:
        log.exception("ai_vote_task_error", game_id=game_id, player_id=player_id)


def cleanup_game(game_id: str) -> None:
    """Clean up all AI state for a game."""
    cancel_all(game_id)
    _personality_map.pop(game_id, None)
