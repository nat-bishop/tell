"""Pure game logic — state transitions, vote resolution, validation."""

from __future__ import annotations

import random
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schemas.prompts import BrainTestChallengeSpec

from schemas.api_models import (
    EliminationEvent,
    GameOverEvent,
    PhaseChangedEvent,
    VoteResultsEvent,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import (
    BrainTestChallenge,
    ChainRound,
    GamePhase,
    Player,
    PlayerRole,
    RoundState,
    RoundType,
    TellGameState,
)
from schemas.prompts import select_prompt


def get_alive_players(state: TellGameState) -> list[Player]:
    return [p for p in state.players if p.is_alive]


def get_alive_humans(state: TellGameState) -> list[Player]:
    return [p for p in state.players if p.is_alive and p.role == PlayerRole.HUMAN]


def get_alive_ai(state: TellGameState) -> list[Player]:
    return [p for p in state.players if p.is_alive and p.role == PlayerRole.AI]


def get_player_by_id(state: TellGameState, player_id: str) -> Player | None:
    return next((p for p in state.players if p.id == player_id), None)


def fill_missing_answers(state: TellGameState) -> None:
    """Fill NO_RESPONSE for alive players who haven't answered."""
    rs = state.current_round
    if not rs:
        return
    for p in get_alive_players(state):
        if p.id not in rs.answers:
            rs.answers[p.id] = NO_RESPONSE


def fill_missing_responses(state: TellGameState) -> None:
    """Fill NO_RESPONSE for unanswered questions."""
    rs = state.current_round
    if not rs:
        return
    for q in rs.questions:
        if q.response is None:
            q.response = NO_RESPONSE


def select_chain_next_word(responses: dict[str, str]) -> tuple[str, str | None]:
    """Pick the next seed word from chain responses. Prefers unique (single-submitter) words.

    Returns (chosen_word, player_id_who_submitted_it_or_None).
    """
    if not responses:
        return "", None

    # Count occurrences of each word (case-insensitive)
    normalized = {pid: word.strip().lower() for pid, word in responses.items()}
    word_counts = Counter(normalized.values())
    word_to_players: dict[str, list[str]] = {}
    for pid, w in normalized.items():
        word_to_players.setdefault(w, []).append(pid)

    # Prefer unique words (submitted by exactly one player)
    unique_words = [w for w, count in word_counts.items() if count == 1]
    if unique_words:
        chosen = random.choice(unique_words)
    else:
        chosen = random.choice(list(word_counts.keys()))

    player_id = random.choice(word_to_players[chosen])
    return chosen, player_id


def select_round_types(num_rounds: int) -> list[RoundType]:
    """Cycle: Task → Word Chain → Brain Test → Interrogation → ...

    Brain Test is evidence-only (no voting). It appears every 3rd round
    starting from round 3.
    """
    cycle = [
        RoundType.TASK,
        RoundType.WORD_CHAIN,
        RoundType.BRAIN_TEST,
        RoundType.INTERROGATION,
    ]
    return [cycle[i % len(cycle)] for i in range(num_rounds)]


# Interstitial hold times (seconds) added to phase deadlines so
# clients can display a phase-transition overlay without eating action time.
# The frontend derives its dismiss timing from the action_starts_at timestamp.
_INTERSTITIAL_HOLD: dict[GamePhase, int] = {
    GamePhase.PROMPT: 5,  # round start — staggered visual beats
    GamePhase.CHAIN: 5,  # round start
    GamePhase.BRAIN_TEST: 5,  # round start
    GamePhase.BRAIN_TEST_RESULTS: 2,
    GamePhase.NOMINATE: 2,  # mid-round (~1.5s on client, 2s gives buffer)
    GamePhase.QUESTION: 2,
    GamePhase.RESPOND: 2,
    GamePhase.REVIEW: 2,
    GamePhase.ELIMINATION: 2,
}


def get_interstitial_hold(phase: GamePhase) -> int:
    """Extra seconds added to phase deadline for client interstitial overlay."""
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
    if phase == GamePhase.CHAIN:
        return settings.chain_duration
    if phase == GamePhase.BRAIN_TEST:
        return settings.brain_test_duration
    if phase == GamePhase.BRAIN_TEST_RESULTS:
        return settings.brain_test_results_duration
    durations = {
        GamePhase.QUESTION: settings.question_duration,
        GamePhase.RESPOND: settings.respond_duration,
        GamePhase.REVIEW: settings.review_duration,
        GamePhase.NOMINATE: settings.nominate_duration,
        GamePhase.ELIMINATION: settings.elimination_duration,
    }
    return durations.get(phase)


def get_question_target(round_state: RoundState, player_id: str) -> str | None:
    """Get the question target for a player based on round type."""
    if round_state.round_type == RoundType.INTERROGATION:
        return round_state.nominated_id
    return round_state.assignments.get(player_id)


def is_question_eligible(round_state: RoundState, player_id: str) -> bool:
    """Check if a player can submit a question this round."""
    if round_state.round_type == RoundType.INTERROGATION:
        return player_id != round_state.nominated_id
    return True


def count_expected_questions(state: TellGameState) -> int:
    """How many questions are expected this round."""
    alive = get_alive_players(state)
    round_state = state.current_round
    if round_state and round_state.round_type == RoundType.INTERROGATION:
        return len([p for p in alive if p.id != round_state.nominated_id])
    return len(alive)


def is_response_eligible(round_state: RoundState, player_id: str) -> bool:
    """Check if a player can respond this round."""
    if round_state.round_type == RoundType.INTERROGATION:
        return player_id == round_state.nominated_id
    return True


def count_responses(round_state: RoundState) -> tuple[int, int]:
    """Return (responded_count, expected_count) for the current round."""
    if round_state.round_type == RoundType.INTERROGATION:
        has_response = any(
            q.target_id == round_state.nominated_id and q.response is not None
            for q in round_state.questions
        )
        return (1 if has_response else 0, 1)
    targets = {q.target_id for q in round_state.questions}
    responded = sum(1 for q in round_state.questions if q.response is not None)
    return (responded, len(targets))


def assign_question_targets(state: TellGameState) -> dict[str, str]:
    """Round-robin chain: player i questions player (i+1) % len."""
    alive = [p for p in state.players if p.is_alive]
    assignments = {}
    for i, player in enumerate(alive):
        target = alive[(i + 1) % len(alive)]
        assignments[player.id] = target.id
    return assignments


def resolve_nominations(state: TellGameState) -> str:
    """Tally nominations and return the nominated player id. Ties broken randomly."""
    round_state = state.current_round
    nominations = round_state.nominations if round_state else {}

    if not nominations:
        alive = get_alive_players(state)
        return random.choice(alive).id

    tallies = Counter(nominations.values())
    max_count = max(tallies.values())
    top = [pid for pid, count in tallies.items() if count == max_count]
    return random.choice(top) if len(top) > 1 else top[0]


def max_votes_for_player(alive_count: int) -> int:
    """Max votes a player can cast: min(3, alive_count - 1)."""
    return min(3, max(1, alive_count - 1))


def get_next_round_type(state: TellGameState) -> RoundType:
    """Get the round type for the next round."""
    next_round = state.round_number + 1
    if state.round_types and next_round <= len(state.round_types):
        return state.round_types[next_round - 1]
    return RoundType.TASK


def transition_to_prompt(
    state: TellGameState, duration: int, reading_duration: int = 0
) -> TellGameState:
    """Start a new round with a new prompt (Interrogation)."""
    state.round_number += 1
    idx, prompt = select_prompt(
        state.used_prompt_indices,
        state.last_prompt_category,
        state.round_number,
    )
    state.used_prompt_indices.append(idx)
    state.last_prompt_category = prompt.category.value

    round_type = RoundType.INTERROGATION
    if state.round_types and state.round_number <= len(state.round_types):
        round_type = state.round_types[state.round_number - 1]

    now = datetime.now(UTC)
    state.current_round = RoundState(
        round_number=state.round_number,
        prompt_text=prompt.text,
        prompt_category=prompt.category.value,
        round_type=round_type,
        writing_begins_at=(
            now + timedelta(seconds=reading_duration) if reading_duration > 0 else None
        ),
    )
    state.phase = GamePhase.PROMPT
    hold = get_interstitial_hold(GamePhase.PROMPT)
    state.phase_deadline = now + timedelta(seconds=duration + hold)
    return state


def transition_to_task_prompt(
    state: TellGameState, duration: int, reading_duration: int = 0
) -> TellGameState:
    """Start a new Task round with a constrained prompt."""
    from schemas.prompts import select_task_prompt

    state.round_number += 1
    idx, prompt = select_task_prompt(
        state.used_task_prompt_indices,
        state.last_task_prompt_category,
    )
    state.used_task_prompt_indices.append(idx)
    state.last_task_prompt_category = prompt.category.value

    now = datetime.now(UTC)
    state.current_round = RoundState(
        round_number=state.round_number,
        prompt_text=prompt.text,
        prompt_category=prompt.category.value,
        round_type=RoundType.TASK,
        writing_begins_at=(
            now + timedelta(seconds=reading_duration) if reading_duration > 0 else None
        ),
    )
    state.phase = GamePhase.PROMPT
    hold = get_interstitial_hold(GamePhase.PROMPT)
    state.phase_deadline = now + timedelta(seconds=duration + hold)
    return state


def transition_to_word_chain(state: TellGameState, seed_word: str, duration: int) -> TellGameState:
    """Start a new Word Chain round."""

    state.round_number += 1

    state.current_round = RoundState(
        round_number=state.round_number,
        prompt_text="word chain",
        prompt_category="word_chain",
        round_type=RoundType.WORD_CHAIN,
        current_sub_round=0,
        chain_rounds=[ChainRound(seed=seed_word)],
    )
    state.phase = GamePhase.CHAIN
    state.phase_deadline = datetime.now(UTC) + timedelta(
        seconds=duration + get_interstitial_hold(GamePhase.CHAIN)
    )
    return state


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
        prompt_text="brain test",
        prompt_category="brain_test",
        round_type=RoundType.BRAIN_TEST,
        current_sub_round=0,
        brain_challenges=[
            BrainTestChallenge(
                challenge_type=c.challenge_type,
                question=c.question,
                correct_answer=c.correct_answer,
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


def transition_to_question(state: TellGameState, duration: int) -> TellGameState:
    return _transition_to_phase(state, GamePhase.QUESTION, duration)


def transition_to_respond(state: TellGameState, duration: int) -> TellGameState:
    return _transition_to_phase(state, GamePhase.RESPOND, duration)


def transition_to_review(state: TellGameState, duration: int) -> TellGameState:
    return _transition_to_phase(state, GamePhase.REVIEW, duration)


def transition_to_nominate(state: TellGameState, duration: int) -> TellGameState:
    return _transition_to_phase(state, GamePhase.NOMINATE, duration)


def transition_to_elimination(state: TellGameState, duration: int) -> TellGameState:
    return _transition_to_phase(state, GamePhase.ELIMINATION, duration)


def resolve_votes(
    state: TellGameState,
    seq_fn,
) -> tuple[TellGameState, VoteResultsEvent, EliminationEvent]:
    """Tally votes (multi-vote) and eliminate the most-voted player.

    If active_ability is double_vote, the holder's votes count 2x.
    """
    round_state = state.current_round
    votes = round_state.votes if round_state else {}

    # Check for double vote ability
    double_vote_holder = None
    if state.active_ability and state.active_ability.ability_type == "double_vote":
        double_vote_holder = state.active_ability.holder_id

    # Flatten all vote lists into a single counter (double-count for ability holder)
    all_targets: list[str] = []
    for voter_id, target_list in votes.items():
        repeat = 2 if voter_id == double_vote_holder else 1
        for _ in range(repeat):
            all_targets.extend(target_list)

    tallies: dict[str, int] = dict(Counter(all_targets))

    eliminated_id = None
    eliminated_alias = None
    was_human = None
    tie = False
    tie_message = None
    no_votes = len(all_targets) == 0
    vote_count = 0

    if tallies:
        max_count = max(tallies.values())
        top_players = [pid for pid, count in tallies.items() if count == max_count]
        vote_count = max_count

        if len(top_players) == 1:
            eliminated_id = top_players[0]
        else:
            tie = True
            eliminated_id = random.choice(top_players)
            tied_aliases = []
            for pid in top_players:
                p = get_player_by_id(state, pid)
                if p:
                    tied_aliases.append(p.alias)
            tie_message = f"{' and '.join(tied_aliases)} tied with {max_count} votes each. "

        for p in state.players:
            if p.id == eliminated_id:
                p.is_alive = False
                p.eliminated_round = state.round_number
                eliminated_alias = p.alias
                was_human = p.role == PlayerRole.HUMAN
                if tie_message:
                    tie_message += f"{p.alias} was randomly eliminated."
                break

    vote_results = VoteResultsEvent(
        seq=seq_fn(),
        votes=votes,
        vote_tallies=tallies,
        eliminated_id=eliminated_id,
        eliminated_alias=eliminated_alias,
        was_human=was_human,
        tie=tie,
        tie_message=tie_message,
    )

    elimination = EliminationEvent(
        seq=seq_fn(),
        eliminated_id=eliminated_id,
        eliminated_alias=eliminated_alias,
        was_human=was_human,
        vote_count=vote_count,
        tie=tie,
        tie_message=tie_message,
        no_votes=no_votes,
    )

    return state, vote_results, elimination


def resolve_comedy_votes(
    state: TellGameState,
) -> tuple[str | None, str | None, int]:
    """Tally comedy votes. Returns (winner_id, winner_alias, vote_count)."""
    round_state = state.current_round
    if not round_state or not round_state.comedy_votes:
        return None, None, 0

    tallies: dict[str, int] = dict(Counter(round_state.comedy_votes.values()))
    if not tallies:
        return None, None, 0

    max_count = max(tallies.values())
    top = [pid for pid, c in tallies.items() if c == max_count]
    winner_id = top[0] if len(top) == 1 else random.choice(top)

    player = get_player_by_id(state, winner_id)
    winner_alias = player.alias if player else None
    return winner_id, winner_alias, max_count


# ---------------------------------------------------------------------------
# Brain Test scoring
# ---------------------------------------------------------------------------

_WORD_TO_NUM: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _normalize_answer(answer: str) -> str:
    """Normalize an answer for fuzzy matching: lowercase, strip whitespace/articles/currency."""
    s = answer.strip().lower()
    # Strip leading articles
    s = re.sub(r"^(the|a|an)\s+", "", s)
    # Strip currency symbols
    s = re.sub(r"^[$€£¥]", "", s)
    return s.strip()


def _parse_numeric(s: str) -> float | None:
    """Try to parse a string as a number."""
    s = re.sub(r"[,$€£¥%]", "", s.strip())
    # Handle "X cents" patterns
    m = re.match(r"^(\d+(?:\.\d+)?)\s*cents?$", s, re.IGNORECASE)
    if m:
        return float(m.group(1)) / 100
    try:
        return float(s)
    except ValueError:
        return None


def _fuzzy_match(response: str, correct: str) -> bool:
    """Check if a response matches the correct answer (fuzzy)."""
    norm_r = _normalize_answer(response)
    norm_c = _normalize_answer(correct)
    if norm_r == norm_c:
        return True
    # Numeric comparison
    num_r = _parse_numeric(response)
    num_c = _parse_numeric(correct)
    if num_r is not None and num_c is not None:
        return abs(num_r - num_c) < 0.001
    # Handle "five cents" -> 0.05 style
    words = norm_r.split()
    if len(words) >= 1 and words[0] in _WORD_TO_NUM:
        val = _WORD_TO_NUM[words[0]]
        if len(words) >= 2 and "cent" in words[1]:
            val = val / 100
        if num_c is not None and abs(val - num_c) < 0.001:
            return True
    return False


def _score_with_answer(challenge: BrainTestChallenge) -> dict[str, int]:
    """1 point for matching correct_answer (fuzzy)."""
    scores: dict[str, int] = {}
    if not challenge.correct_answer:
        return scores
    for pid, response in challenge.responses.items():
        scores[pid] = 1 if _fuzzy_match(response, challenge.correct_answer) else 0
    return scores


def _score_by_uniqueness(challenge: BrainTestChallenge) -> dict[str, int]:
    """1 point if your answer is unique among all responses."""
    scores: dict[str, int] = {}
    if not challenge.responses:
        return scores
    # Count normalized occurrences
    normalized = {pid: _normalize_answer(ans) for pid, ans in challenge.responses.items()}
    counts: dict[str, int] = {}
    for norm in normalized.values():
        counts[norm] = counts.get(norm, 0) + 1
    for pid, norm in normalized.items():
        scores[pid] = 1 if counts[norm] == 1 else 0
    return scores


def score_brain_test(challenges: list[BrainTestChallenge]) -> dict[str, int]:
    """Score all challenges. Returns player_id -> total points."""
    totals: dict[str, int] = {}
    for ch in challenges:
        ch_scores = _score_with_answer(ch) if ch.correct_answer else _score_by_uniqueness(ch)
        for pid, pts in ch_scores.items():
            totals[pid] = totals.get(pid, 0) + pts
    return totals


def determine_challenge_winner(
    scores: dict[str, int],
) -> tuple[str, str] | None:
    """Highest score wins. Random tiebreak. Returns (player_id, alias_placeholder) or None.

    Note: caller must resolve alias from the game state.
    """
    if not scores:
        return None
    max_score = max(scores.values())
    if max_score == 0:
        return None
    top = [pid for pid, s in scores.items() if s == max_score]
    winner = random.choice(top) if len(top) > 1 else top[0]
    return winner, ""  # alias resolved by caller


def check_game_over(state: TellGameState) -> str | None:
    """Check if the game should end. Returns 'humans', 'ai', or None."""
    alive_humans = get_alive_humans(state)
    alive_ai = get_alive_ai(state)
    alive = get_alive_players(state)

    if not alive_humans:
        return "ai"
    if not alive_ai:
        return "humans"
    if len(alive) <= 2:
        if alive_humans:
            return "humans"
        return "ai"
    if state.round_number >= state.max_rounds:
        return "humans"
    return None


def make_game_over_event(state: TellGameState, winner: str, seq_fn) -> GameOverEvent:
    players_revealed = []
    for p in state.players:
        players_revealed.append(
            {
                "id": p.id,
                "alias": p.alias,
                "role": p.role.value,
                "is_alive": p.is_alive,
                "eliminated_round": p.eliminated_round,
            }
        )
    return GameOverEvent(
        seq=seq_fn(),
        winner=winner,
        players=players_revealed,
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


def validate_player_alive(state: TellGameState, player_id: str) -> Player | str:
    player = get_player_by_id(state, player_id)
    if not player:
        return "Player not found"
    if not player.is_alive:
        return "Player has been eliminated"
    return player


def sanitize_players_for_client(state: TellGameState) -> list[dict]:
    result = []
    for p in state.players:
        d = {
            "id": p.id,
            "alias": p.alias,
            "is_alive": p.is_alive,
            "is_connected": p.is_connected,
            "is_host": p.is_host,
            "eliminated_round": p.eliminated_round,
        }
        if not p.is_alive:
            d["role"] = p.role.value
        result.append(d)
    return result


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
    questions: list[dict] = []
    assignments: dict[str, str] = {}
    nominated_id: str | None = None
    nominations: dict[str, str] = {}
    synthesis: str | None = None
    verdict: str | None = None
    chain_rounds: list[dict] = []
    current_sub_round: int = 0

    if round_state:
        prompt_text = round_state.prompt_text
        prompt_category = round_state.prompt_category
        round_type = round_state.round_type

        # Answers visible during question, respond, review, elimination, game_over
        visible_phases = (
            GamePhase.QUESTION,
            GamePhase.RESPOND,
            GamePhase.REVIEW,
            GamePhase.ELIMINATION,
            GamePhase.GAME_OVER,
            GamePhase.NOMINATE,
        )
        if state.phase in visible_phases:
            answers = round_state.answers

        if state.phase == GamePhase.PROMPT and player_id in round_state.answers:
            my_answer = round_state.answers[player_id]

        assignments = round_state.assignments
        nominated_id = round_state.nominated_id
        nominations = round_state.nominations
        synthesis = round_state.synthesis
        verdict = round_state.verdict

        for q in round_state.questions:
            qd: dict = {
                "questioner_id": q.questioner_id,
                "target_id": q.target_id,
                "target_alias": q.target_alias,
                "question": q.question,
                "response": q.response,
            }
            questions.append(qd)

        # Word Chain state
        if round_state.chain_rounds:
            chain_rounds = [cr.model_dump() for cr in round_state.chain_rounds]
            current_sub_round = round_state.current_sub_round

    player_obj = get_player_by_id(state, player_id)
    is_host = player_obj.is_host if player_obj else False

    return {
        "event_type": "state_sync",
        "seq": seq,
        "game_id": state.game_id,
        "phase": state.phase.value,
        "players": sanitize_players_for_client(state),
        "round_number": state.round_number,
        "prompt_text": prompt_text,
        "prompt_category": prompt_category,
        "round_type": round_type,
        "answers": answers,
        "questions": questions,
        "assignments": assignments,
        "nominated_id": nominated_id,
        "nominations": nominations,
        "synthesis": synthesis,
        "verdict": verdict,
        "my_votes": (
            round_state.votes.get(player_id, [])
            if round_state and state.phase == GamePhase.REVIEW
            else []
        ),
        "phase_deadline": state.phase_deadline.isoformat() if state.phase_deadline else None,
        "phase_duration": phase_duration,
        "winner": state.winner,
        "is_host": is_host,
        "my_answer": my_answer,
        "writing_begins_at": (
            round_state.writing_begins_at.isoformat()
            if round_state and round_state.writing_begins_at
            else None
        ),
        "chain_rounds": chain_rounds,
        "current_sub_round": current_sub_round,
        "action_starts_at": (
            (state.phase_deadline - timedelta(seconds=phase_duration)).isoformat()
            if state.phase_deadline and phase_duration
            else None
        ),
    }
