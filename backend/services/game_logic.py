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
from schemas.game_state import (
    ChatMessage,
    GamePhase,
    Player,
    PlayerRole,
    RoundState,
    TellGameState,
)
from schemas.prompts import select_prompt


def get_alive_players(state: TellGameState) -> list[Player]:
    return [p for p in state.players if p.is_alive]


def get_alive_humans(state: TellGameState) -> list[Player]:
    return [p for p in state.players if p.is_alive and p.role == PlayerRole.HUMAN]


def get_alive_ai(state: TellGameState) -> list[Player]:
    return [p for p in state.players if p.is_alive and p.role == PlayerRole.AI]


def transition_to_prompt(state: TellGameState, duration: int) -> TellGameState:
    """Start a new round with a new prompt."""
    state.round_number += 1
    idx, prompt = select_prompt(
        state.used_prompt_indices,
        state.last_prompt_category,
        state.round_number,
    )
    state.used_prompt_indices.append(idx)
    state.last_prompt_category = prompt.category.value
    state.current_round = RoundState(
        round_number=state.round_number,
        prompt_text=prompt.text,
        prompt_category=prompt.category.value,
    )
    state.phase = GamePhase.PROMPT
    state.phase_deadline = datetime.now(UTC) + timedelta(seconds=duration)
    return state


def transition_to_chat(state: TellGameState, duration: int) -> TellGameState:
    """Move to chat phase — answers become visible."""
    state.phase = GamePhase.CHAT
    state.phase_deadline = datetime.now(UTC) + timedelta(seconds=duration)
    return state


def transition_to_vote(state: TellGameState, duration: int) -> TellGameState:
    """Move to vote phase."""
    state.phase = GamePhase.VOTE
    state.phase_deadline = datetime.now(UTC) + timedelta(seconds=duration)
    return state


def transition_to_elimination(state: TellGameState, duration: int) -> TellGameState:
    """Move to elimination reveal phase."""
    state.phase = GamePhase.ELIMINATION
    state.phase_deadline = datetime.now(UTC) + timedelta(seconds=duration)
    return state


def resolve_votes(state: TellGameState, seq_fn) -> tuple[TellGameState, VoteResultsEvent, EliminationEvent]:
    """Tally votes and eliminate the most-voted player. Returns updated state and events."""
    round_state = state.current_round
    votes = round_state.votes if round_state else {}

    # Tally
    tallies: dict[str, int] = Counter(votes.values())

    eliminated_id = None
    eliminated_alias = None
    was_human = None
    tie = False
    tie_message = None
    no_votes = len(votes) == 0
    vote_count = 0

    if tallies:
        max_count = max(tallies.values())
        top_players = [pid for pid, count in tallies.items() if count == max_count]
        vote_count = max_count

        if len(top_players) == 1:
            eliminated_id = top_players[0]
        else:
            # Tie — random elimination among tied
            tie = True
            eliminated_id = random.choice(top_players)
            tied_aliases = []
            for pid in top_players:
                p = next((p for p in state.players if p.id == pid), None)
                if p:
                    tied_aliases.append(p.alias)
            tie_message = f"{' and '.join(tied_aliases)} tied with {max_count} votes each. "

        # Find and eliminate the player
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
        vote_tallies=dict(tallies),
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

    # All humans eliminated — AI wins
    if not alive_humans:
        return "ai"

    # All AI eliminated — humans win
    if not alive_ai:
        return "humans"

    # Only 2 players left — game over
    if len(alive) <= 2:
        if alive_humans:
            return "humans"
        return "ai"

    # Max rounds reached — humans survive
    if state.round_number >= state.max_rounds:
        return "humans"

    return None


def make_game_over_event(state: TellGameState, winner: str, seq_fn) -> GameOverEvent:
    """Create GameOverEvent with all player identities revealed."""
    players_revealed = []
    for p in state.players:
        players_revealed.append({
            "id": p.id,
            "alias": p.alias,
            "role": p.role.value,
            "is_alive": p.is_alive,
            "eliminated_round": p.eliminated_round,
        })
    return GameOverEvent(
        seq=seq_fn(),
        winner=winner,
        players=players_revealed,
    )


def validate_player_alive(state: TellGameState, player_id: str) -> Player | str:
    """Returns the Player if alive, or an error message string."""
    player = next((p for p in state.players if p.id == player_id), None)
    if not player:
        return "Player not found"
    if not player.is_alive:
        return "Player has been eliminated"
    return player


def sanitize_players_for_client(state: TellGameState) -> list[dict]:
    """Return player list without revealing roles of alive players."""
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
        # Only reveal role of eliminated players
        if not p.is_alive:
            d["role"] = p.role.value
        result.append(d)
    return result


def build_state_sync(state: TellGameState, player_id: str, seq: int) -> dict:
    """Build a StateSyncEvent payload for a specific player."""
    round_state = state.current_round
    answers: dict[str, str] = {}
    messages: list[dict] = []
    my_answer: str | None = None
    prompt_text: str | None = None
    prompt_category: str | None = None

    if round_state:
        prompt_text = round_state.prompt_text
        prompt_category = round_state.prompt_category

        # Answers visible during chat, vote, elimination, game_over
        if state.phase in (GamePhase.CHAT, GamePhase.VOTE, GamePhase.ELIMINATION, GamePhase.GAME_OVER):
            answers = round_state.answers

        # Player's own answer always visible to them during prompt phase
        if state.phase == GamePhase.PROMPT and player_id in round_state.answers:
            my_answer = round_state.answers[player_id]

        messages = [m.model_dump(mode="json") for m in round_state.messages]

    is_host = any(p.id == player_id and p.is_host for p in state.players)

    return {
        "event_type": "state_sync",
        "seq": seq,
        "game_id": state.game_id,
        "phase": state.phase.value,
        "players": sanitize_players_for_client(state),
        "round_number": state.round_number,
        "prompt_text": prompt_text,
        "prompt_category": prompt_category,
        "answers": answers,
        "messages": messages,
        "votes": {},  # votes are hidden until results
        "phase_deadline": state.phase_deadline.isoformat() if state.phase_deadline else None,
        "winner": state.winner,
        "is_host": is_host,
        "my_answer": my_answer,
    }
