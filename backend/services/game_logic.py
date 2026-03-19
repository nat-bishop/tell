"""Pure game logic — state transitions, vote resolution, validation."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schemas.prompts import BrainTestChallengeSpec

from schemas.api_models import (
    GameOverEvent,
    PhaseChangedEvent,
    VoteResultsEvent,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import (
    BrainTestChallenge,
    GamePhase,
    Player,
    RoundState,
    RoundType,
    TellGameState,
)


def get_player_by_id(state: TellGameState, player_id: str) -> Player | None:
    return next((p for p in state.players if p.id == player_id), None)


def fill_missing_answers(state: TellGameState) -> None:
    """Fill NO_RESPONSE for players who haven't answered."""
    rs = state.current_round
    if not rs:
        return
    for p in state.players:
        if p.id not in rs.answers:
            rs.answers[p.id] = NO_RESPONSE


class MinigameMeta:
    """Metadata for a round type, used by round selection."""

    __slots__ = ("min_players",)

    def __init__(self, *, min_players: int) -> None:
        self.min_players = min_players


MINIGAMES: dict[RoundType, MinigameMeta] = {
    RoundType.TASK: MinigameMeta(min_players=2),
    RoundType.BRAIN_TEST: MinigameMeta(min_players=2),
}


def select_next_round_type(
    last_round_type: RoundType | None,
) -> RoundType:
    """Pick the next round type dynamically.

    Rules:
    - No repeat of previous round type
    - Random from remaining eligible types
    """
    eligible: list[RoundType] = []

    for rt in MINIGAMES:
        if rt == last_round_type:
            continue
        eligible.append(rt)

    if not eligible:
        return RoundType.TASK

    return random.choice(eligible)


# Interstitial hold times (seconds) added to phase deadlines so
# clients can display a phase-transition overlay without eating action time.
# The frontend derives its dismiss timing from the action_starts_at timestamp.
_INTERSTITIAL_HOLD: dict[GamePhase, int] = {
    GamePhase.PROMPT: 5,  # round start — staggered visual beats
    GamePhase.BRAIN_TEST: 5,  # round start
    GamePhase.BRAIN_TEST_RESULTS: 2,
    GamePhase.VOTE: 3,
    GamePhase.VOTE_RESULTS: 2,
}


def get_interstitial_hold(phase: GamePhase) -> int:
    """Extra seconds added to phase deadline for client interstitial overlay."""
    return _INTERSTITIAL_HOLD.get(phase, 0)


def get_phase_duration(
    settings, phase: GamePhase, round_type: RoundType | None = None
) -> int | None:
    """Get the duration for a given phase."""
    if phase == GamePhase.PROMPT:
        return settings.prompt_duration
    if phase == GamePhase.VOTE:
        return settings.vote_duration
    if phase == GamePhase.VOTE_RESULTS:
        return settings.vote_results_duration
    if phase == GamePhase.BRAIN_TEST:
        return settings.brain_test_duration
    if phase == GamePhase.BRAIN_TEST_RESULTS:
        return settings.brain_test_results_duration
    return None


def _transition_to_phase(state: TellGameState, phase: GamePhase, duration: int) -> TellGameState:
    """Move to a phase with a deadline (includes interstitial hold)."""
    state.phase = phase
    state.phase_deadline = datetime.now(UTC) + timedelta(
        seconds=duration + get_interstitial_hold(phase)
    )
    return state


def transition_to_brain_test(
    state: TellGameState,
    challenges: list[BrainTestChallengeSpec],
    duration: int,
) -> TellGameState:
    """Start a new Brain Test round."""
    from schemas.game_state import BrainTestChallenge

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
    state.phase = GamePhase.BRAIN_TEST
    state.phase_deadline = datetime.now(UTC) + timedelta(
        seconds=duration + get_interstitial_hold(GamePhase.BRAIN_TEST)
    )
    return state


def transition_to_brain_test_results(state: TellGameState, duration: int) -> TellGameState:
    return _transition_to_phase(state, GamePhase.BRAIN_TEST_RESULTS, duration)


def transition_to_task_prompt(state: TellGameState, duration: int) -> TellGameState:
    """Start a new Task round — single prompt for all players."""
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
    return _transition_to_phase(state, GamePhase.PROMPT, duration)


def transition_to_vote(state: TellGameState, duration: int) -> TellGameState:
    return _transition_to_phase(state, GamePhase.VOTE, duration)


def transition_to_vote_results(state: TellGameState, duration: int) -> TellGameState:
    return _transition_to_phase(state, GamePhase.VOTE_RESULTS, duration)


def tally_gallery_votes(state: TellGameState) -> dict[str, int]:
    """Count votes received per player. Returns player_id → vote count."""
    vote_counts: dict[str, int] = {p.id: 0 for p in state.players}
    rs = state.current_round
    if rs:
        for target_id in rs.gallery_votes.values():
            if target_id in vote_counts:
                vote_counts[target_id] += 1
    return vote_counts


def resolve_gallery_votes(state: TellGameState, seq_fn) -> tuple[TellGameState, VoteResultsEvent]:
    """Tally gallery votes. Each vote received = -1 point."""
    vote_counts = tally_gallery_votes(state)
    # Apply penalties
    player_map = {p.id: p for p in state.players}
    for pid, count in vote_counts.items():
        if count > 0 and pid in player_map:
            player_map[pid].score -= count
    scores = {p.id: p.score for p in state.players}
    return state, VoteResultsEvent(seq=seq_fn(), vote_counts=vote_counts, scores=scores)


# ---------------------------------------------------------------------------
# Brain Test scoring (multiple choice — pure correctness)
# ---------------------------------------------------------------------------


def score_brain_test(challenges: list[BrainTestChallenge]) -> dict[str, int]:
    """Score all challenges. 1 point per correct answer (selected_index == correct_index)."""
    totals: dict[str, int] = {}
    for ch in challenges:
        for pid, selected in ch.responses.items():
            totals[pid] = totals.get(pid, 0) + (1 if selected == ch.correct_index else 0)
    return totals


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
    state: TellGameState, winner: str, winner_ids: list[str], seq_fn
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


def make_phase_changed_event(
    state: TellGameState, seq: int, phase_duration: int | None = None, **extra
) -> PhaseChangedEvent:
    action_starts_at = None
    if state.phase_deadline and phase_duration:
        action_starts_at = (state.phase_deadline - timedelta(seconds=phase_duration)).isoformat()
    return PhaseChangedEvent(
        seq=seq,
        phase=state.phase.value,
        round_number=state.round_number,
        phase_deadline=state.phase_deadline.isoformat() if state.phase_deadline else None,
        phase_duration=phase_duration,
        action_starts_at=action_starts_at,
        **extra,
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
    """Get the round type for the next round (dynamic selection)."""
    last = state.round_types[-1] if state.round_types else None
    return select_next_round_type(last)


def build_state_sync(
    state: TellGameState, player_id: str, seq: int, phase_duration: int | None = None
) -> dict:
    """Build a StateSyncEvent payload for a specific player."""
    round_state = state.current_round
    answers: dict[str, str] = {}
    my_answer: str | None = None
    prompt_text: str | None = None
    prompt_category: str | None = None
    round_type: str | None = None
    my_vote: str | None = None

    if round_state:
        prompt_text = round_state.prompt_text
        prompt_category = round_state.prompt_category
        round_type = round_state.round_type

        # Answers visible during VOTE, VOTE_RESULTS, and GAME_OVER
        if state.phase in (GamePhase.VOTE, GamePhase.VOTE_RESULTS, GamePhase.GAME_OVER):
            answers = round_state.answers

        if state.phase == GamePhase.PROMPT and player_id in round_state.answers:
            my_answer = round_state.answers[player_id]

        # Include player's own vote during VOTE phase
        if state.phase == GamePhase.VOTE and player_id in round_state.gallery_votes:
            my_vote = round_state.gallery_votes[player_id]

    player_obj = get_player_by_id(state, player_id)
    is_host = player_obj.is_host if player_obj else False

    scores = {p.id: p.score for p in state.players}

    return {
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
        "phase_duration": phase_duration,
        "winner": state.winner,
        "winner_ids": state.winner_ids,
        "is_host": is_host,
        "my_answer": my_answer,
        "my_vote": my_vote,
        "action_starts_at": (
            (state.phase_deadline - timedelta(seconds=phase_duration)).isoformat()
            if state.phase_deadline and phase_duration
            else None
        ),
    }
