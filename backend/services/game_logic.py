"""Pure game logic — state transitions, vote resolution, validation."""

from __future__ import annotations

import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.minigames import MINIGAME_REGISTRY, get_handler
from schemas.api_models import (
    GameOverEvent,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import (
    GamePhase,
    Player,
    RoundType,
    TellGameState,
)


def get_player_by_id(state: TellGameState, player_id: str) -> Player | None:
    return next((p for p in state.players if p.id == player_id), None)


def get_answer_total(state: TellGameState) -> int:
    """How many answers are expected this compose step."""
    rs = state.current_round
    if rs and rs.round_type == RoundType.SIGNAL:
        return len(rs.signal_player_order)
    return len(state.players)


def fill_missing_answers(state: TellGameState) -> None:
    """Fill NO_RESPONSE for players who haven't answered."""
    rs = state.current_round
    if not rs:
        return
    for p in state.players:
        if p.id not in rs.answers:
            rs.answers[p.id] = NO_RESPONSE


def select_next_round_type(
    last_round_type: RoundType | None,
) -> RoundType:
    """Pick the next round type dynamically.

    Rules:
    - No repeat of previous round type
    - Random from remaining eligible types
    """
    eligible: list[RoundType] = []

    for rt in MINIGAME_REGISTRY:
        if rt == last_round_type:
            continue
        eligible.append(rt)

    if not eligible:
        return random.choice(list(MINIGAME_REGISTRY.keys()))

    return random.choice(eligible)


def get_current_step(state: TellGameState) -> dict | None:
    """Get the current step def dict, or None if not in a round."""
    if not state.round_step_defs or state.current_step_index >= len(state.round_step_defs):
        return None
    return state.round_step_defs[state.current_step_index]


def get_step_name(state: TellGameState) -> str | None:
    """Get the current step name, or None."""
    step = get_current_step(state)
    return step["name"] if step else None


def transition_to_step(
    state: TellGameState,
    step_index: int,
) -> None:
    """Move to a step: set step index and deadline from step duration."""
    state.current_step_index = step_index
    step = state.round_step_defs[step_index]
    state.phase_deadline = datetime.now(UTC) + timedelta(seconds=step["duration"])


def get_final_rankings(state: TellGameState) -> list[tuple[str, int]]:
    """Return list of (player_id, score) sorted by score descending. Ties included."""
    return sorted(
        [(p.id, p.score) for p in state.players],
        key=lambda x: x[1],
        reverse=True,
    )


def check_game_over(state: TellGameState) -> tuple[str, list[str]] | None:
    """Check if the game should end.

    Triggers when round_number >= total_rounds.
    Returns ("winners", [player_ids_with_highest_score]) or None.
    """
    if state.round_number < state.total_rounds:
        return None

    rankings = get_final_rankings(state)
    if not rankings:
        return None

    top_score = rankings[0][1]
    winner_ids = [pid for pid, score in rankings if score == top_score]
    return ("winners", winner_ids)


def make_game_over_event(
    state: TellGameState, winner: str, winner_ids: list[str], seq_fn: Callable[[], int]
) -> GameOverEvent:
    players_revealed = []
    for p in state.players:
        players_revealed.append(
            {
                "id": p.id,
                "alias": p.alias,
                "role": p.role.value,
                "score": p.score,
            }
        )
    scores = {p.id: p.score for p in state.players}
    return GameOverEvent(
        seq=seq_fn(),
        winner=winner,
        winner_ids=winner_ids,
        players=players_revealed,
        scores=scores,
    )


def sanitize_players_for_client(state: TellGameState) -> list[dict]:
    result = []
    for p in state.players:
        d: dict = {
            "id": p.id,
            "alias": p.alias,
            "is_connected": p.is_connected,
            "is_host": p.is_host,
            "score": p.score,
        }
        # Only reveal role at game over
        if state.phase == GamePhase.GAME_OVER:
            d["role"] = p.role.value
        result.append(d)
    return result


def get_next_round_type(state: TellGameState) -> RoundType:
    """Get the round type for the next round.

    Uses forced_round_sequence if configured, otherwise random selection.
    """
    round_index = len(state.round_types)
    if state.forced_round_sequence and round_index < len(state.forced_round_sequence):
        return state.forced_round_sequence[round_index]

    last = state.round_types[-1] if state.round_types else None
    return select_next_round_type(last)


def tally_gallery_votes(state: TellGameState) -> dict[str, int]:
    """Count votes received per player. Returns player_id → vote count."""
    vote_counts: dict[str, int] = {p.id: 0 for p in state.players}
    rs = state.current_round
    if rs:
        for target_id in rs.gallery_votes.values():
            if target_id in vote_counts:
                vote_counts[target_id] += 1
    return vote_counts


def build_state_sync(state: TellGameState, player_id: str, seq: int) -> dict:
    """Build a StateSyncEvent payload for a specific player."""
    round_state = state.current_round
    answers: dict[str, str] = {}
    my_answer: str | None = None
    prompt_text: str | None = None
    prompt_category: str | None = None
    round_type: str | None = None
    my_vote: str | None = None

    step = get_current_step(state)
    step_name = step["name"] if step else None

    if round_state:
        prompt_text = round_state.prompt_text
        prompt_category = round_state.prompt_category
        round_type = round_state.round_type

        # Answers visible after compose steps
        in_compose = step_name in ("compose", "signal_compose", "preroll", None)
        if (state.phase == GamePhase.ROUND and not in_compose) or (
            state.phase == GamePhase.GAME_OVER
        ):
            answers = round_state.answers

        # Own answer visible during compose
        if step_name in ("compose", "signal_compose") and player_id in round_state.answers:
            my_answer = round_state.answers[player_id]

        # Include player's own vote during vote step
        if step_name == "vote" and player_id in round_state.gallery_votes:
            my_vote = round_state.gallery_votes[player_id]

    player_obj = get_player_by_id(state, player_id)
    is_host = player_obj.is_host if player_obj else False

    scores = {p.id: p.score for p in state.players}

    duration = step["duration"] if step else None

    result: dict[str, Any] = {
        "event_type": "state_sync",
        "seq": seq,
        "game_id": state.game_id,
        "phase": state.phase.value,
        "players": sanitize_players_for_client(state),
        "round_number": state.round_number,
        "total_rounds": state.total_rounds,
        "prompt_text": prompt_text,
        "prompt_category": prompt_category,
        "round_type": round_type,
        "answers": answers,
        "scores": scores,
        "phase_deadline": state.phase_deadline.isoformat() if state.phase_deadline else None,
        "phase_duration": duration,
        "winner": state.winner,
        "winner_ids": state.winner_ids,
        "is_host": is_host,
        "my_answer": my_answer,
        "my_vote": my_vote,
        "timers_disabled": state.timers_disabled,
        # Step fields
        "step_name": step_name,
        "step_index": state.current_step_index if step else None,
        "component": step["component"] if step else None,
    }

    # Merge handler-specific reconnection data
    if round_state and round_type:
        try:
            handler = get_handler(RoundType(round_type))
            extras = handler.build_state_sync_extras(state, player_id)
            result.update(extras)
        except (KeyError, ValueError):
            pass

    return result
