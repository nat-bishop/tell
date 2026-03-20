"""Base minigame handler interface — implemented by each round type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.config import Settings
    from schemas.game_state import RoundType, TellGameState


@dataclass
class MinigameMeta:
    min_players: int = 2
    has_prompt: bool = True
    has_results: bool = True
    active_interstitial: int = 3
    results_interstitial: int = 2


class MinigameHandler:
    round_type: RoundType
    meta: MinigameMeta

    def setup_round(self, state: TellGameState, settings: Settings) -> None:
        """Initialize round state (mutates in place)."""
        raise NotImplementedError

    def get_prompt_duration(self, settings: Settings) -> int:
        """Duration for the PROMPT phase. Override for round-type-specific timing."""
        return settings.prompt_duration

    def get_active_duration(self, settings: Settings) -> int:
        raise NotImplementedError

    def get_results_duration(self, settings: Settings) -> int:
        raise NotImplementedError

    def active_event_extras(self, state: TellGameState) -> dict:
        """Extra fields for PhaseChangedEvent when entering ACTIVE."""
        return {}

    async def on_active_start(self, game_id: str) -> None:
        """Called after ACTIVE begins. Start sub-round loops, schedule AI, etc."""

    def build_results(self, state: TellGameState) -> tuple[dict, dict[str, int]]:
        """Return (results_payload, score_deltas) when ACTIVE ends."""
        raise NotImplementedError

    def build_state_sync_extras(self, state: TellGameState, player_id: str) -> dict:
        """Extra fields for reconnection StateSyncEvent.

        Default handles RESULTS phase (shared by all handlers with has_results=True).
        Subclasses override for ACTIVE/PROMPT-specific extras and call super() as fallback.
        """
        from schemas.game_state import GamePhase

        if state.phase == GamePhase.RESULTS:
            payload, _ = self.build_results(state)
            return {
                "round_results_payload": payload,
                "round_scores": {p.id: p.score for p in state.players},
            }
        return {}
