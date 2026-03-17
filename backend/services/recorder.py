"""Write completed game recordings to disk as JSON."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import structlog

from schemas.api_models import GameEvent
from schemas.game_state import TellGameState

log = structlog.get_logger(__name__)

_RECORDINGS_DIR = Path(__file__).resolve().parent.parent.parent / "recordings"


def save_recording(game_id: str, state: TellGameState, events: list[GameEvent]) -> None:
    """Persist the full event stream and final state for a completed game."""
    try:
        os.makedirs(_RECORDINGS_DIR, exist_ok=True)
        path = _RECORDINGS_DIR / f"{game_id}.json"
        data = {
            "game_id": game_id,
            "recorded_at": datetime.now(UTC).isoformat(),
            "winner": state.winner,
            "round_count": state.round_number,
            "players": [
                {"alias": p.alias, "role": p.role.value, "is_alive": p.is_alive}
                for p in state.players
            ],
            "final_state": state.model_dump(mode="json"),
            "events": [e.model_dump(mode="json") for e in events],
        }
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        log.info("recording_saved", game_id=game_id, path=str(path), event_count=len(events))
    except Exception:
        log.exception("recording_failed", game_id=game_id)
