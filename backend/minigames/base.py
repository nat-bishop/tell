"""Base minigame handler interface — implemented by each round type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.config import Settings
    from schemas.game_state import RoundType, TellGameState


@dataclass
class StepDef:
    name: str  # "compose", "vote", "challenge_0", "results"
    duration: int  # seconds of gameplay
    component: str = ""  # frontend component key for routing
    is_results: bool = False  # transition system calls build_results() before this step


class MinigameHandler:
    round_type: RoundType
    min_players: int = 2

    def _preroll_step(self, settings: Settings) -> StepDef:
        """Preroll step prepended to every round — shows round type + instructions."""
        return StepDef(name="preroll", duration=settings.preroll_duration, component="preroll")

    def setup_round(self, state: TellGameState, settings: Settings) -> None:
        """Initialize round state (mutates in place)."""
        raise NotImplementedError

    def get_steps(self, state: TellGameState, settings: Settings) -> list[StepDef]:
        """Return the full step sequence for this round, including results."""
        raise NotImplementedError

    async def on_step_start(self, game_id: str, state: TellGameState, step_index: int) -> None:
        """Called when a step begins. Schedule AI tasks, set up state."""

    async def on_step_end(self, game_id: str, state: TellGameState, step_index: int) -> None:
        """Called when a step expires. Cleanup (e.g. fill_missing_answers)."""

    def step_event_extras(self, state: TellGameState, step_index: int) -> dict:
        """Extra fields for the StepChangedEvent payload."""
        return {}

    async def finalize_round(self, game_id: str) -> None:
        """Async work after last gameplay step, before results (e.g. Signal LLM judging)."""

    def check_early_complete(self, state: TellGameState, step_index: int) -> bool:
        """Can this step end early? Default: False."""
        return False

    def build_results(self, state: TellGameState) -> tuple[dict, dict[str, int]]:
        """Return (results_payload, score_deltas) when scoring is needed."""
        raise NotImplementedError

    def build_state_sync_extras(self, state: TellGameState, player_id: str) -> dict:
        """Extra fields for reconnection StateSyncEvent.

        Default handles results steps (shared by all handlers).
        Subclasses override for step-specific extras and call super() as fallback.
        """
        steps = state.round_step_defs
        idx = state.current_step_index
        if steps and idx < len(steps) and steps[idx].get("is_results"):
            payload, _ = self.build_results(state)
            return {
                "round_results_payload": payload,
                "round_scores": {p.id: p.score for p in state.players},
            }
        return {}


# ---------------------------------------------------------------------------
# Shared helpers — used by handler subclasses to reduce boilerplate
# ---------------------------------------------------------------------------


def get_step_info(state: TellGameState, step_index: int):
    """Get round state and step def from state. Returns ``(rs, step_def)`` or ``None``."""
    rs = state.current_round
    if not rs:
        return None
    steps = state.round_step_defs
    if not steps or step_index >= len(steps):
        return None
    return rs, steps[step_index]


def parse_sub_index(step_name: str) -> int | None:
    """Extract numeric suffix from step names like ``challenge_2``, ``signal_guess_0``."""
    try:
        return int(step_name.rsplit("_", 1)[-1])
    except (ValueError, IndexError):
        return None
