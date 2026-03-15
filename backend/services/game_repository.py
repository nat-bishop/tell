"""In-memory game session store."""

from __future__ import annotations

from dataclasses import dataclass, field

from schemas.game_state import TellGameState


@dataclass
class TellGameSession:
    state: TellGameState
    event_seq: int = 0

    def next_seq(self) -> int:
        self.event_seq += 1
        return self.event_seq


class GameRepository:
    """In-memory store for active games."""

    def __init__(self) -> None:
        self._games: dict[str, TellGameSession] = {}

    def create(self, state: TellGameState) -> TellGameSession:
        session = TellGameSession(state=state)
        self._games[state.game_id] = session
        return session

    def get(self, game_id: str) -> TellGameSession | None:
        return self._games.get(game_id)

    def delete(self, game_id: str) -> None:
        self._games.pop(game_id, None)

    def list_games(self) -> list[TellGameSession]:
        return list(self._games.values())
