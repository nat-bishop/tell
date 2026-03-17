"""Debug routes — state injection for testing. Requires TELL_DEBUG=true."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter

from backend.api.deps import get_game_repository, get_settings
from backend.services.game_logic import get_phase_duration
from schemas.api_models import SeedGameRequest
from schemas.game_state import GamePhase, PlayerRole

router = APIRouter()

log = structlog.get_logger(__name__)


@router.post("/seed")
async def seed_game(req: SeedGameRequest):
    """Inject a complete game state for debugging."""
    repo = get_game_repository()
    settings = get_settings()

    state = req.state
    game_id = state.game_id
    active_phase = state.phase not in (GamePhase.LOBBY, GamePhase.GAME_OVER)

    # Set phase deadline if starting timers
    if req.start_timers and active_phase:
        round_type = state.current_round.round_type if state.current_round else None
        duration = get_phase_duration(settings, state.phase, round_type)
        if duration:
            state.phase_deadline = datetime.now(UTC) + timedelta(seconds=duration)

    # Store the game
    repo.create(state)

    log.info(
        "game_seeded",
        game_id=game_id,
        phase=state.phase.value,
        player_count=len(state.players),
    )

    # Start phase timer (fresh game, no contention)
    if req.start_timers and active_phase:
        from backend.services.transitions import start_phase_timer

        await start_phase_timer(game_id, state.phase)

    # Assign AI personalities and schedule AI actions
    if req.trigger_ai and active_phase:
        from backend.services.ai_scheduler import assign_personalities, on_phase_change

        ai_player_ids = [p.id for p in state.players if p.role == PlayerRole.AI and p.is_alive]
        if ai_player_ids:
            assign_personalities(game_id, ai_player_ids)
            await on_phase_change(game_id, state.phase)

    return {
        "status": "seeded",
        "game_id": game_id,
        "phase": state.phase.value,
        "player_count": len(state.players),
        "url": f"http://localhost:3500/game/{game_id}",
    }
