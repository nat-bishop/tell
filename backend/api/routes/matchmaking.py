"""Matchmaking routes — join queue, leave queue, SSE lobby events."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from backend.api.deps import get_connection_manager, get_matchmaking_service
from schemas.api_models import (
    LobbyStatusEvent,
    MatchmakingJoinRequest,
    MatchmakingJoinResponse,
    MatchmakingLeaveRequest,
    MatchmakingStatusResponse,
    StatusResponse,
)
from schemas.constants import MATCHMAKING_LOBBY_ID

router = APIRouter()

log = structlog.get_logger(__name__)


@router.post("/join", response_model=MatchmakingJoinResponse)
async def matchmaking_join(req: MatchmakingJoinRequest):
    """Join the matchmaking queue."""
    mm = get_matchmaking_service()
    result = await mm.join(req.player_name)
    log.info("matchmaking_player_joined", alias=result.alias, position=result.position)
    return result


@router.post("/leave", response_model=StatusResponse)
async def matchmaking_leave(req: MatchmakingLeaveRequest):
    """Leave the matchmaking queue."""
    mm = get_matchmaking_service()
    await mm.leave(req.player_id)
    return {"status": "ok"}


@router.get("/status", response_model=MatchmakingStatusResponse)
async def matchmaking_status():
    """Current matchmaking lobby state."""
    mm = get_matchmaking_service()
    status = mm.get_status()
    return MatchmakingStatusResponse(
        human_count=status["human_count"],
        countdown_seconds=None,
        message=f"{status['human_count']} in queue" if status["human_count"] > 0 else "",
    )


@router.get("/events")
async def matchmaking_events(player_id: str, request: Request):
    """SSE stream for matchmaking lobby updates."""
    cm = get_connection_manager()
    queue = cm.connect(MATCHMAKING_LOBBY_ID, player_id)
    log.info("matchmaking_sse_connected", player_id=player_id)

    async def event_generator():
        try:
            # Send initial status using the model
            mm = get_matchmaking_service()
            count = mm.human_count
            initial = LobbyStatusEvent(
                seq=0,
                human_count=count,
                message=f"{count} assembled — waiting for more"
                if count > 0
                else "waiting for players",
            )
            yield {
                "event": initial.event_type,
                "data": initial.model_dump_json(),
            }

            # Stream live events
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    if event is None:
                        break
                    yield {
                        "id": str(event.seq),
                        "event": event.event_type,
                        "data": event.model_dump_json(),
                    }
                except asyncio.TimeoutError:
                    yield {"comment": "ping"}
        finally:
            log.info("matchmaking_sse_disconnected", player_id=player_id)
            cm.disconnect(MATCHMAKING_LOBBY_ID, player_id)
            # If they disconnect without explicitly leaving, remove from queue
            mm = get_matchmaking_service()
            await mm.leave(player_id)

    return EventSourceResponse(event_generator(), ping=15)
