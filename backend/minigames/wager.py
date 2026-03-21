"""Wager (numerical estimation + social betting) minigame handler."""

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
    RoundState,
    RoundType,
    TellGameState,
    WagerQuestion,
)


def _get_closest_ids(q: WagerQuestion) -> list[str]:
    """Return player IDs with the closest guess to the correct answer."""
    if not q.guesses:
        return []
    correct = q.correct_answer
    min_dist = min(abs(g - correct) for g in q.guesses.values())
    return [pid for pid, g in q.guesses.items() if abs(g - correct) == min_dist]


def _build_sub_round_payload(q: WagerQuestion, q_idx: int, num_questions: int, phase: str) -> dict:
    """Build the payload dict for a wager step event."""
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
    """Score all wager questions. +100 closest guess, +100 correct bet per question."""
    totals: dict[str, int] = {}
    for q in questions:
        closest = set(_get_closest_ids(q))
        for pid in closest:
            totals[pid] = totals.get(pid, 0) + 100
        for pid, target in q.bets.items():
            if target in closest:
                totals[pid] = totals.get(pid, 0) + 100
    return totals


class WagerHandler(MinigameHandler):
    round_type = RoundType.WAGER
    min_players = 3

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

    def get_steps(self, state: TellGameState, settings: Settings) -> list[StepDef]:
        num = settings.wager_questions
        dur = settings.wager_sub_round_duration
        steps: list[StepDef] = []
        for i in range(num):
            steps.append(StepDef(name=f"guess_{i}", duration=dur, component="wager"))
            steps.append(StepDef(name=f"bet_{i}", duration=dur, component="wager"))
        steps.append(
            StepDef(
                name="results",
                duration=settings.wager_results_duration,
                component="wager_results",
                is_results=True,
            )
        )
        return steps

    async def on_step_start(self, game_id: str, state: TellGameState, step_index: int) -> None:
        info = get_step_info(state, step_index)
        if not info:
            return
        rs, step = info
        step_name = step["name"]
        q_idx = parse_sub_index(step_name)
        if q_idx is None:
            return

        rs.current_sub_round = step_index

        if step_name.startswith("guess_"):
            from backend.services.ai_scheduler import on_wager_guess

            await on_wager_guess(game_id, q_idx)

        elif step_name.startswith("bet_"):
            from backend.services.ai_scheduler import on_wager_bet

            await on_wager_bet(game_id, q_idx)

    def step_event_extras(self, state: TellGameState, step_index: int) -> dict:
        info = get_step_info(state, step_index)
        if not info:
            return {}
        rs, step = info
        step_name = step["name"]
        q_idx = parse_sub_index(step_name)
        if q_idx is None or q_idx >= len(rs.wager_questions):
            return {}

        q = rs.wager_questions[q_idx]
        if step_name.startswith("guess_"):
            return _build_sub_round_payload(q, q_idx, len(rs.wager_questions), "guess")
        elif step_name.startswith("bet_"):
            return _build_sub_round_payload(q, q_idx, len(rs.wager_questions), "bet")
        return {}

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
        """Provide current sub-round info for reconnection during gameplay steps."""
        info = get_step_info(state, state.current_step_index)
        if not info:
            return super().build_state_sync_extras(state, player_id)

        rs, step = info
        step_name = step["name"]

        if step_name.startswith(("guess_", "bet_")):
            q_idx = parse_sub_index(step_name)
            if q_idx is not None and q_idx < len(rs.wager_questions):
                q = rs.wager_questions[q_idx]
                phase = "guess" if step_name.startswith("guess") else "bet"
                return {
                    "sub_round_index": state.current_step_index,
                    "sub_round_payload": _build_sub_round_payload(
                        q, q_idx, len(rs.wager_questions), phase
                    ),
                }

        return super().build_state_sync_extras(state, player_id)
