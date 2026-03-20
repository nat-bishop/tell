"""Task (gallery vote) minigame handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.minigames.base import MinigameHandler, MinigameMeta
from schemas.game_state import RoundState, RoundType, TellGameState

if TYPE_CHECKING:
    from backend.config import Settings


class TaskHandler(MinigameHandler):
    round_type = RoundType.TASK
    meta = MinigameMeta(
        min_players=2,
        has_prompt=True,
        has_results=True,
        active_interstitial=3,
        results_interstitial=2,
    )

    def setup_round(self, state: TellGameState, settings: Settings) -> None:
        from schemas.prompts import select_duel_prompt

        state.round_number += 1
        idx, prompt = select_duel_prompt(state.used_prompt_indices, state.last_prompt_category)
        state.used_prompt_indices.append(idx)
        state.last_prompt_category = prompt.category.value
        state.current_round = RoundState(
            round_number=state.round_number,
            prompt_text=prompt.text,
            prompt_category=prompt.category.value,
            round_type=RoundType.TASK,
        )

    def get_active_duration(self, settings: Settings) -> int:
        return settings.vote_duration

    def get_results_duration(self, settings: Settings) -> int:
        return settings.vote_results_duration

    def active_event_extras(self, state: TellGameState) -> dict:
        rs = state.current_round
        return {"answers": rs.answers if rs else {}}

    async def on_active_start(self, game_id: str) -> None:
        """Schedule AI vote tasks."""
        from backend.services.ai_scheduler import schedule_ai_votes

        await schedule_ai_votes(game_id)

    def build_results(self, state: TellGameState) -> tuple[dict, dict[str, int]]:
        """Tally gallery votes. Each vote received = -1 point."""
        from backend.services.game_logic import tally_gallery_votes

        vote_counts = tally_gallery_votes(state)
        score_deltas = {pid: -count for pid, count in vote_counts.items() if count > 0}
        return {"vote_counts": vote_counts}, score_deltas

    def build_state_sync_extras(self, state: TellGameState, player_id: str) -> dict:
        rs = state.current_round
        if rs and player_id in rs.gallery_votes:
            return {"my_vote": rs.gallery_votes[player_id]}
        return {}
