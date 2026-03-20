"""Debug routes — state injection for testing. Requires TELL_DEBUG=true."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter

from backend.api.deps import get_game_repository, get_settings, get_timer_manager
from backend.minigames import get_handler
from backend.services.game_logic import get_current_step
from schemas.api_models import SeedGameRequest
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
                await handler.on_step_start(game_id, state.current_step_index)

    return {
        "status": "seeded",
        "game_id": game_id,
        "phase": state.phase.value,
        "player_count": len(state.players),
        "url": f"http://localhost:3500/game/{game_id}",
    }
