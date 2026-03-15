"""In-game action routes — join, start, answer, chat, vote."""

from __future__ import annotations

import random
import uuid

from fastapi import APIRouter, HTTPException

from backend.api.deps import get_connection_manager, get_game_repository, get_settings, get_timer_manager
from backend.services.game_logic import (
    build_state_sync,
    check_game_over,
    get_alive_players,
    make_game_over_event,
    resolve_votes,
    transition_to_chat,
    transition_to_elimination,
    transition_to_prompt,
    transition_to_vote,
    validate_player_alive,
)
from schemas.aliases import generate_aliases
from schemas.api_models import (
    AnswerSubmittedEvent,
    CastVoteRequest,
    ChatMessageEvent,
    JoinGameRequest,
    JoinGameResponse,
    PhaseChangedEvent,
    PlayerJoinedEvent,
    SendChatRequest,
    StartGameRequest,
    SubmitAnswerRequest,
    VoteCastEvent,
)
from schemas.game_state import ChatMessage, GamePhase, Player, PlayerRole

router = APIRouter()


async def _start_phase_timer(game_id: str, phase: GamePhase) -> None:
    """Start the timer for the current phase. On expiry, transition to next phase."""
    settings = get_settings()
    tm = get_timer_manager()

    durations = {
        GamePhase.PROMPT: settings.prompt_duration,
        GamePhase.CHAT: settings.chat_duration,
        GamePhase.VOTE: settings.vote_duration,
        GamePhase.ELIMINATION: settings.elimination_duration,
    }
    duration = durations.get(phase)
    if not duration:
        return

    async def on_timer_expire():
        await _handle_phase_expiry(game_id, phase)

    tm.start_timer(game_id, duration, on_timer_expire)


async def _handle_phase_expiry(game_id: str, expired_phase: GamePhase) -> None:
    """Handle timer expiry — transition to next phase under lock."""
    cm = get_connection_manager()
    repo = get_game_repository()
    settings = get_settings()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session or session.state.phase != expired_phase:
            return  # Phase already changed

        state = session.state

        if expired_phase == GamePhase.PROMPT:
            # Fill in "[no response]" for players who didn't answer
            alive = get_alive_players(state)
            for p in alive:
                if state.current_round and p.id not in state.current_round.answers:
                    state.current_round.answers[p.id] = "[no response]"

            transition_to_chat(state, settings.chat_duration)
            event = PhaseChangedEvent(
                seq=session.next_seq(),
                phase=state.phase.value,
                round_number=state.round_number,
                phase_deadline=state.phase_deadline.isoformat() if state.phase_deadline else None,
                answers=state.current_round.answers if state.current_round else {},
            )
            await cm.broadcast(game_id, event)
            await _start_phase_timer(game_id, GamePhase.CHAT)

        elif expired_phase == GamePhase.CHAT:
            transition_to_vote(state, settings.vote_duration)
            event = PhaseChangedEvent(
                seq=session.next_seq(),
                phase=state.phase.value,
                round_number=state.round_number,
                phase_deadline=state.phase_deadline.isoformat() if state.phase_deadline else None,
            )
            await cm.broadcast(game_id, event)
            await _start_phase_timer(game_id, GamePhase.VOTE)

        elif expired_phase == GamePhase.VOTE:
            await _do_vote_resolution(game_id, session)

        elif expired_phase == GamePhase.ELIMINATION:
            await _after_elimination(game_id, session)


async def _do_vote_resolution(game_id: str, session) -> None:
    """Resolve votes, show elimination, check game over."""
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state

    state, vote_results, elimination = resolve_votes(state, session.next_seq)
    await cm.broadcast(game_id, vote_results)

    transition_to_elimination(state, settings.elimination_duration)
    await cm.broadcast(game_id, elimination)
    await _start_phase_timer(game_id, GamePhase.ELIMINATION)


async def _after_elimination(game_id: str, session) -> None:
    """After elimination reveal, check game over or start next round."""
    cm = get_connection_manager()
    settings = get_settings()
    state = session.state

    winner = check_game_over(state)
    if winner:
        state.phase = GamePhase.GAME_OVER
        state.winner = winner
        state.phase_deadline = None
        event = make_game_over_event(state, winner, session.next_seq)
        await cm.broadcast(game_id, event)
        return

    # Next round
    transition_to_prompt(state, settings.prompt_duration)
    event = PhaseChangedEvent(
        seq=session.next_seq(),
        phase=state.phase.value,
        round_number=state.round_number,
        prompt_text=state.current_round.prompt_text if state.current_round else None,
        prompt_category=state.current_round.prompt_category if state.current_round else None,
        phase_deadline=state.phase_deadline.isoformat() if state.phase_deadline else None,
    )
    await cm.broadcast(game_id, event)
    await _start_phase_timer(game_id, GamePhase.PROMPT)


@router.post("/{game_id}/join", response_model=JoinGameResponse)
async def join_game(game_id: str, req: JoinGameRequest):
    """Join a game lobby."""
    cm = get_connection_manager()
    repo = get_game_repository()
    settings = get_settings()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="Game not found")

        state = session.state
        if state.phase != GamePhase.LOBBY:
            raise HTTPException(status_code=400, detail="Game already in progress")

        if len(state.players) >= settings.max_players:
            raise HTTPException(status_code=400, detail="Game is full")

        player_id = uuid.uuid4().hex[:12]
        existing_aliases = {p.alias for p in state.players}
        aliases = generate_aliases(1, existing_aliases)
        alias = aliases[0]

        is_host = len(state.players) == 0  # First player is host
        player = Player(
            id=player_id,
            alias=alias,
            role=PlayerRole.HUMAN,
            is_host=is_host,
        )
        state.players.append(player)

        event = PlayerJoinedEvent(
            seq=session.next_seq(),
            player_id=player_id,
            alias=alias,
            player_count=len(state.players),
        )
        await cm.broadcast(game_id, event)

    return JoinGameResponse(player_id=player_id, alias=alias, game_id=game_id)


@router.post("/{game_id}/start")
async def start_game(game_id: str, req: StartGameRequest):
    """Start the game (host only). Spawns AI players and begins round 1."""
    cm = get_connection_manager()
    repo = get_game_repository()
    settings = get_settings()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="Game not found")

        state = session.state
        if state.phase != GamePhase.LOBBY:
            raise HTTPException(status_code=400, detail="Game already started")

        # Verify host
        host = next((p for p in state.players if p.id == req.player_id and p.is_host), None)
        if not host:
            raise HTTPException(status_code=403, detail="Only the host can start the game")

        human_count = len([p for p in state.players if p.role == PlayerRole.HUMAN])
        if human_count < settings.min_humans:
            raise HTTPException(
                status_code=400,
                detail=f"Need at least {settings.min_humans} human players",
            )

        # Spawn AI players
        ai_count = min(max(req.ai_count, settings.min_ai), settings.max_ai)
        existing_aliases = {p.alias for p in state.players}
        ai_aliases = generate_aliases(ai_count, existing_aliases)

        from backend.llm.personalities import PERSONALITIES

        personalities = random.sample(PERSONALITIES, min(ai_count, len(PERSONALITIES)))

        for i in range(ai_count):
            ai_player = Player(
                id=f"ai-{uuid.uuid4().hex[:8]}",
                alias=ai_aliases[i],
                role=PlayerRole.AI,
                is_connected=True,
            )
            state.players.append(ai_player)

            # Broadcast AI join
            event = PlayerJoinedEvent(
                seq=session.next_seq(),
                player_id=ai_player.id,
                alias=ai_player.alias,
                player_count=len(state.players),
            )
            await cm.broadcast(game_id, event)

        # Calculate max rounds
        state.max_rounds = max(3, human_count + 1)

        # Transition to first prompt
        transition_to_prompt(state, settings.prompt_duration)
        event = PhaseChangedEvent(
            seq=session.next_seq(),
            phase=state.phase.value,
            round_number=state.round_number,
            prompt_text=state.current_round.prompt_text if state.current_round else None,
            prompt_category=state.current_round.prompt_category if state.current_round else None,
            phase_deadline=state.phase_deadline.isoformat() if state.phase_deadline else None,
        )
        await cm.broadcast(game_id, event)

    # Start phase timer OUTSIDE the lock
    await _start_phase_timer(game_id, GamePhase.PROMPT)

    return {"status": "started", "round": state.round_number}


@router.post("/{game_id}/answer")
async def submit_answer(game_id: str, req: SubmitAnswerRequest):
    """Submit an answer to the current prompt."""
    cm = get_connection_manager()
    repo = get_game_repository()
    settings = get_settings()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="Game not found")

        state = session.state
        if state.phase != GamePhase.PROMPT:
            raise HTTPException(status_code=400, detail="Not in prompt phase")

        result = validate_player_alive(state, req.player_id)
        if isinstance(result, str):
            raise HTTPException(status_code=400, detail=result)

        if not state.current_round:
            raise HTTPException(status_code=400, detail="No active round")

        if req.player_id in state.current_round.answers:
            raise HTTPException(status_code=400, detail="Already answered")

        answer_text = req.answer.strip() if req.answer.strip() else "[no response]"
        state.current_round.answers[req.player_id] = answer_text

        alive = get_alive_players(state)
        answer_count = len(state.current_round.answers)
        total_count = len(alive)

        event = AnswerSubmittedEvent(
            seq=session.next_seq(),
            player_id=req.player_id,
            answer_count=answer_count,
            total_count=total_count,
        )
        await cm.broadcast(game_id, event)

        # Check if all answered — early transition to chat
        if answer_count >= total_count:
            get_timer_manager().cancel_timer(game_id)
            transition_to_chat(state, settings.chat_duration)
            phase_event = PhaseChangedEvent(
                seq=session.next_seq(),
                phase=state.phase.value,
                round_number=state.round_number,
                phase_deadline=state.phase_deadline.isoformat() if state.phase_deadline else None,
                answers=state.current_round.answers,
            )
            await cm.broadcast(game_id, phase_event)
            early_transition = True
        else:
            early_transition = False

    if early_transition:
        await _start_phase_timer(game_id, GamePhase.CHAT)

    return {"status": "ok"}


@router.post("/{game_id}/chat")
async def send_chat(game_id: str, req: SendChatRequest):
    """Send a chat message during the chat phase."""
    cm = get_connection_manager()
    repo = get_game_repository()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="Game not found")

        state = session.state
        if state.phase != GamePhase.CHAT:
            raise HTTPException(status_code=400, detail="Not in chat phase")

        result = validate_player_alive(state, req.player_id)
        if isinstance(result, str):
            raise HTTPException(status_code=400, detail=result)
        player = result

        if not state.current_round:
            raise HTTPException(status_code=400, detail="No active round")

        message = ChatMessage(
            player_id=req.player_id,
            player_alias=player.alias,
            text=req.message,
        )
        state.current_round.messages.append(message)

        event = ChatMessageEvent(
            seq=session.next_seq(),
            player_id=req.player_id,
            player_alias=player.alias,
            text=req.message,
        )
        await cm.broadcast(game_id, event)

    return {"status": "ok"}


@router.post("/{game_id}/vote")
async def cast_vote(game_id: str, req: CastVoteRequest):
    """Cast a vote for who you think is human."""
    cm = get_connection_manager()
    repo = get_game_repository()
    settings = get_settings()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="Game not found")

        state = session.state
        if state.phase != GamePhase.VOTE:
            raise HTTPException(status_code=400, detail="Not in vote phase")

        result = validate_player_alive(state, req.player_id)
        if isinstance(result, str):
            raise HTTPException(status_code=400, detail=result)

        if not state.current_round:
            raise HTTPException(status_code=400, detail="No active round")

        if req.player_id in state.current_round.votes:
            raise HTTPException(status_code=400, detail="Already voted")

        # Validate target is alive
        target = next((p for p in state.players if p.id == req.target_id and p.is_alive), None)
        if not target:
            raise HTTPException(status_code=400, detail="Invalid vote target")

        state.current_round.votes[req.player_id] = req.target_id

        alive = get_alive_players(state)
        vote_count = len(state.current_round.votes)
        total_count = len(alive)

        event = VoteCastEvent(
            seq=session.next_seq(),
            voter_id=req.player_id,
            vote_count=vote_count,
            total_count=total_count,
        )
        await cm.broadcast(game_id, event)

        # Check if all voted — early transition
        if vote_count >= total_count:
            get_timer_manager().cancel_timer(game_id)
            await _do_vote_resolution(game_id, session)

    return {"status": "ok"}
