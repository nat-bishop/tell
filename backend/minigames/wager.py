"""Wager (numerical estimation + social betting) minigame handler."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.config import Settings

import structlog

from backend.minigames.base import MinigameHandler, MinigameMeta
from schemas.game_state import (
    RoundState,
    RoundType,
    TellGameState,
    WagerQuestion,
)

log = structlog.get_logger(__name__)


def _get_closest_ids(q: WagerQuestion) -> list[str]:
    """Return player IDs with the closest guess to the correct answer."""
    if not q.guesses:
        return []
    correct = q.correct_answer
    min_dist = min(abs(g - correct) for g in q.guesses.values())
    return [pid for pid, g in q.guesses.items() if abs(g - correct) == min_dist]


def _build_sub_round_payload(q: WagerQuestion, q_idx: int, num_questions: int, phase: str) -> dict:
    """Build the payload dict for a wager sub-round event."""
    payload: dict = {
        "round_type": "wager",
        "phase": phase,
        "question_index": q_idx,
        "question": q.question,
        "range_min": q.range_min,
        "range_max": q.range_max,
        "unit": q.unit,
        "total_questions": num_questions,
    }
    if phase == "bet":
        payload["guesses"] = dict(q.guesses)
    return payload


def score_wager(questions: list[WagerQuestion]) -> dict[str, int]:
    """Score all wager questions. +1 closest guess, +1 correct bet per question."""
    totals: dict[str, int] = {}
    for q in questions:
        closest = set(_get_closest_ids(q))
        for pid in closest:
            totals[pid] = totals.get(pid, 0) + 1
        for pid, target in q.bets.items():
            if target in closest:
                totals[pid] = totals.get(pid, 0) + 1
    return totals


class WagerHandler(MinigameHandler):
    round_type = RoundType.WAGER
    meta = MinigameMeta(
        min_players=3,
        has_prompt=False,
        has_results=True,
        active_interstitial=5,
        results_interstitial=2,
    )

    def setup_round(self, state: TellGameState, settings: Settings) -> None:
        from schemas.prompts import select_wager_questions

        questions = select_wager_questions(settings.wager_questions)
        state.round_number += 1
        state.current_round = RoundState(
            round_number=state.round_number,
            prompt_text="wager",
            prompt_category="wager",
            round_type=RoundType.WAGER,
            current_sub_round=0,
            wager_questions=[
                WagerQuestion(
                    question=q.question,
                    correct_answer=q.correct_answer,
                    range_min=q.range_min,
                    range_max=q.range_max,
                    unit=q.unit,
                    category=q.category,
                )
                for q in questions
            ],
        )

    def get_active_duration(self, settings: Settings) -> int:
        return settings.wager_duration

    def get_results_duration(self, settings: Settings) -> int:
        return settings.wager_results_duration

    async def on_active_start(self, game_id: str) -> None:
        """Start the wager sub-round loop."""
        from backend.services.ai_scheduler import register_task

        task = asyncio.create_task(self._wager_loop(game_id))
        register_task(game_id, task)

    async def _wager_loop(self, game_id: str) -> None:
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
            sub_duration = settings.wager_sub_round_duration
            num_questions = settings.wager_questions
            lock = cm.get_lock(game_id)

            for q_idx in range(num_questions):
                for phase in ("guess", "bet"):
                    sub_index = q_idx * 2 if phase == "guess" else q_idx * 2 + 1

                    async with lock:
                        session = repo.get(game_id)
                        if not session:
                            return
                        state = session.state
                        if state.phase != GamePhase.ACTIVE:
                            return
                        rs = state.current_round
                        if not rs or q_idx >= len(rs.wager_questions):
                            return

                        rs.current_sub_round = sub_index
                        q = rs.wager_questions[q_idx]

                        sub_deadline = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=sub_duration)
                        state.phase_deadline = sub_deadline

                        await cm.broadcast(
                            game_id,
                            SubRoundEvent(
                                seq=session.next_seq(),
                                round_type="wager",
                                sub_round_index=sub_index,
                                payload=_build_sub_round_payload(q, q_idx, num_questions, phase),
                                sub_deadline=sub_deadline.isoformat(),
                                phase_duration=sub_duration,
                            ),
                        )

                    # Schedule AI (outside lock)
                    if phase == "guess":
                        from backend.services.ai_scheduler import on_wager_guess

                        await on_wager_guess(game_id, q_idx)
                    else:
                        from backend.services.ai_scheduler import on_wager_bet

                        await on_wager_bet(game_id, q_idx)

                    await asyncio.sleep(sub_duration)

            # All questions done — transition to results
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
            log.exception("wager_loop_error", game_id=game_id)

    def build_results(self, state: TellGameState) -> tuple[dict, dict[str, int]]:
        rs = state.current_round
        if not rs:
            return {}, {}

        questions_payload = [
            {
                "question": q.question,
                "correct_answer": q.correct_answer,
                "range_min": q.range_min,
                "range_max": q.range_max,
                "unit": q.unit,
                "guesses": dict(q.guesses),
                "bets": dict(q.bets),
                "closest_ids": _get_closest_ids(q),
            }
            for q in rs.wager_questions
        ]

        score_deltas = score_wager(rs.wager_questions)
        return {"questions": questions_payload}, score_deltas

    def build_state_sync_extras(self, state: TellGameState, player_id: str) -> dict:
        """Provide current sub-round info for reconnection during ACTIVE."""
        from schemas.game_state import GamePhase

        rs = state.current_round
        if not rs:
            return {}

        if state.phase == GamePhase.ACTIVE:
            sub = rs.current_sub_round
            q_idx = sub // 2
            if q_idx < len(rs.wager_questions):
                q = rs.wager_questions[q_idx]
                phase = "guess" if sub % 2 == 0 else "bet"
                return {
                    "sub_round_index": sub,
                    "sub_round_payload": _build_sub_round_payload(
                        q, q_idx, len(rs.wager_questions), phase
                    ),
                }
        return {}
