"""Signal (Drawful-style) minigame handler.

3 random transmitters get secret phrases + a shared constraint.
Each transmitter transforms their phrase. Then 3 sub-rounds:
one per transmitter, all non-transmitters guess simultaneously.
LLM judges guesses on a 0/1/2 scale.
"""

from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.config import Settings

import structlog

from backend.minigames.base import (
    MinigameHandler,
    StepDef,
    get_step_context,
    get_step_info,
    parse_sub_index,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import (
    RoundState,
    RoundType,
    TellGameState,
)

log = structlog.get_logger(__name__)

NUM_TRANSMITTERS = 3


class SignalHandler(MinigameHandler):
    round_type = RoundType.SIGNAL
    min_players = 2

    def setup_round(self, state: TellGameState, settings: Settings) -> None:
        from schemas.prompts import select_signal_constraint, select_signal_phrases

        state.round_number += 1

        idx, constraint = select_signal_constraint(state.used_signal_constraint_indices)
        state.used_signal_constraint_indices.append(idx)

        # Select transmitters — avoid repeats across rounds
        player_ids = [p.id for p in state.players]
        available = [pid for pid in player_ids if pid not in state.used_signal_transmitter_ids]
        if len(available) < NUM_TRANSMITTERS:
            # Not enough unused — reset tracking
            state.used_signal_transmitter_ids.clear()
            available = list(player_ids)

        num_tx = min(NUM_TRANSMITTERS, len(available))
        transmitter_ids = random.sample(available, num_tx)
        state.used_signal_transmitter_ids.extend(transmitter_ids)

        # Only transmitters get phrases
        phrase_selections = select_signal_phrases(num_tx, state.used_signal_phrase_indices)
        signal_phrases: dict[str, str] = {}
        for (phrase_idx, phrase), pid in zip(phrase_selections, transmitter_ids, strict=False):
            state.used_signal_phrase_indices.append(phrase_idx)
            signal_phrases[pid] = phrase

        state.current_round = RoundState(
            round_number=state.round_number,
            prompt_text=constraint.instruction,
            prompt_category="signal",
            round_type=RoundType.SIGNAL,
            signal_constraint=constraint.text,
            signal_phrases=signal_phrases,
            signal_player_order=transmitter_ids,
        )

    def get_steps(self, state: TellGameState, settings: Settings) -> list[StepDef]:
        rs = state.current_round
        num_tx = len(rs.signal_player_order) if rs else NUM_TRANSMITTERS
        dur = settings.signal_sub_round_duration

        steps: list[StepDef] = [
            StepDef(
                name="compose", duration=settings.signal_prompt_duration, component="signal_compose"
            ),
        ]
        for i in range(num_tx):
            steps.append(StepDef(name=f"signal_guess_{i}", duration=dur, component="signal_guess"))
        steps.append(
            StepDef(
                name="results",
                duration=settings.signal_results_duration,
                component="signal_results",
                is_results=True,
            )
        )
        return steps

    async def on_step_start(self, game_id: str, step_index: int) -> None:
        ctx = get_step_context(game_id, step_index)
        if not ctx:
            return
        _session, rs, step = ctx
        step_name = step["name"]

        if step_name == "compose":
            from backend.services.ai_scheduler import schedule_ai_answers

            await schedule_ai_answers(game_id)

        elif step_name.startswith("signal_guess_"):
            tx_index = parse_sub_index(step_name)
            if tx_index is not None:
                rs.current_sub_round = tx_index
                if tx_index < len(rs.signal_player_order):
                    featured_pid = rs.signal_player_order[tx_index]
                    from backend.services.ai_scheduler import on_signal_sub_round

                    await on_signal_sub_round(game_id, tx_index, featured_pid)

    async def on_step_end(self, game_id: str, step_index: int) -> None:
        ctx = get_step_context(game_id, step_index)
        if not ctx:
            return
        session, _rs, step = ctx
        if step["name"] == "compose":
            from backend.services.game_logic import fill_missing_answers

            fill_missing_answers(session.state)

    def step_event_extras(self, state: TellGameState, step_index: int) -> dict:
        info = get_step_info(state, step_index)
        if not info:
            return {}
        rs, step = info
        step_name = step["name"]

        if step_name == "compose":
            return {
                "prompt_text": rs.prompt_text,
                "constraint": rs.signal_constraint,
                "transmitter_ids": rs.signal_player_order,
            }
        elif step_name.startswith("signal_guess_"):
            tx_index = parse_sub_index(step_name)
            if tx_index is not None and tx_index < len(rs.signal_player_order):
                featured_pid = rs.signal_player_order[tx_index]
                alias_map = {p.id: p.alias for p in state.players}
                transformation = rs.answers.get(featured_pid, NO_RESPONSE)
                return {
                    "featured_player_id": featured_pid,
                    "featured_alias": alias_map.get(featured_pid, featured_pid),
                    "transformation": transformation,
                    "constraint": rs.signal_constraint,
                    "total_transmitters": len(rs.signal_player_order),
                    "sub_round_index": tx_index,
                }
        return {}

    async def finalize_round(self, game_id: str) -> None:
        """Batch-judge all guesses via LLM, parallelized per transmitter."""
        from backend.api.deps import get_connection_manager, get_game_repository

        cm = get_connection_manager()
        lock = cm.get_lock(game_id)

        # Snapshot data under lock
        async with lock:
            session = get_game_repository().get(game_id)
            if not session or not session.state.current_round:
                return
            rs = session.state.current_round
            guesses_snapshot = {pid: dict(gs) for pid, gs in rs.signal_guesses.items()}
            phrases_snapshot = dict(rs.signal_phrases)
            order_snapshot = list(rs.signal_player_order)

        # Judge outside lock
        from backend.llm.agents import judge_signal_guesses

        async def judge_one(featured_pid: str) -> tuple[str, dict[str, int]]:
            guesses = guesses_snapshot.get(featured_pid, {})
            phrase = phrases_snapshot.get(featured_pid, "")
            if not guesses:
                return featured_pid, {}
            try:
                result = await judge_signal_guesses(phrase, guesses, game_id=game_id)
                return featured_pid, result
            except Exception:
                log.exception("signal_judge_error", game_id=game_id, featured_pid=featured_pid)
                return featured_pid, {}

        tasks = [judge_one(pid) for pid in order_snapshot]
        judge_results = await asyncio.gather(*tasks)

        # Store under lock
        async with lock:
            session = get_game_repository().get(game_id)
            if not session:
                return
            rs = session.state.current_round
            if not rs:
                return
            for featured_pid, judgments in judge_results:
                rs.signal_judgments[featured_pid] = judgments

    def build_results(self, state: TellGameState) -> tuple[dict, dict[str, int]]:
        rs = state.current_round
        if not rs:
            return {}, {}

        alias_map = {p.id: p.alias for p in state.players}
        score_deltas: dict[str, int] = {}
        results: dict[str, dict] = {}

        for featured_pid in rs.signal_player_order:
            phrase = rs.signal_phrases.get(featured_pid, "")
            transformation = rs.answers.get(featured_pid, NO_RESPONSE)
            guesses = rs.signal_guesses.get(featured_pid, {})
            judgments = rs.signal_judgments.get(featured_pid, {})

            # Guesser scoring: judge score * 50 (0→0, 1→50, 2→100)
            guesser_points: dict[str, int] = {}
            for guesser_id, score in judgments.items():
                pts = score * 50
                guesser_points[guesser_id] = pts
                score_deltas[guesser_id] = score_deltas.get(guesser_id, 0) + pts

            # Transmitter scoring: avg of guesser points (integer division)
            num_guessers = len(guesser_points)
            if num_guessers > 0:
                total_guesser_pts = sum(guesser_points.values())
                tx_pts = total_guesser_pts // num_guessers
                score_deltas[featured_pid] = score_deltas.get(featured_pid, 0) + tx_pts
            else:
                tx_pts = 0

            # Build display data
            guesses_display: dict[str, str] = {}
            judgments_display: dict[str, int] = {}
            for gid, guess in guesses.items():
                guesses_display[alias_map.get(gid, gid)] = guess
                judgments_display[alias_map.get(gid, gid)] = judgments.get(gid, 0)

            results[featured_pid] = {
                "original_phrase": phrase,
                "transformation": transformation,
                "featured_alias": alias_map.get(featured_pid, featured_pid),
                "guesses": guesses_display,
                "judgments": judgments_display,
                "transmitter_score": tx_pts,
            }

        payload = {
            "constraint": rs.signal_constraint,
            "results": results,
        }
        return payload, score_deltas

    def build_state_sync_extras(self, state: TellGameState, player_id: str) -> dict:
        info = get_step_info(state, state.current_step_index)
        if not info:
            return super().build_state_sync_extras(state, player_id)

        rs, step = info
        transmitter_ids = set(rs.signal_player_order)
        step_name = step["name"]

        if step_name == "compose":
            if player_id in transmitter_ids:
                phrase = rs.signal_phrases.get(player_id, "")
                if phrase:
                    return {"signal_phrase": phrase, "is_transmitter": True}
            return {"is_transmitter": player_id in transmitter_ids}

        if step_name.startswith("signal_guess_"):
            tx_index = parse_sub_index(step_name)
            if tx_index is not None and tx_index < len(rs.signal_player_order):
                featured_pid = rs.signal_player_order[tx_index]
                alias_map = {p.id: p.alias for p in state.players}
                transformation = rs.answers.get(featured_pid, NO_RESPONSE)
                return {
                    "answers": {
                        pid: ans for pid, ans in rs.answers.items() if pid in transmitter_ids
                    },
                    "sub_round_index": tx_index,
                    "sub_round_payload": {
                        "round_type": "signal",
                        "featured_player_id": featured_pid,
                        "featured_alias": alias_map.get(featured_pid, featured_pid),
                        "transformation": transformation,
                        "constraint": rs.signal_constraint,
                        "total_transmitters": len(rs.signal_player_order),
                    },
                    "is_transmitter": player_id in transmitter_ids,
                }

        return super().build_state_sync_extras(state, player_id)
