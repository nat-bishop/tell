"""Game lifecycle routes — create and info."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException

from backend.api.deps import get_connection_manager, get_game_repository, get_settings
from schemas.aliases import generate_game_id
from schemas.api_models import CreateGameResponse, GameInfoResponse
from schemas.game_state import TellGameState

router = APIRouter()

log = structlog.get_logger(__name__)


@router.post("", response_model=CreateGameResponse)
async def create_game():
    """Create a new game room."""
    game_id = generate_game_id()
    state = TellGameState(game_id=game_id)
    repo = get_game_repository()
    repo.create(state)
    # Ensure connection infrastructure exists
    cm = get_connection_manager()
    cm.get_lock(game_id)
    log.info("game_created", game_id=game_id)
    return CreateGameResponse(
        game_id=game_id,
        join_url=f"/game/{game_id}",
    )


@router.get("/{game_id}", response_model=GameInfoResponse)
async def get_game_info(game_id: str):
    """Get basic game info."""
    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")
    settings = get_settings()
    return GameInfoResponse(
        game_id=game_id,
        phase=session.state.phase.value,
        player_count=len(session.state.players),
        max_players=settings.max_players,
    )
