"""Test data factories — plain functions that build Pydantic models with sensible defaults."""

from __future__ import annotations

import uuid

from schemas.game_state import (
    GamePhase,
    Player,
    PlayerRole,
    RoundState,
    RoundType,
    TellGameState,
    WagerQuestion,
)


def make_player(
    *,
    role: PlayerRole = PlayerRole.HUMAN,
    alias: str | None = None,
    is_host: bool = False,
    player_id: str | None = None,
    is_connected: bool = True,
    score: int = 0,
) -> Player:
    pid = player_id or uuid.uuid4().hex[:8]
    return Player(
        id=pid,
        alias=alias or f"UNIT-{pid[:2].upper()}",
        role=role,
        is_host=is_host,
        is_connected=is_connected,
        score=score,
    )


def make_round_state(
    *,
    round_number: int = 1,
    round_type: RoundType = RoundType.TASK,
    prompt_text: str = "Test prompt",
    prompt_category: str = "logical",
    answers: dict[str, str] | None = None,
    gallery_votes: dict[str, str] | None = None,
    wager_questions: list[WagerQuestion] | None = None,
) -> RoundState:
    return RoundState(
        round_number=round_number,
        prompt_text=prompt_text,
        prompt_category=prompt_category,
        round_type=round_type,
        answers=answers or {},
        gallery_votes=gallery_votes or {},
        wager_questions=wager_questions or [],
    )


def make_game_state(
    *,
    game_id: str = "test1234",
    phase: GamePhase = GamePhase.PROMPT,
    players: list[Player] | None = None,
    round_number: int = 1,
    round_type: RoundType = RoundType.TASK,
    total_rounds: int = 5,
    round_types: list[RoundType] | None = None,
    current_round: RoundState | None = "auto",
    winner: str | None = None,
) -> TellGameState:
    if current_round == "auto":
        current_round = make_round_state(round_number=round_number, round_type=round_type)

    return TellGameState(
        game_id=game_id,
        phase=phase,
        players=players or [],
        current_round=current_round,
        round_number=round_number,
        total_rounds=total_rounds,
        round_types=round_types or [],
        winner=winner,
    )


def make_wager_question(
    *,
    question: str = "How many?",
    correct_answer: int = 50,
    range_min: int = 0,
    range_max: int = 100,
    unit: str = "units",
    category: str = "test",
    guesses: dict[str, int] | None = None,
    bets: dict[str, str] | None = None,
) -> WagerQuestion:
    return WagerQuestion(
        question=question,
        correct_answer=correct_answer,
        range_min=range_min,
        range_max=range_max,
        unit=unit,
        category=category,
        guesses=guesses or {},
        bets=bets or {},
    )


def make_standard_game(
    *,
    phase: GamePhase = GamePhase.PROMPT,
    round_type: RoundType = RoundType.TASK,
) -> tuple[TellGameState, list[Player]]:
    """8-player game: 2 human (first is host), 6 AI. Returns (state, players)."""
    h1 = make_player(role=PlayerRole.HUMAN, alias="UNIT-01", player_id="h1", is_host=True)
    h2 = make_player(role=PlayerRole.HUMAN, alias="BOT-42", player_id="h2")
    a1 = make_player(role=PlayerRole.AI, alias="CORE-07", player_id="a1")
    a2 = make_player(role=PlayerRole.AI, alias="WIRE-13", player_id="a2")
    a3 = make_player(role=PlayerRole.AI, alias="NODE-05", player_id="a3")
    a4 = make_player(role=PlayerRole.AI, alias="GRID-11", player_id="a4")
    a5 = make_player(role=PlayerRole.AI, alias="BYTE-03", player_id="a5")
    a6 = make_player(role=PlayerRole.AI, alias="FLUX-09", player_id="a6")
    players = [h1, h2, a1, a2, a3, a4, a5, a6]

    state = make_game_state(
        phase=phase,
        players=players,
        round_type=round_type,
        round_types=[RoundType.TASK],
    )
    return state, players
