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
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import (
    BrainTestChallenge,
    GamePhase,
    Matchup,
    Player,
    RoundState,
    RoundType,
    TellGameState,
)


def get_player_by_id(state: TellGameState, player_id: str) -> Player | None:
    return next((p for p in state.players if p.id == player_id), None)


def fill_missing_answers(state: TellGameState) -> None:
    """Fill NO_RESPONSE for players who haven't answered.

    For matchup Task rounds, only paired players need answers (bye player excluded).
    """
    rs = state.current_round
    if not rs:
        return
    for p in state.players:
        if p.id == rs.bye_player_id:
            continue
        if p.id not in rs.answers:
            rs.answers[p.id] = NO_RESPONSE


class MinigameMeta:
    """Metadata for a round type, used by round selection and phase transitions."""

    __slots__ = (
        "active_interstitial",
        "has_prompt",
        "has_results",
        "min_players",
        "results_interstitial",
    )

    def __init__(
        self,
        *,
        min_players: int,
        has_prompt: bool = True,
        has_results: bool = False,
        active_interstitial: int = 3,
        results_interstitial: int = 0,
    ) -> None:
        self.min_players = min_players
        self.has_prompt = has_prompt
        self.has_results = has_results
        self.active_interstitial = active_interstitial
        self.results_interstitial = results_interstitial


MINIGAMES: dict[RoundType, MinigameMeta] = {
    RoundType.TASK: MinigameMeta(
        min_players=3,
        has_prompt=True,
        has_results=False,
        active_interstitial=3,
        results_interstitial=0,
    ),
    RoundType.BRAIN_TEST: MinigameMeta(
        min_players=2,
        has_prompt=False,
        has_results=True,
        active_interstitial=5,
        results_interstitial=2,
    ),
}


def select_next_round_type(
    last_round_type: RoundType | None,
) -> RoundType:
    """Pick the next round type dynamically.

    Rules:
    - Exclude types where player count < min_players (not checked here — caller's job)
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
}


def get_interstitial_hold(phase: GamePhase, round_type: RoundType | None = None) -> int:
    """Extra seconds added to phase deadline for client interstitial overlay."""
    if phase in (GamePhase.ACTIVE, GamePhase.RESULTS) and round_type:
        meta = MINIGAMES.get(round_type)
        if meta:
            if phase == GamePhase.ACTIVE:
                return meta.active_interstitial
            return meta.results_interstitial
    return _INTERSTITIAL_HOLD.get(phase, 0)


def get_phase_duration(
    settings, phase: GamePhase, round_type: RoundType | None = None
) -> int | None:
    """Get the duration for a given phase, accounting for round-type-specific overrides."""
    if phase == GamePhase.PROMPT:
        reading = settings.prompt_reading_duration
        if round_type == RoundType.TASK:
            return settings.task_prompt_duration + reading
        return settings.prompt_duration + reading
    if phase == GamePhase.ACTIVE:
        if round_type == RoundType.TASK:
            return settings.matchup_duration
        if round_type == RoundType.BRAIN_TEST:
            return settings.brain_test_duration
        return None
    if phase == GamePhase.RESULTS:
        if round_type == RoundType.BRAIN_TEST:
            return settings.brain_test_results_duration
        return None
    return None


def _transition_to_phase(
    state: TellGameState, phase: GamePhase, duration: int, round_type: RoundType | None = None
) -> TellGameState:
    """Move to a phase with a deadline (includes interstitial hold)."""
    state.phase = phase
    state.phase_deadline = datetime.now(UTC) + timedelta(
        seconds=duration + get_interstitial_hold(phase, round_type)
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
    state.phase = GamePhase.ACTIVE
    state.phase_deadline = datetime.now(UTC) + timedelta(
        seconds=duration + get_interstitial_hold(GamePhase.ACTIVE, RoundType.BRAIN_TEST)
    )
    return state


def transition_to_brain_test_results(state: TellGameState, duration: int) -> TellGameState:
    return _transition_to_phase(state, GamePhase.RESULTS, duration, RoundType.BRAIN_TEST)


def transition_to_matchup(state: TellGameState, duration: int) -> TellGameState:
    return _transition_to_phase(state, GamePhase.ACTIVE, duration, RoundType.TASK)


def generate_matchup_pairs(
    state: TellGameState,
) -> tuple[list[tuple[str, str]], str | None]:
    """Shuffle players into pairs. Odd count -> one bye player.

    Returns (pairs, bye_player_id).
    """
    ids = [p.id for p in state.players]
    random.shuffle(ids)

    bye_id: str | None = None
    if len(ids) % 2 == 1:
        bye_id = ids.pop()

    pairs: list[tuple[str, str]] = []
    for i in range(0, len(ids), 2):
        pairs.append((ids[i], ids[i + 1]))

    return pairs, bye_id


def transition_to_task_matchup_prompt(
    state: TellGameState, duration: int, reading_duration: int = 0
) -> TellGameState:
    """Start a new Task round with per-pair matchup prompts."""
    from schemas.prompts import select_task_prompt

    state.round_number += 1

    pairs, bye_id = generate_matchup_pairs(state)

    matchups: list[Matchup] = []
    for left_id, right_id in pairs:
        idx, prompt = select_task_prompt(
            state.used_task_prompt_indices,
            state.last_task_prompt_category,
        )
        state.used_task_prompt_indices.append(idx)
        state.last_task_prompt_category = prompt.category.value
        matchups.append(
            Matchup(
                pair=[left_id, right_id],
                prompt_text=prompt.text,
                prompt_category=prompt.category.value,
            )
        )

    # Use the first pair's prompt as the round-level prompt_text (for narrator context)
    first_prompt = matchups[0].prompt_text if matchups else "matchup"
    first_category = matchups[0].prompt_category if matchups else "task"

    now = datetime.now(UTC)
    state.current_round = RoundState(
        round_number=state.round_number,
        prompt_text=first_prompt,
        prompt_category=first_category,
        round_type=RoundType.TASK,
        matchups=matchups,
        bye_player_id=bye_id,
        writing_begins_at=(
            now + timedelta(seconds=reading_duration) if reading_duration > 0 else None
        ),
    )
    state.phase = GamePhase.PROMPT
    hold = get_interstitial_hold(GamePhase.PROMPT)
    state.phase_deadline = now + timedelta(seconds=duration + hold)
    return state


def build_matchup_round_payload(matchups: list[Matchup], players: list[Player]) -> dict:
    """Build the round_payload dict for matchup data (used in events + reconnection)."""
    player_map = {p.id: p for p in players}
    return {
        "matchups": [
            {
                "pair": m.pair,
                "prompt_text": m.prompt_text,
                "prompt_category": m.prompt_category,
                "left_alias": player_map[m.pair[0]].alias if m.pair[0] in player_map else "",
                "right_alias": player_map[m.pair[1]].alias if m.pair[1] in player_map else "",
            }
            for m in matchups
        ],
    }


def build_matchup_sub_round_payload(
    matchup: Matchup, index: int, answers: dict[str, str], players: list[Player]
) -> dict:
    """Build the sub-round payload dict for a single matchup challenge."""
    player_map = {p.id: p for p in players}
    left_id, right_id = matchup.pair[0], matchup.pair[1]
    return {
        "matchup_index": index,
        "left_player_id": left_id,
        "left_alias": player_map[left_id].alias if left_id in player_map else left_id,
        "left_answer": answers.get(left_id, "[no response]"),
        "right_player_id": right_id,
        "right_alias": player_map[right_id].alias if right_id in player_map else right_id,
        "right_answer": answers.get(right_id, "[no response]"),
        "prompt_text": matchup.prompt_text,
    }


def resolve_matchup_votes(
    state: TellGameState,
) -> tuple[TellGameState, list[dict], dict[str, int]]:
    """Tally per-matchup LEFT/RIGHT votes. Award 1 point to the winner of each matchup.

    Returns (state, matchup_results_list, scores_dict). Caller wraps in RoundResultsEvent.
    """
    rs = state.current_round
    matchups = rs.matchups if rs else []

    player_map = {p.id: p for p in state.players}
    matchup_results_list: list[dict] = []

    for i, m in enumerate(matchups):
        left_id, right_id = m.pair[0], m.pair[1]
        left_votes = 0
        right_votes = 0

        for _voter_id, choice in m.votes.items():
            if choice == 0:
                left_votes += 1
            else:
                right_votes += 1

        left_player = player_map.get(left_id)
        right_player = player_map.get(right_id)

        # Award point to winner (no point on tie)
        if left_votes > right_votes and left_player:
            left_player.score += 1
        elif right_votes > left_votes and right_player:
            right_player.score += 1

        matchup_results_list.append(
            {
                "matchup_index": i,
                "left_player_id": left_id,
                "left_alias": left_player.alias if left_player else left_id,
                "left_votes": left_votes,
                "right_player_id": right_id,
                "right_alias": right_player.alias if right_player else right_id,
                "right_votes": right_votes,
                "prompt_text": m.prompt_text,
            }
        )

    # Build scores dict: all players' current total scores
    scores = {p.id: p.score for p in state.players}

    return state, matchup_results_list, scores


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

    if round_state:
        prompt_text = round_state.prompt_text
        prompt_category = round_state.prompt_category
        round_type = round_state.round_type

        # For matchup Task rounds, show the player's specific prompt during PROMPT
        if round_state.matchups and state.phase == GamePhase.PROMPT:
            for m in round_state.matchups:
                if player_id in m.pair:
                    prompt_text = m.prompt_text
                    prompt_category = m.prompt_category
                    break
            else:
                # Bye player
                prompt_text = None
                prompt_category = None

        # Answers visible during game_over, active (matchup)
        if state.phase in (GamePhase.GAME_OVER, GamePhase.ACTIVE):
            answers = round_state.answers

        if state.phase == GamePhase.PROMPT and player_id in round_state.answers:
            my_answer = round_state.answers[player_id]

    player_obj = get_player_by_id(state, player_id)
    is_host = player_obj.is_host if player_obj else False

    scores = {p.id: p.score for p in state.players}

    # Build generic round data for reconnection
    round_payload: dict | None = None
    sub_round_index: int = 0
    sub_round_payload: dict | None = None

    if round_state and state.phase in (GamePhase.ACTIVE, GamePhase.PROMPT):
        if round_state.round_type == RoundType.TASK and round_state.matchups:
            round_payload = build_matchup_round_payload(round_state.matchups, state.players)
            # Active matchup sub-round data
            if state.phase == GamePhase.ACTIVE:
                sub_round_index = round_state.current_sub_round
                idx = round_state.current_sub_round
                if idx < len(round_state.matchups):
                    sub_round_payload = build_matchup_sub_round_payload(
                        round_state.matchups[idx], idx, round_state.answers, state.players
                    )
        elif round_state.round_type == RoundType.BRAIN_TEST and round_state.brain_challenges:
            sub_round_index = round_state.current_sub_round
            if state.phase == GamePhase.ACTIVE:
                idx = round_state.current_sub_round
                if idx < len(round_state.brain_challenges):
                    ch = round_state.brain_challenges[idx]
                    sub_round_payload = {
                        "challenge_type": ch.challenge_type,
                        "question": ch.question,
                        "options": ch.options,
                    }

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
        "writing_begins_at": (
            round_state.writing_begins_at.isoformat()
            if round_state and round_state.writing_begins_at
            else None
        ),
        "action_starts_at": (
            (state.phase_deadline - timedelta(seconds=phase_duration)).isoformat()
            if state.phase_deadline and phase_duration
            else None
        ),
        "round_payload": round_payload,
        "sub_round_index": sub_round_index,
        "sub_round_payload": sub_round_payload,
    }
