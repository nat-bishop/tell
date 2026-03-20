"""Brain Test (Quick Draw) minigame handler."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.config import Settings

import structlog

from backend.minigames.base import MinigameHandler, MinigameMeta
from schemas.game_state import (
    BrainTestChallenge,
    RoundState,
    RoundType,
    TellGameState,
)

log = structlog.get_logger(__name__)


def score_brain_test(challenges: list[BrainTestChallenge]) -> dict[str, int]:
    """Score all challenges. 1 point per correct answer (selected_index == correct_index)."""
    totals: dict[str, int] = {}
    for ch in challenges:
        for pid, selected in ch.responses.items():
            totals[pid] = totals.get(pid, 0) + (1 if selected == ch.correct_index else 0)
    return totals


class BrainTestHandler(MinigameHandler):
    round_type = RoundType.BRAIN_TEST
    meta = MinigameMeta(
        min_players=2,
        has_prompt=False,
        has_results=True,
        active_interstitial=5,
        results_interstitial=2,
    )

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

    def get_active_duration(self, settings: Settings) -> int:
        return settings.brain_test_duration

    def get_results_duration(self, settings: Settings) -> int:
        return settings.brain_test_results_duration

    async def on_active_start(self, game_id: str) -> None:
        """Start the brain test sub-round loop."""
        from backend.services.ai_scheduler import register_task

        task = asyncio.create_task(self._brain_loop(game_id))
        register_task(game_id, task)

    async def _brain_loop(self, game_id: str) -> None:
        try:
            from backend.api.deps import (
                get_connection_manager,
                get_game_repository,
                get_settings,
                get_timer_manager,
            )
            from schemas.api_models import SubRoundEvent
            from schemas.game_state import GamePhase

            cm = get_connection_manager()
            settings = get_settings()
            repo = get_game_repository()
            sub_duration = settings.brain_test_challenge_duration
            num_challenges = settings.brain_test_challenges
            lock = cm.get_lock(game_id)

            for i in range(num_challenges):
                async with lock:
                    session = repo.get(game_id)
                    if not session:
                        return
                    state = session.state
                    if state.phase != GamePhase.ACTIVE:
                        return
                    rs = state.current_round
                    if not rs or i >= len(rs.brain_challenges):
                        return

                    rs.current_sub_round = i
                    ch = rs.brain_challenges[i]

                    sub_deadline = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=sub_duration)
                    state.phase_deadline = sub_deadline

                    await cm.broadcast(
                        game_id,
                        SubRoundEvent(
                            seq=session.next_seq(),
                            round_type="brain_test",
                            sub_round_index=i,
                            payload={
                                "challenge_index": i,
                                "challenge_type": ch.challenge_type,
                                "question": ch.question,
                                "options": ch.options,
                            },
                            sub_deadline=sub_deadline.isoformat(),
                            phase_duration=sub_duration,
                        ),
                    )

                # Schedule AI for this challenge
                from backend.services.ai_scheduler import on_brain_test_challenge

                await on_brain_test_challenge(game_id, i)

                await asyncio.sleep(sub_duration)

            # All challenges done — transition to results
            async with lock:
                session = repo.get(game_id)
                if not session:
                    return
                if session.state.phase != GamePhase.ACTIVE:
                    return
                get_timer_manager().cancel_timer(game_id)

                # Runtime import to avoid circular dep
                from backend.services.transitions import do_active_complete

                await do_active_complete(game_id, session)

        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("brain_test_loop_error", game_id=game_id)

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
        """Provide current challenge info for reconnection during ACTIVE."""
        from schemas.game_state import GamePhase

        rs = state.current_round
        if not rs:
            return {}

        if state.phase == GamePhase.ACTIVE:
            idx = rs.current_sub_round
            if idx < len(rs.brain_challenges):
                ch = rs.brain_challenges[idx]
                return {
                    "sub_round_index": idx,
                    "sub_round_payload": {
                        "round_type": "brain_test",
                        "challenge_index": idx,
                        "challenge_type": ch.challenge_type,
                        "question": ch.question,
                        "options": ch.options,
                    },
                }

        return super().build_state_sync_extras(state, player_id)
