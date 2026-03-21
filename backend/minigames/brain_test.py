"""Brain Test (Quick Draw) minigame handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.config import Settings

from backend.minigames.base import (
    MinigameHandler,
    StepDef,
    get_step_info,
    parse_sub_index,
)
from schemas.game_state import (
    BrainTestChallenge,
    RoundState,
    RoundType,
    TellGameState,
)


def score_brain_test(challenges: list[BrainTestChallenge]) -> dict[str, int]:
    """Score all challenges. 100 points per correct answer."""
    totals: dict[str, int] = {}
    for ch in challenges:
        for pid, selected in ch.responses.items():
            totals[pid] = totals.get(pid, 0) + (100 if selected == ch.correct_index else 0)
    return totals


class BrainTestHandler(MinigameHandler):
    round_type = RoundType.BRAIN_TEST
    min_players = 2

    def setup_round(self, state: TellGameState, settings: Settings) -> None:
        from schemas.prompts import select_brain_test_challenges

        challenges = select_brain_test_challenges(settings.brain_test_challenges)
        state.round_number += 1
        state.current_round = RoundState(
            round_number=state.round_number,
            prompt_text="quick draw",
            prompt_category="brain_test",
            round_type=RoundType.BRAIN_TEST,
            current_sub_round=0,
            brain_challenges=[
                BrainTestChallenge(
                    challenge_type=c.challenge_type,
                    question=c.question,
                    options=c.options,
                    correct_index=c.correct_index,
                )
                for c in challenges
            ],
        )

    def get_steps(self, state: TellGameState, settings: Settings) -> list[StepDef]:
        num = settings.brain_test_challenges
        dur = settings.brain_test_challenge_duration
        steps = [
            StepDef(name=f"challenge_{i}", duration=dur, component="brain_test") for i in range(num)
        ]
        steps.append(
            StepDef(
                name="results",
                duration=settings.brain_test_results_duration,
                component="brain_test_results",
                is_results=True,
            )
        )
        return steps

    async def on_step_start(self, game_id: str, state: TellGameState, step_index: int) -> None:
        info = get_step_info(state, step_index)
        if not info:
            return
        rs, step = info
        challenge_index = parse_sub_index(step["name"])
        if challenge_index is None:
            return

        rs.current_sub_round = challenge_index

        from backend.services.ai_scheduler import on_brain_test_challenge

        await on_brain_test_challenge(game_id, challenge_index)

    def step_event_extras(self, state: TellGameState, step_index: int) -> dict:
        info = get_step_info(state, step_index)
        if not info:
            return {}
        rs, step = info
        challenge_index = parse_sub_index(step["name"])
        if challenge_index is None or challenge_index >= len(rs.brain_challenges):
            return {}
        ch = rs.brain_challenges[challenge_index]
        return {
            "round_type": "brain_test",
            "challenge_index": challenge_index,
            "challenge_type": ch.challenge_type,
            "question": ch.question,
            "options": ch.options,
        }

    def build_results(self, state: TellGameState) -> tuple[dict, dict[str, int]]:
        rs = state.current_round
        if not rs:
            return {}, {}

        # Build per-player results
        results: dict[str, list[dict]] = {}
        for p in state.players:
            player_results = []
            for ch in rs.brain_challenges:
                player_results.append(
                    {
                        "question": ch.question,
                        "options": ch.options,
                        "selected_index": ch.responses.get(p.id, -1),
                        "correct_index": ch.correct_index,
                        "challenge_type": ch.challenge_type,
                    }
                )
            results[p.id] = player_results

        score_deltas = score_brain_test(rs.brain_challenges)
        return {"results": results}, score_deltas

    def build_state_sync_extras(self, state: TellGameState, player_id: str) -> dict:
        """Provide current challenge info for reconnection during challenge steps."""
        info = get_step_info(state, state.current_step_index)
        if info:
            rs, step = info
            challenge_index = parse_sub_index(step["name"])
            if challenge_index is not None and challenge_index < len(rs.brain_challenges):
                ch = rs.brain_challenges[challenge_index]
                return {
                    "sub_round_index": challenge_index,
                    "sub_round_payload": {
                        "round_type": "brain_test",
                        "challenge_index": challenge_index,
                        "challenge_type": ch.challenge_type,
                        "question": ch.question,
                        "options": ch.options,
                    },
                }

        return super().build_state_sync_extras(state, player_id)
