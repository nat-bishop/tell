"""Pure game logic — state transitions, vote resolution, validation."""

from __future__ import annotations

import random
from collections import Counter
from datetime import UTC, datetime, timedelta

from schemas.api_models import (
    EliminationEvent,
    GameOverEvent,
    PhaseChangedEvent,
    VoteResultsEvent,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import (
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
    """Cycle: Task → Interrogation → Word Chain → Task → ..."""
    cycle = [RoundType.TASK, RoundType.INTERROGATION, RoundType.WORD_CHAIN]
    return [cycle[i % len(cycle)] for i in range(num_rounds)]


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
    state.phase_deadline = now + timedelta(seconds=duration)
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
    state.phase_deadline = now + timedelta(seconds=duration)
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
    state.phase_deadline = datetime.now(UTC) + timedelta(seconds=duration)
    return state


def _transition_to_phase(state: TellGameState, phase: GamePhase, duration: int) -> TellGameState:
    """Move to a phase with a deadline."""
    state.phase = phase
    state.phase_deadline = datetime.now(UTC) + timedelta(seconds=duration)
    return state


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
    """Tally votes (multi-vote) and eliminate the most-voted player."""
    round_state = state.current_round
    votes = round_state.votes if round_state else {}

    # Flatten all vote lists into a single counter
    all_targets: list[str] = []
    for target_list in votes.values():
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


def make_phase_changed_event(state: TellGameState, seq: int, **extra) -> PhaseChangedEvent:
    return PhaseChangedEvent(
        seq=seq,
        phase=state.phase.value,
        round_number=state.round_number,
        phase_deadline=state.phase_deadline.isoformat() if state.phase_deadline else None,
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
    }
