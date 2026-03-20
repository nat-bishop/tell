"""Signal (Drawful-style) minigame handler."""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.config import Settings

import structlog

from backend.minigames.base import MinigameHandler, MinigameMeta
from schemas.constants import NO_RESPONSE
from schemas.game_state import (
    RoundState,
    RoundType,
    TellGameState,
)

log = structlog.get_logger(__name__)


class SignalHandler(MinigameHandler):
    round_type = RoundType.SIGNAL
    meta = MinigameMeta(
        min_players=2,
        has_prompt=True,
        has_results=True,
        active_interstitial=3,
        results_interstitial=2,
    )

    def setup_round(self, state: TellGameState, settings: Settings) -> None:
        from schemas.prompts import select_signal_constraint, select_signal_phrases

        state.round_number += 1

        idx, constraint = select_signal_constraint(state.used_signal_constraint_indices)
        state.used_signal_constraint_indices.append(idx)

        player_ids = [p.id for p in state.players]
        phrase_selections = select_signal_phrases(len(player_ids), state.used_signal_phrase_indices)

        signal_phrases: dict[str, str] = {}
        for (phrase_idx, phrase), pid in zip(phrase_selections, player_ids, strict=False):
            state.used_signal_phrase_indices.append(phrase_idx)
            signal_phrases[pid] = phrase

        state.current_round = RoundState(
            round_number=state.round_number,
            prompt_text=constraint.instruction,
            prompt_category="signal",
            round_type=RoundType.SIGNAL,
            signal_constraint=constraint.text,
            signal_phrases=signal_phrases,
            signal_player_order=player_ids.copy(),
        )

    def get_prompt_duration(self, settings: Settings) -> int:
        return settings.signal_prompt_duration

    def get_active_duration(self, settings: Settings) -> int:
        return settings.signal_safety_duration

    def get_results_duration(self, settings: Settings) -> int:
        return settings.signal_results_duration

    def active_event_extras(self, state: TellGameState) -> dict:
        return {}

    async def on_active_start(self, game_id: str) -> None:
        from backend.services.ai_scheduler import register_task

        task = asyncio.create_task(self._signal_loop(game_id))
        register_task(game_id, task)

    async def _signal_loop(self, game_id: str) -> None:
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
            sub_duration = settings.signal_sub_round_duration
            lock = cm.get_lock(game_id)

            # Snapshot player order under lock
            async with lock:
                session = repo.get(game_id)
                if not session:
                    return
                rs = session.state.current_round
                if not rs:
                    return
                player_order = list(rs.signal_player_order)
                alias_map = {p.id: p.alias for p in session.state.players}

            for i, featured_pid in enumerate(player_order):
                async with lock:
                    session = repo.get(game_id)
                    if not session:
                        return
                    state = session.state
                    if state.phase != GamePhase.ACTIVE:
                        return
                    rs = state.current_round
                    if not rs:
                        return

                    rs.current_sub_round = i
                    sub_deadline = dt.datetime.now(dt.UTC) + dt.timedelta(seconds=sub_duration)
                    state.phase_deadline = sub_deadline

                    transformation = rs.answers.get(featured_pid, NO_RESPONSE)

                    await cm.broadcast(
                        game_id,
                        SubRoundEvent(
                            seq=session.next_seq(),
                            round_type="signal",
                            sub_round_index=i,
                            payload={
                                "featured_player_id": featured_pid,
                                "featured_alias": alias_map.get(featured_pid, featured_pid),
                                "transformation": transformation,
                                "constraint": rs.signal_constraint,
                            },
                            sub_deadline=sub_deadline.isoformat(),
                            phase_duration=sub_duration,
                        ),
                    )

                # Schedule AI guesses outside lock
                from backend.services.ai_scheduler import on_signal_sub_round

                await on_signal_sub_round(game_id, i, featured_pid)

                await asyncio.sleep(sub_duration)

            # Snapshot guesses under lock before judging (avoid race with late submissions)
            async with lock:
                session = repo.get(game_id)
                if not session or not session.state.current_round:
                    return
                rs = session.state.current_round
                guesses_snapshot = {pid: dict(gs) for pid, gs in rs.signal_guesses.items()}
                phrases_snapshot = dict(rs.signal_phrases)
                player_order_snapshot = list(rs.signal_player_order)

            # All sub-rounds done — judge all guesses (outside lock)
            await self._judge_all_guesses(
                game_id, player_order_snapshot, guesses_snapshot, phrases_snapshot
            )

            # Transition to results
            async with lock:
                session = repo.get(game_id)
                if not session:
                    return
                if session.state.phase != GamePhase.ACTIVE:
                    return
                get_timer_manager().cancel_timer(game_id)

                from backend.services.transitions import do_active_complete

                await do_active_complete(game_id, session)

        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("signal_loop_error", game_id=game_id)

    async def _judge_all_guesses(
        self,
        game_id: str,
        player_order: list[str],
        guesses_snapshot: dict[str, dict[str, str]],
        phrases_snapshot: dict[str, str],
    ) -> None:
        """Batch-judge all guesses via LLM, parallelized per featured player."""
        from backend.api.deps import get_connection_manager

        cm = get_connection_manager()

        from backend.llm.agents import judge_signal_guesses

        async def judge_one(featured_pid: str) -> tuple[str, dict[str, bool]]:
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

        tasks = [judge_one(pid) for pid in player_order]
        judge_results = await asyncio.gather(*tasks)

        # Store under lock
        from backend.api.deps import get_game_repository

        lock = cm.get_lock(game_id)
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

            # Guesser scoring: +1 per correct guess
            for guesser_id, correct in judgments.items():
                if correct:
                    score_deltas[guesser_id] = score_deltas.get(guesser_id, 0) + 1

            # Transmitter bonus: +1 if >= half of guessers got it right
            num_guessers = len(guesses)
            num_correct = sum(1 for v in judgments.values() if v)
            transmitter_bonus = num_guessers > 0 and num_correct >= num_guessers / 2

            if transmitter_bonus:
                score_deltas[featured_pid] = score_deltas.get(featured_pid, 0) + 1

            # Build guesses with aliases for display
            guesses_display: dict[str, str] = {}
            judgments_display: dict[str, bool] = {}
            for gid, guess in guesses.items():
                guesses_display[alias_map.get(gid, gid)] = guess
                judgments_display[alias_map.get(gid, gid)] = judgments.get(gid, False)

            results[featured_pid] = {
                "original_phrase": phrase,
                "transformation": transformation,
                "featured_alias": alias_map.get(featured_pid, featured_pid),
                "guesses": guesses_display,
                "judgments": judgments_display,
                "transmitter_bonus": transmitter_bonus,
            }

        payload = {
            "constraint": rs.signal_constraint,
            "results": results,
        }
        return payload, score_deltas

    def build_state_sync_extras(self, state: TellGameState, player_id: str) -> dict:
        from schemas.game_state import GamePhase

        rs = state.current_round
        if not rs:
            return {}

        if state.phase == GamePhase.PROMPT:
            phrase = rs.signal_phrases.get(player_id, "")
            if phrase:
                return {"signal_phrase": phrase}

        if state.phase == GamePhase.ACTIVE:
            idx = rs.current_sub_round
            if idx < len(rs.signal_player_order):
                featured_pid = rs.signal_player_order[idx]
                alias_map = {p.id: p.alias for p in state.players}
                transformation = rs.answers.get(featured_pid, NO_RESPONSE)
                return {
                    "sub_round_index": idx,
                    "sub_round_payload": {
                        "round_type": "signal",
                        "featured_player_id": featured_pid,
                        "featured_alias": alias_map.get(featured_pid, featured_pid),
                        "transformation": transformation,
                        "constraint": rs.signal_constraint,
                    },
                }

        return {}
