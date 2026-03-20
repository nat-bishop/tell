"""SSE event stream — persistent connection for real-time game updates."""

from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from backend.api.deps import get_connection_manager, get_game_repository
from backend.services.game_logic import build_state_sync
from schemas.api_models import HostChangedEvent
from schemas.game_state import PlayerRole

router = APIRouter()

log = structlog.get_logger(__name__)


@router.get("/{game_id}/events")
async def game_events(
    game_id: str, player_id: str, request: Request, last_seq: int = 0
) -> EventSourceResponse:
    """Persistent SSE stream for a game. Sends state_sync on connect, then live events."""
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(game_id=game_id, player_id=player_id)

    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    cm = get_connection_manager()
    queue = cm.connect(game_id, player_id)
    log.info("sse_connected")

    # Mark player as connected
    for p in session.state.players:
        if p.id == player_id:
            p.is_connected = True
            break

    async def event_generator():
        try:
            # Replay missed events, or fall back to full state sync
            send_full_sync = True
            if last_seq > 0:
                missed = cm.get_events_after(game_id, last_seq)
                if missed is not None:
                    send_full_sync = False
                    log.debug("sse_replay", event_count=len(missed))
                    for event in missed:
                        yield {
                            "id": str(event.seq),
                            "event": event.event_type,
                            "data": event.model_dump_json(),
                        }

            if send_full_sync:
                log.debug("sse_full_sync")
                sync_data = build_state_sync(session.state, player_id, session.next_seq())
                yield {
                    "id": str(sync_data["seq"]),
                    "event": "state_sync",
                    "data": json.dumps(sync_data),
                }

            # Stream live events
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)  # type: ignore[arg-type]
                    if event is None:
                        break  # Shutdown signal
                    yield {
                        "id": str(event.seq),
                        "event": event.event_type,
                        "data": event.model_dump_json(),
                    }
                except TimeoutError:
                    yield {"comment": "ping"}
        finally:
            log.info("sse_disconnected")
            cm.disconnect(game_id, player_id)
            await _handle_disconnect(cm, repo, game_id, player_id)

    return EventSourceResponse(event_generator(), ping=15)


async def _handle_disconnect(cm, repo, game_id: str, player_id: str) -> None:
    """Mark player disconnected and promote a new host if needed."""
    lock = cm.get_lock(game_id)
    async with lock:
        session = repo.get(game_id)
        if not session:
            return

        # Mark disconnected and check host promotion in one pass
        was_host = False
        for p in session.state.players:
            if p.id == player_id:
                p.is_connected = False
                was_host = p.is_host
                if was_host:
                    p.is_host = False
                break

        if was_host:
            for p in session.state.players:
                if p.id != player_id and p.is_connected and p.role == PlayerRole.HUMAN:
                    p.is_host = True
                    log.info("host_promoted", new_host_id=p.id)
                    event = HostChangedEvent(
                        seq=session.next_seq(),
                        new_host_id=p.id,
                        new_host_alias=p.alias,
                    )
                    await cm.broadcast(game_id, event)
                    break
