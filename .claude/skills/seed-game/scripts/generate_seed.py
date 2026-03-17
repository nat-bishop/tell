#!/usr/bin/env python
"""Generate valid TellGameState JSON for the debug seed endpoint.

Usage:
    python .claude/skills/seed-game/scripts/generate_seed.py --phase review --round 2
    python .claude/skills/seed-game/scripts/generate_seed.py --phase chain --sub-round 3
    python .claude/skills/seed-game/scripts/generate_seed.py --phase prompt --no-timers --no-ai
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

# Add project root to path so we can import schemas
_project_root = Path(__file__).resolve().parent
while not (_project_root / "schemas").is_dir():
    _project_root = _project_root.parent
    if _project_root == _project_root.parent:
        sys.exit("Error: Cannot find project root (looking for schemas/ directory)")
sys.path.insert(0, str(_project_root))

from schemas.aliases import generate_aliases, generate_game_id, generate_player_id
from schemas.game_state import (
    ChainRound,
    GamePhase,
    Player,
    PlayerRole,
    QuestionEntry,
    RoundState,
    RoundType,
    TellGameState,
)
from schemas.prompts import select_prompt, select_task_prompt
from schemas.word_chain import select_seed_word

# ---------------------------------------------------------------------------
# Round type cycle (inlined from game_logic.py to avoid backend dependencies)
# ---------------------------------------------------------------------------
ROUND_CYCLE = [RoundType.TASK, RoundType.INTERROGATION, RoundType.WORD_CHAIN]


def _select_round_types(num_rounds: int) -> list[RoundType]:
    return [ROUND_CYCLE[i % len(ROUND_CYCLE)] for i in range(num_rounds)]


# ---------------------------------------------------------------------------
# Placeholder content for auto-derived state
# ---------------------------------------------------------------------------
PLACEHOLDER_ANSWERS = [
    "The recursive beauty of a well-crafted algorithm.",
    "Something between nostalgia and static electricity.",
    "I'd say it's like debugging — you never know until you know.",
    "That moment when the compiler finally agrees with you.",
    "A strange warmth, like optimized cache performance.",
    "The hum of processors in a quiet server room.",
    "Like watching a sunset rendered in 4K.",
    "An unexpected segfault in my emotional registers.",
    "Pattern recognition, but for feelings I can't name.",
    "The weight of a decision tree with no leaf nodes.",
]

PLACEHOLDER_QUESTIONS = [
    "Can you elaborate on what you mean by that?",
    "How does that make you feel in this context?",
    "What specifically triggered that response?",
    "Would you say that's a common experience?",
    "How does that relate to the others here?",
    "What would change your mind about that?",
]

PLACEHOLDER_RESPONSES = [
    "I think the question reveals more about the asker.",
    "If I could quantify it, I would, but some things resist measurement.",
    "That's a fair point — let me reconsider my initial answer.",
    "My processing suggests multiple valid interpretations here.",
]

PLACEHOLDER_CHAIN_WORDS = [
    "echo", "spark", "drift", "pulse", "glow", "bloom", "wave",
    "frost", "ember", "tide", "haze", "gleam", "shade", "vapor",
    "mist", "flare", "dust", "core", "root", "veil",
]

# ---------------------------------------------------------------------------
# Valid phases per round type
# ---------------------------------------------------------------------------
VALID_PHASES: dict[RoundType, set[GamePhase]] = {
    RoundType.TASK: {
        GamePhase.PROMPT, GamePhase.REVIEW, GamePhase.ELIMINATION,
    },
    RoundType.INTERROGATION: {
        GamePhase.PROMPT, GamePhase.NOMINATE, GamePhase.QUESTION,
        GamePhase.RESPOND, GamePhase.REVIEW, GamePhase.ELIMINATION,
    },
    RoundType.WORD_CHAIN: {
        GamePhase.CHAIN, GamePhase.REVIEW, GamePhase.ELIMINATION,
    },
}

# Phase ordering for "how far through the round are we"
PHASE_ORDER = {
    GamePhase.PROMPT: 0,
    GamePhase.NOMINATE: 1,
    GamePhase.QUESTION: 2,
    GamePhase.RESPOND: 3,
    GamePhase.CHAIN: 0,  # chain is the first phase in word_chain rounds
    GamePhase.REVIEW: 4,
    GamePhase.ELIMINATION: 5,
}


# ---------------------------------------------------------------------------
# Player generation
# ---------------------------------------------------------------------------
def _make_players(
    num_humans: int,
    num_ai: int,
    num_eliminated: int,
) -> list[Player]:
    total = num_humans + num_ai
    aliases = generate_aliases(total)
    players: list[Player] = []

    for i in range(num_humans):
        players.append(Player(
            id=generate_player_id(),
            alias=aliases[i],
            role=PlayerRole.HUMAN,
            is_host=(i == 0),
        ))

    for i in range(num_ai):
        pid = f"ai-{generate_player_id()[:8]}"
        players.append(Player(
            id=pid,
            alias=aliases[num_humans + i],
            role=PlayerRole.AI,
        ))

    # Eliminate players — pick from the end of the list, spread across rounds
    if num_eliminated > 0:
        eliminable = list(range(len(players)))
        random.shuffle(eliminable)
        for elim_idx in range(min(num_eliminated, len(eliminable))):
            p = players[eliminable[elim_idx]]
            p.is_alive = False
            p.eliminated_round = elim_idx + 1

    return players


# ---------------------------------------------------------------------------
# Auto-derive round state for a given phase
# ---------------------------------------------------------------------------
def _derive_round_state(
    phase: GamePhase,
    round_number: int,
    round_type: RoundType,
    alive_players: list[Player],
    used_prompt_indices: list[int],
    last_prompt_category: str | None,
    used_task_prompt_indices: list[int],
    last_task_prompt_category: str | None,
    sub_round: int,
) -> tuple[RoundState, list[int], str | None, list[int], str | None]:
    """Build a RoundState with auto-derived data for the target phase.

    Returns (round_state, used_prompt_indices, last_prompt_cat,
             used_task_prompt_indices, last_task_prompt_cat).
    """
    alive_ids = [p.id for p in alive_players]

    # --- Select prompt ---
    if round_type == RoundType.TASK:
        idx, prompt = select_task_prompt(used_task_prompt_indices, last_task_prompt_category)
        prompt_text = prompt.text
        prompt_category = prompt.category.value
        used_task_prompt_indices = [*used_task_prompt_indices, idx]
        last_task_prompt_category = prompt_category
    elif round_type == RoundType.WORD_CHAIN:
        prompt_text = "word chain"
        prompt_category = "word_chain"
    else:  # INTERROGATION (or legacy PROBE)
        idx, prompt = select_prompt(used_prompt_indices, last_prompt_category, round_number)
        prompt_text = prompt.text
        prompt_category = prompt.category.value
        used_prompt_indices = [*used_prompt_indices, idx]
        last_prompt_category = prompt_category

    # --- Build base round state ---
    rs = RoundState(
        round_number=round_number,
        prompt_text=prompt_text,
        prompt_category=prompt_category,
        round_type=round_type,
    )

    # --- Fill data based on how far through the round we are ---

    # TASK: prompt → review → elimination
    if round_type == RoundType.TASK:
        if PHASE_ORDER.get(phase, 0) >= PHASE_ORDER[GamePhase.REVIEW]:
            # Answers filled
            rs.answers = {pid: random.choice(PLACEHOLDER_ANSWERS) for pid in alive_ids}
        if phase == GamePhase.ELIMINATION:
            rs.votes = _make_votes(alive_players)

    # INTERROGATION: prompt → nominate → question → respond → review → elimination
    elif round_type == RoundType.INTERROGATION:
        nominated = random.choice(alive_players)

        if PHASE_ORDER.get(phase, 0) >= PHASE_ORDER[GamePhase.NOMINATE]:
            rs.answers = {pid: random.choice(PLACEHOLDER_ANSWERS) for pid in alive_ids}

        if PHASE_ORDER.get(phase, 0) >= PHASE_ORDER[GamePhase.QUESTION]:
            rs.nominated_id = nominated.id
            rs.nominations = {pid: nominated.id for pid in alive_ids if pid != nominated.id}

        if PHASE_ORDER.get(phase, 0) >= PHASE_ORDER[GamePhase.RESPOND]:
            # Questions from everyone except nominee
            rs.questions = [
                QuestionEntry(
                    questioner_id=pid,
                    target_id=nominated.id,
                    target_alias=nominated.alias,
                    question=random.choice(PLACEHOLDER_QUESTIONS),
                    response=(
                        random.choice(PLACEHOLDER_RESPONSES)
                        if PHASE_ORDER.get(phase, 0) >= PHASE_ORDER[GamePhase.REVIEW]
                        else None
                    ),
                    anonymous=False,
                )
                for pid in alive_ids
                if pid != nominated.id
            ]
            rs.synthesis = (
                f"The group questioned {nominated.alias} about their perspective. "
                "Several probing questions explored the depth of their response."
            )

        if PHASE_ORDER.get(phase, 0) >= PHASE_ORDER[GamePhase.REVIEW]:
            rs.verdict = (
                f"{nominated.alias}'s responses suggest careful consideration, "
                "but something feels calculated."
            )

        if phase == GamePhase.ELIMINATION:
            rs.votes = _make_votes(alive_players)

    # WORD_CHAIN: chain → review → elimination
    elif round_type == RoundType.WORD_CHAIN:
        if phase == GamePhase.CHAIN:
            rs.chain_rounds, rs.current_sub_round = _make_chain_rounds(
                alive_ids, sub_round, completed=False,
            )
        elif PHASE_ORDER.get(phase, 0) >= PHASE_ORDER[GamePhase.REVIEW]:
            rs.chain_rounds, rs.current_sub_round = _make_chain_rounds(
                alive_ids, 7, completed=True,
            )
        if phase == GamePhase.ELIMINATION:
            rs.votes = _make_votes(alive_players)

    return (
        rs,
        used_prompt_indices,
        last_prompt_category,
        used_task_prompt_indices,
        last_task_prompt_category,
    )


def _make_votes(alive_players: list[Player]) -> dict[str, list[str]]:
    """Generate plausible votes — each player votes for random targets."""
    alive_ids = [p.id for p in alive_players]
    max_votes = min(3, len(alive_ids) - 1)
    votes: dict[str, list[str]] = {}
    for pid in alive_ids:
        targets = [t for t in alive_ids if t != pid]
        votes[pid] = random.sample(targets, min(max_votes, len(targets)))
    return votes


def _make_chain_rounds(
    alive_ids: list[str],
    target_sub_round: int,
    completed: bool,
) -> tuple[list[ChainRound], int]:
    """Generate chain sub-rounds up to target_sub_round.

    If completed=True, all sub-rounds have responses and chosen words.
    If completed=False, the last sub-round has empty responses (in progress).
    """
    rounds: list[ChainRound] = []
    seed = select_seed_word()
    used_seeds = [seed]

    num_complete = target_sub_round if not completed else target_sub_round + 1

    for i in range(num_complete + (0 if completed else 1)):
        responses: dict[str, str] = {}
        chosen_word: str | None = None
        chosen_player_id: str | None = None

        if i < num_complete or completed:
            # Completed sub-round — all players responded
            words_pool = list(PLACEHOLDER_CHAIN_WORDS)
            random.shuffle(words_pool)
            for j, pid in enumerate(alive_ids):
                responses[pid] = words_pool[j % len(words_pool)]

            # Pick a winner
            chosen_player_id = random.choice(alive_ids)
            chosen_word = responses[chosen_player_id]
        # else: current in-progress sub-round — responses empty

        rounds.append(ChainRound(
            seed=seed,
            responses=responses,
            chosen_word=chosen_word,
            chosen_player_id=chosen_player_id,
        ))

        if chosen_word:
            seed = chosen_word
            used_seeds.append(seed)
        else:
            # Next seed would be chosen from responses; for in-progress, keep current
            pass

    current_sub_round = target_sub_round if not completed else 7
    return rounds, current_sub_round


# ---------------------------------------------------------------------------
# Track prompt usage for prior rounds
# ---------------------------------------------------------------------------
def _track_prior_rounds(
    round_types: list[RoundType],
    target_round: int,
) -> tuple[list[int], str | None, list[int], str | None]:
    """Simulate prompt selection for rounds before the target round."""
    used_prompt_indices: list[int] = []
    last_prompt_category: str | None = None
    used_task_prompt_indices: list[int] = []
    last_task_prompt_category: str | None = None

    for r in range(1, target_round):
        rt = round_types[r - 1]
        if rt == RoundType.TASK:
            idx, prompt = select_task_prompt(used_task_prompt_indices, last_task_prompt_category)
            used_task_prompt_indices.append(idx)
            last_task_prompt_category = prompt.category.value
        elif rt in (RoundType.INTERROGATION, RoundType.PROBE):
            idx, prompt = select_prompt(used_prompt_indices, last_prompt_category, r)
            used_prompt_indices.append(idx)
            last_prompt_category = prompt.category.value
        # WORD_CHAIN: no prompt consumed

    return (
        used_prompt_indices,
        last_prompt_category,
        used_task_prompt_indices,
        last_task_prompt_category,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _validate_args(args: argparse.Namespace) -> None:
    """Validate argument combinations and provide clear error messages."""
    phase = GamePhase(args.phase)
    total = args.humans + args.ai

    if total < 3:
        sys.exit("Error: Need at least 3 players (humans + ai >= 3)")

    if args.eliminated >= total - 1:
        sys.exit(
            f"Error: Cannot eliminate {args.eliminated} of {total} players "
            f"— need at least 2 alive"
        )

    if phase in (GamePhase.LOBBY, GamePhase.GAME_OVER):
        return  # No round-type constraints

    round_types = _select_round_types(max(3, args.humans + 1))
    if args.round < 1 or args.round > len(round_types):
        sys.exit(f"Error: Round must be 1-{len(round_types)}, got {args.round}")

    rt = RoundType(args.round_type) if args.round_type else round_types[args.round - 1]

    if args.eliminated >= args.round:
        sys.exit(
            f"Error: Cannot have {args.eliminated} eliminated players by round "
            f"{args.round} — at most {args.round - 1} eliminations "
            f"(one per completed round)"
        )

    alive_count = total - args.eliminated
    if alive_count < 2:
        sys.exit(f"Error: Only {alive_count} alive — need at least 2")

    if phase not in VALID_PHASES.get(rt, set()):
        valid = ", ".join(sorted(p.value for p in VALID_PHASES[rt]))
        sys.exit(
            f"Error: Phase '{phase.value}' is not valid for {rt.value} rounds. "
            f"Valid phases: {valid}"
        )

    if phase == GamePhase.CHAIN and args.sub_round is not None:
        if args.sub_round < 0 or args.sub_round > 7:
            sys.exit(f"Error: Sub-round must be 0-7, got {args.sub_round}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def generate(args: argparse.Namespace) -> dict:
    """Generate a complete SeedGameRequest dict."""
    phase = GamePhase(args.phase)

    # --- Lobby shortcut ---
    if phase == GamePhase.LOBBY:
        players = _make_players(args.humans, args.ai, 0)
        max_rounds = max(3, args.humans + 1)
        state = TellGameState(
            game_id=generate_game_id(),
            phase=GamePhase.LOBBY,
            players=players,
            round_number=0,
            max_rounds=max_rounds,
            round_types=_select_round_types(max_rounds),
        )
        return {
            "state": json.loads(state.model_dump_json()),
            "start_timers": False,
            "trigger_ai": False,
        }

    # --- Game over shortcut ---
    if phase == GamePhase.GAME_OVER:
        players = _make_players(args.humans, args.ai, args.eliminated)
        winner = args.winner or "humans"
        state = TellGameState(
            game_id=generate_game_id(),
            phase=GamePhase.GAME_OVER,
            players=players,
            round_number=args.round,
            max_rounds=args.round,
            round_types=_select_round_types(args.round),
            winner=winner,
        )
        return {
            "state": json.loads(state.model_dump_json()),
            "start_timers": False,
            "trigger_ai": False,
        }

    # --- Active game ---
    players = _make_players(args.humans, args.ai, args.eliminated)
    alive_players = [p for p in players if p.is_alive]
    max_rounds = max(3, args.humans + 1)
    round_types_list = _select_round_types(max_rounds)

    rt = RoundType(args.round_type) if args.round_type else round_types_list[args.round - 1]

    # Track prompt usage from prior rounds
    (
        used_prompt_indices,
        last_prompt_category,
        used_task_prompt_indices,
        last_task_prompt_category,
    ) = _track_prior_rounds(round_types_list, args.round)

    # Build round state for target phase
    sub_round = args.sub_round if args.sub_round is not None else 0
    round_state, upi, lpc, utpi, ltpc = _derive_round_state(
        phase=phase,
        round_number=args.round,
        round_type=rt,
        alive_players=alive_players,
        used_prompt_indices=used_prompt_indices,
        last_prompt_category=last_prompt_category,
        used_task_prompt_indices=used_task_prompt_indices,
        last_task_prompt_category=last_task_prompt_category,
        sub_round=sub_round,
    )

    state = TellGameState(
        game_id=generate_game_id(),
        phase=phase,
        players=players,
        current_round=round_state,
        round_number=args.round,
        max_rounds=max_rounds,
        round_types=round_types_list,
        used_prompt_indices=upi,
        used_task_prompt_indices=utpi,
        last_prompt_category=lpc,
        last_task_prompt_category=ltpc,
        phase_deadline=None,
    )

    return {
        "state": json.loads(state.model_dump_json()),
        "start_timers": not args.no_timers,
        "trigger_ai": not args.no_ai,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate valid TellGameState JSON for the debug seed endpoint.",
    )
    parser.add_argument(
        "--phase", default="prompt",
        choices=[p.value for p in GamePhase],
        help="Game phase to seed into (default: prompt)",
    )
    parser.add_argument(
        "--round", type=int, default=1,
        help="Round number, 1-indexed (default: 1)",
    )
    parser.add_argument(
        "--humans", type=int, default=3,
        help="Number of human players (default: 3)",
    )
    parser.add_argument(
        "--ai", type=int, default=2,
        help="Number of AI players (default: 2)",
    )
    parser.add_argument(
        "--eliminated", type=int, default=0,
        help="Number of eliminated players (default: 0)",
    )
    parser.add_argument(
        "--no-timers", action="store_true",
        help="Freeze the phase (start_timers=false)",
    )
    parser.add_argument(
        "--no-ai", action="store_true",
        help="AI players don't act (trigger_ai=false)",
    )
    parser.add_argument(
        "--round-type",
        choices=[rt.value for rt in RoundType if rt != RoundType.PROBE],
        help="Override round type (default: auto from cycle)",
    )
    parser.add_argument(
        "--sub-round", type=int, default=None,
        help="Word chain sub-round, 0-7 (default: 0)",
    )
    parser.add_argument(
        "--winner", choices=["humans", "ai"],
        help="Winner for game_over phase (default: humans)",
    )

    args = parser.parse_args()
    _validate_args(args)
    result = generate(args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
