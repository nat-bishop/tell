"""SSE event stream route — real-time game updates."""

from fastapi import APIRouter

router = APIRouter()

# TODO: GET /{game_id}/events?player_id=...&last_seq=... — SSE stream
