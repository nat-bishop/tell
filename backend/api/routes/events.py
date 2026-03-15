"""SSE event stream — persistent connection for real-time game updates."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from backend.api.deps import get_connection_manager, get_game_repository
from backend.services.game_logic import build_state_sync
from schemas.api_models import HostChangedEvent
from schemas.game_state import PlayerRole

router = APIRouter()


@router.get("/{game_id}/events")
async def game_events(game_id: str, player_id: str, request: Request, last_seq: int = 0):
    """Persistent SSE stream for a game. Sends state_sync on connect, then live events."""
    repo = get_game_repository()
    session = repo.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    cm = get_connection_manager()
    queue = cm.connect(game_id, player_id)

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
                    for event in missed:
                        yield {
                            "id": str(event.seq),
                            "event": event.event_type,
                            "data": event.model_dump_json(),
                        }

            if send_full_sync:
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
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    if event is None:
                        break  # Shutdown signal
                    yield {
                        "id": str(event.seq),
                        "event": event.event_type,
                        "data": event.model_dump_json(),
                    }
                except asyncio.TimeoutError:
                    yield {"comment": "ping"}
        finally:
            cm.disconnect(game_id, player_id)
            repo_session = repo.get(game_id)
            if repo_session:
                # Mark disconnected and check host promotion in one pass
                was_host = False
                for p in repo_session.state.players:
                    if p.id == player_id:
                        p.is_connected = False
                        was_host = p.is_host
                        if was_host:
                            p.is_host = False
                        break

                if was_host:
                    for p in repo_session.state.players:
                        if p.id != player_id and p.is_connected and p.role == PlayerRole.HUMAN:
                            p.is_host = True
                            event = HostChangedEvent(
                                seq=repo_session.next_seq(),
                                new_host_id=p.id,
                                new_host_alias=p.alias,
                            )
                            await cm.broadcast(game_id, event)
                            break

    return EventSourceResponse(event_generator(), ping=15)
