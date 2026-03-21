"""Task (gallery vote) minigame handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.minigames.base import MinigameHandler, StepDef, get_step_info
from schemas.game_state import RoundState, RoundType, TellGameState

if TYPE_CHECKING:
    from backend.config import Settings


class TaskHandler(MinigameHandler):
    round_type = RoundType.TASK
    min_players = 2

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

    def get_steps(self, state: TellGameState, settings: Settings) -> list[StepDef]:
        return [
            self._preroll_step(settings),
            StepDef(name="compose", duration=settings.prompt_duration, component="compose"),
            StepDef(name="vote", duration=settings.vote_duration, component="vote"),
            StepDef(
                name="results",
                duration=settings.vote_results_duration,
                component="vote_results",
                is_results=True,
            ),
        ]

    async def on_step_start(self, game_id: str, state: TellGameState, step_index: int) -> None:
        from backend.services.ai_scheduler import schedule_ai_answers, schedule_ai_votes

        info = get_step_info(state, step_index)
        if not info:
            return
        _rs, step = info
        step_name = step["name"]

        if step_name == "compose":
            await schedule_ai_answers(game_id)
        elif step_name == "vote":
            await schedule_ai_votes(game_id)

    async def on_step_end(self, game_id: str, state: TellGameState, step_index: int) -> None:
        info = get_step_info(state, step_index)
        if not info:
            return
        _rs, step = info
        if step["name"] == "compose":
            from backend.services.game_logic import fill_missing_answers

            fill_missing_answers(state)

    def step_event_extras(self, state: TellGameState, step_index: int) -> dict:
        info = get_step_info(state, step_index)
        if not info:
            return {}
        rs, step = info
        step_name = step["name"]

        if step_name == "compose":
            return {
                "prompt_text": rs.prompt_text,
                "prompt_category": rs.prompt_category,
            }
        if step_name == "vote":
            return {"answers": rs.answers}
        return {}

    def check_early_complete(self, state: TellGameState, step_index: int) -> bool:
        info = get_step_info(state, step_index)
        if not info:
            return False
        rs, step = info
        step_name = step["name"]

        if step_name == "compose":
            from backend.services.game_logic import get_answer_total

            return len(rs.answers) >= get_answer_total(state)
        if step_name == "vote":
            return len(rs.gallery_votes) >= len(state.players)
        return False

    def build_results(self, state: TellGameState) -> tuple[dict, dict[str, int]]:
        """Tally gallery votes. Each vote received = -1 point."""
        from backend.services.game_logic import tally_gallery_votes

        vote_counts = tally_gallery_votes(state)
        score_deltas = {pid: -100 * count for pid, count in vote_counts.items() if count > 0}
        return {"vote_counts": vote_counts}, score_deltas

    def build_state_sync_extras(self, state: TellGameState, player_id: str) -> dict:
        rs = state.current_round
        if not rs:
            return {}

        extras: dict = {}
        if player_id in rs.gallery_votes:
            extras["my_vote"] = rs.gallery_votes[player_id]

        extras.update(super().build_state_sync_extras(state, player_id))
        return extras
