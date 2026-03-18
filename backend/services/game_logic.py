"""Pure game logic — state transitions, vote resolution, validation."""

from __future__ import annotations

import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schemas.prompts import BrainTestChallengeSpec

from schemas.api_models import (
    EliminationEvent,
    GameOverEvent,
    MatchupResultsEvent,
    PhaseChangedEvent,
    VoteResultsEvent,
)
from schemas.constants import NO_RESPONSE
from schemas.game_state import (
    BrainTestChallenge,
    GamePhase,
    Matchup,
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
    """Fill NO_RESPONSE for alive players who haven't answered.

    For matchup Task rounds, only paired players need answers (bye player excluded).
    """
    rs = state.current_round
    if not rs:
        return
    for p in get_alive_players(state):
        if p.id == rs.bye_player_id:
            continue
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


class MinigameMeta:
    """Metadata for a round type, used by round selection."""

    __slots__ = ("has_elimination", "min_players")

    def __init__(self, *, min_players: int, has_elimination: bool) -> None:
        self.min_players = min_players
        self.has_elimination = has_elimination


MINIGAMES: dict[RoundType, MinigameMeta] = {
    RoundType.TASK: MinigameMeta(min_players=3, has_elimination=True),
    RoundType.BRAIN_TEST: MinigameMeta(min_players=2, has_elimination=False),
    RoundType.INTERROGATION: MinigameMeta(min_players=4, has_elimination=True),
}


def select_next_round_type(
    last_round_type: RoundType | None,
    alive_count: int,
) -> RoundType:
    """Pick the next round type dynamically.

    Rules (driven by MINIGAMES registry):
    - Exclude types where alive_count < min_players
    - No repeat of previous round type
    - No consecutive non-eliminating rounds
    - Random from remaining eligible types
    """
    eligible: list[RoundType] = []
    last_meta = MINIGAMES.get(last_round_type) if last_round_type else None

    for rt, meta in MINIGAMES.items():
        if alive_count < meta.min_players:
            continue
        if rt == last_round_type:
            continue
        # Don't allow consecutive non-eliminating rounds
        if last_meta and not last_meta.has_elimination and not meta.has_elimination:
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
    GamePhase.NOMINATE: 2,  # mid-round (~1.5s on client, 2s gives buffer)
    GamePhase.QUESTION: 2,
    GamePhase.RESPOND: 2,
    GamePhase.REVIEW: 2,
    GamePhase.ELIMINATION: 2,
    GamePhase.MATCHUP: 3,
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
    if phase == GamePhase.BRAIN_TEST:
        return settings.brain_test_duration
    if phase == GamePhase.BRAIN_TEST_RESULTS:
        return settings.brain_test_results_duration
    if phase == GamePhase.MATCHUP:
        return settings.matchup_duration
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
    """Get the round type for the next round (dynamic selection)."""
    last = state.round_types[-1] if state.round_types else None
    alive_count = len(get_alive_players(state))
    return select_next_round_type(last, alive_count)


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

    now = datetime.now(UTC)
    state.current_round = RoundState(
        round_number=state.round_number,
        prompt_text=prompt.text,
        prompt_category=prompt.category.value,
        round_type=RoundType.INTERROGATION,
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


def transition_to_matchup(state: TellGameState, duration: int) -> TellGameState:
    return _transition_to_phase(state, GamePhase.MATCHUP, duration)


def generate_matchup_pairs(
    state: TellGameState,
) -> tuple[list[tuple[str, str]], str | None]:
    """Shuffle alive players into pairs. Odd count → one bye player.

    Returns (pairs, bye_player_id).
    """
    alive = [p for p in state.players if p.is_alive]
    ids = [p.id for p in alive]
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
        current_matchup=0,
        bye_player_id=bye_id,
        writing_begins_at=(
            now + timedelta(seconds=reading_duration) if reading_duration > 0 else None
        ),
    )
    state.phase = GamePhase.PROMPT
    hold = get_interstitial_hold(GamePhase.PROMPT)
    state.phase_deadline = now + timedelta(seconds=duration + hold)
    return state


def resolve_matchup_votes(
    state: TellGameState, seq_fn
) -> tuple[
    TellGameState,
    MatchupResultsEvent,
    EliminationEvent,
]:
    """Tally per-matchup LEFT/RIGHT votes, compute margins, eliminate widest-margin loser."""
    rs = state.current_round
    matchups = rs.matchups if rs else []

    # Check for double vote ability
    double_vote_holder = None
    if state.active_ability and state.active_ability.ability_type == "double_vote":
        double_vote_holder = state.active_ability.holder_id

    # Per-matchup results and player margin tracking
    matchup_results_list: list[dict] = []
    # margin = opponent_votes - my_votes (positive means I lost by that many)
    player_margins: dict[str, int] = {}
    player_map = {p.id: p for p in state.players}

    for i, m in enumerate(matchups):
        left_id, right_id = m.pair[0], m.pair[1]
        left_votes = 0
        right_votes = 0

        for voter_id, choice in m.votes.items():
            weight = 2 if voter_id == double_vote_holder else 1
            if choice == 0:
                left_votes += weight
            else:
                right_votes += weight

        left_player = player_map.get(left_id)
        right_player = player_map.get(right_id)

        matchup_results_list.append({
            "matchup_index": i,
            "left_player_id": left_id,
            "left_alias": left_player.alias if left_player else left_id,
            "left_votes": left_votes,
            "right_player_id": right_id,
            "right_alias": right_player.alias if right_player else right_id,
            "right_votes": right_votes,
            "prompt_text": m.prompt_text,
        })

        # Each player is in exactly one matchup
        player_margins[left_id] = right_votes - left_votes
        player_margins[right_id] = left_votes - right_votes

    # Find widest-margin loser (highest positive margin)
    eliminated_id = None
    eliminated_alias = None
    was_human = None
    vote_count = 0

    if player_margins:
        max_margin = max(player_margins.values())
        if max_margin > 0:
            # Only eliminate if someone actually lost
            losers = [pid for pid, m in player_margins.items() if m == max_margin]
            eliminated_id = random.choice(losers) if len(losers) > 1 else losers[0]
        elif max_margin == 0:
            # All ties — random elimination among all paired players
            eliminated_id = random.choice(list(player_margins.keys()))

        if eliminated_id:
            for p in state.players:
                if p.id == eliminated_id:
                    p.is_alive = False
                    p.eliminated_round = state.round_number
                    eliminated_alias = p.alias
                    was_human = p.role == PlayerRole.HUMAN
                    vote_count = player_margins.get(eliminated_id, 0)
                    break

    results_event = MatchupResultsEvent(
        seq=seq_fn(),
        matchup_results=matchup_results_list,
        eliminated_id=eliminated_id,
        eliminated_alias=eliminated_alias,
        was_human=was_human,
        margins=player_margins,
    )

    elimination = EliminationEvent(
        seq=seq_fn(),
        eliminated_id=eliminated_id,
        eliminated_alias=eliminated_alias,
        was_human=was_human,
        vote_count=abs(vote_count),
    )

    return state, results_event, elimination


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
# Brain Test scoring (multiple choice — pure correctness)
# ---------------------------------------------------------------------------


def score_brain_test(challenges: list[BrainTestChallenge]) -> dict[str, int]:
    """Score all challenges. 1 point per correct answer (selected_index == correct_index)."""
    totals: dict[str, int] = {}
    for ch in challenges:
        for pid, selected in ch.responses.items():
            totals[pid] = totals.get(pid, 0) + (1 if selected == ch.correct_index else 0)
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


def check_game_over(state: TellGameState) -> tuple[str, list[str]] | None:
    """Check if the game should end.

    Returns ("ai", []) or ("survivors", [player_ids...]) or None.
    """
    alive_humans = get_alive_humans(state)
    alive_ai = get_alive_ai(state)
    alive = get_alive_players(state)

    if not alive_humans:
        return ("ai", [])
    if not alive_ai:
        return ("survivors", [p.id for p in alive])
    if len(alive) <= 2:
        return ("survivors", [p.id for p in alive])
    if state.round_number >= state.max_rounds:
        # Safety cap — shouldn't normally be reached
        return ("survivors", [p.id for p in alive])
    return None


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
                "is_alive": p.is_alive,
                "eliminated_round": p.eliminated_round,
            }
        )
    return GameOverEvent(
        seq=seq_fn(),
        winner=winner,
        winner_ids=winner_ids,
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

    if round_state:
        prompt_text = round_state.prompt_text
        prompt_category = round_state.prompt_category
        round_type = round_state.round_type

        # For matchup Task rounds, show the player's specific prompt during PROMPT
        if (
            round_state.matchups
            and state.phase == GamePhase.PROMPT
        ):
            for m in round_state.matchups:
                if player_id in m.pair:
                    prompt_text = m.prompt_text
                    prompt_category = m.prompt_category
                    break
            else:
                # Bye player
                prompt_text = None
                prompt_category = None

        # Answers visible during question, respond, review, elimination, game_over, matchup
        visible_phases = (
            GamePhase.QUESTION,
            GamePhase.RESPOND,
            GamePhase.REVIEW,
            GamePhase.ELIMINATION,
            GamePhase.GAME_OVER,
            GamePhase.NOMINATE,
            GamePhase.MATCHUP,
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
    }
