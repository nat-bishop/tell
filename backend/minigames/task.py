"""Task (gallery vote) minigame handler."""

from __future__ import annotations

import random
from typing import Any

import structlog

from backend.minigames.base import MinigameHandler, MinigameMeta
from schemas.game_state import RoundState, RoundType, TellGameState

log = structlog.get_logger(__name__)


class TaskHandler(MinigameHandler):
    round_type = RoundType.TASK
    meta = MinigameMeta(
        min_players=2,
        has_prompt=True,
        has_results=True,
        active_interstitial=3,
        results_interstitial=2,
    )

    def setup_round(self, state: TellGameState, settings: Any) -> None:
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

    def get_active_duration(self, settings: Any) -> int:
        return settings.vote_duration

    def get_results_duration(self, settings: Any) -> int:
        return settings.vote_results_duration

    def active_event_extras(self, state: TellGameState) -> dict:
        rs = state.current_round
        return {"answers": rs.answers if rs else {}}

    async def on_active_start(self, game_id: str) -> None:
        """Schedule AI vote tasks."""
        import asyncio

        from backend.api.deps import get_game_repository
        from backend.services.ai_scheduler import (
            _ai_tasks,
            _ai_vote_task,
        )

        repo = get_game_repository()
        session = repo.get(game_id)
        if not session:
            return

        state = session.state
        from schemas.game_state import PlayerRole

        ai_players = [p for p in state.players if p.role == PlayerRole.AI]
        if not ai_players:
            return

        tasks: list[asyncio.Task] = []
        for player in ai_players:
            delay = random.uniform(2, 8)
            tasks.append(asyncio.create_task(_ai_vote_task(game_id, player.id, delay)))
        _ai_tasks.setdefault(game_id, []).extend(tasks)

    def build_results(self, state: TellGameState) -> tuple[dict, dict[str, int]]:
        """Tally gallery votes. Each vote received = -1 point."""
        vote_counts: dict[str, int] = {p.id: 0 for p in state.players}
        rs = state.current_round
        if rs:
            for target_id in rs.gallery_votes.values():
                if target_id in vote_counts:
                    vote_counts[target_id] += 1

        # Score deltas: votes received = negative points
        score_deltas: dict[str, int] = {}
        for pid, count in vote_counts.items():
            if count > 0:
                score_deltas[pid] = -count

        return {"vote_counts": vote_counts}, score_deltas

    def build_state_sync_extras(self, state: TellGameState, player_id: str) -> dict:
        rs = state.current_round
        if rs and player_id in rs.gallery_votes:
            return {"my_vote": rs.gallery_votes[player_id]}
        return {}
