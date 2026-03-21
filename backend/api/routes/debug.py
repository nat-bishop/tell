"""Debug routes — state injection for testing. Requires TELL_DEBUG=true."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, HTTPException

from backend.api.deps import (
    get_connection_manager,
    get_game_repository,
    get_settings,
    get_timer_manager,
)
from backend.minigames import get_handler
from backend.services.game_logic import get_current_step
from schemas.api_models import EndGameRequest, SeedGameRequest, SkipStepRequest
from schemas.game_state import GamePhase, PlayerRole

router = APIRouter()

log = structlog.get_logger(__name__)


@router.post("/seed")
async def seed_game(req: SeedGameRequest) -> dict[str, str | int]:
    """Inject a complete game state for debugging."""
    repo = get_game_repository()
    settings = get_settings()

    state = req.state
    game_id = state.game_id
    in_round = state.phase == GamePhase.ROUND

    # If in a round and step defs are missing, generate them from the handler
    if in_round and state.current_round and not state.round_step_defs:
        handler = get_handler(state.current_round.round_type)
        step_defs = handler.get_steps(state, settings)
        state.round_step_defs = [asdict(s) for s in step_defs]

    # Set phase deadline if starting timers
    if req.start_timers and in_round:
        step = get_current_step(state)
        if step:
            duration = step["duration"]
            state.phase_deadline = datetime.now(UTC) + timedelta(seconds=duration)

    # Store the game
    repo.create(state)

    log.info(
        "game_seeded",
        game_id=game_id,
        phase=state.phase.value,
        player_count=len(state.players),
    )

    # Start step timer
    if req.start_timers and in_round:
        step = get_current_step(state)
        if step:
            from backend.services.transitions import _handle_step_expiry

            tm = get_timer_manager()

            async def on_expire():
                await _handle_step_expiry(game_id)

            tm.start_timer(game_id, step["duration"], on_expire)

    # Assign AI personalities and schedule AI actions
    if req.trigger_ai and in_round:
        from backend.services.ai_scheduler import assign_personalities

        ai_player_ids = [p.id for p in state.players if p.role == PlayerRole.AI]
        if ai_player_ids:
            assign_personalities(game_id, ai_player_ids)
            # Trigger on_step_start for current step
            if state.current_round:
                handler = get_handler(state.current_round.round_type)
                await handler.on_step_start(game_id, state, state.current_step_index)

    return {
        "status": "seeded",
        "game_id": game_id,
        "phase": state.phase.value,
        "player_count": len(state.players),
        "url": f"http://localhost:3500/game/{game_id}",
    }


@router.post("/end-game/{game_id}")
async def end_game(game_id: str, req: EndGameRequest) -> dict[str, str]:
    """Force-end a game and clean up all resources. Host only."""
    cm = get_connection_manager()
    repo = get_game_repository()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="Game not found")

        state = session.state
        host = next((p for p in state.players if p.id == req.player_id and p.is_host), None)
        if not host:
            raise HTTPException(status_code=400, detail="Only the host can end the game")

        # Cancel timer
        get_timer_manager().cancel_timer(game_id)

        # Cancel AI tasks
        from backend.services.ai_scheduler import cleanup_game as ai_cleanup

        ai_cleanup(game_id)

        # Remove game from repo
        repo.delete(game_id)

        log.info("game_ended_by_host", game_id=game_id)

    # Clean up connections (removes lock, so must be outside lock block)
    cm.cleanup_game(game_id)

    return {"status": "ended"}


@router.post("/skip-step/{game_id}")
async def skip_step(game_id: str, req: SkipStepRequest) -> dict[str, str]:
    """Force-advance the current step. Host only. Reuses timer-expiry logic."""
    repo = get_game_repository()
    cm = get_connection_manager()
    lock = cm.get_lock(game_id)

    async with lock:
        session = repo.get(game_id)
        if not session:
            raise HTTPException(status_code=404, detail="Game not found")

        state = session.state
        host = next((p for p in state.players if p.id == req.player_id and p.is_host), None)
        if not host:
            raise HTTPException(status_code=400, detail="Only the host can skip steps")

        if state.phase != GamePhase.ROUND:
            raise HTTPException(status_code=400, detail="Game is not in a round")

    # Cancel any running timer, then trigger expiry logic
    get_timer_manager().cancel_timer(game_id)

    from backend.services.transitions import _handle_step_expiry

    await _handle_step_expiry(game_id)

    log.info("step_skipped_by_host", game_id=game_id)

    return {"status": "skipped"}
