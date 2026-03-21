"""AI player agents — all AI actions go through ai_agent with personality + history.

ai_agent:       Character agent for all player actions (answers, votes, guesses, bets).
                Stable system prompt (personality) via instructions=, volatile context in
                user message. Maintains conversation history across the game.
narrator_agent: Narrator with its own per-game history. Unchanged.
judge_agent:    Signal judging only — system-level, not a player.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.messages import ModelMessage

from backend.api.deps import get_settings
from backend.llm.prompts import NARRATOR_SYSTEM_PROMPT

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Structured output models
# ---------------------------------------------------------------------------


class BrainTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected: int = Field(description="Number of the option you choose")
    reasoning: str = Field(description="Brief reasoning (1 sentence)")

    @field_validator("selected")
    @classmethod
    def check_in_range(cls, v: int, info: ValidationInfo) -> int:
        if info.context is not None and v not in info.context:
            raise ValueError(f"Pick from: {info.context}")
        return v


class AliasPickResponse(BaseModel):
    """Pick a player by alias."""

    model_config = ConfigDict(extra="forbid")

    selected: str = Field(description="Alias of the player you choose")

    @field_validator("selected")
    @classmethod
    def check_valid_alias(cls, v: str, info: ValidationInfo) -> str:
        if info.context is not None and v not in info.context:
            raise ValueError(f"Invalid alias '{v}'. Choose from: {info.context}")
        return v


class PlayerPickResponse(AliasPickResponse):
    """Gallery vote — pick a player by alias with reasoning."""

    reasoning: str = Field(description="Brief reasoning (1 sentence)")


class WagerGuessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int = Field(description="Your numerical estimate")


class SignalGuessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    guess: str = Field(description="Your guess of the original secret phrase")
    reasoning: str = Field(description="Brief reasoning (1 sentence)")


class JudgmentEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(description="0 = wrong, 1 = partially right, 2 = correct")

    @field_validator("score")
    @classmethod
    def check_score_range(cls, v: int) -> int:
        if v not in (0, 1, 2):
            raise ValueError(f"Score must be 0, 1, or 2, got {v}")
        return v


class SignalJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judgments: list[JudgmentEntry] = Field(description="One score per guess, in order")


# ---------------------------------------------------------------------------
# Deps — minimal, carries only validation context for structured output
# ---------------------------------------------------------------------------


@dataclass
class AICallContext:
    """Runtime context for ai_agent calls. Only carries validation data."""

    valid: list | None = None  # valid indices or aliases for validators


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

ai_agent: Agent[AICallContext, str] = Agent(
    output_type=str,
    deps_type=AICallContext,
    retries=2,
    model_settings={"max_tokens": 200},
    validation_context=lambda ctx: ctx.deps.valid,
)

narrator_agent: Agent[None, str] = Agent(
    output_type=str,
    retries=1,
    instructions=NARRATOR_SYSTEM_PROMPT,
    model_settings={"max_tokens": 200},
)

judge_agent: Agent[None, SignalJudgment] = Agent(
    output_type=SignalJudgment,
    retries=2,
    instructions=(
        "Judge whether each guess matches the original phrase in meaning.\n"
        "Score each guess:\n"
        "  2 = captures the same idea (close paraphrase or correct)\n"
        "  1 = partially right (related but missing key elements)\n"
        "  0 = wrong\n"
        "Be generous — close paraphrases count as 2."
    ),
    model_settings={"max_tokens": 200},
)


# ---------------------------------------------------------------------------
# Core runner — all player actions go through here
# ---------------------------------------------------------------------------


async def _run_ai_agent(
    user_prompt: str,
    action: str,
    message_history: list[ModelMessage] | None = None,
    *,
    instructions: str,
    output_type: type = str,
    valid: list | None = None,
    log_fields: dict | None = None,
) -> tuple[Any, list[ModelMessage]]:
    """Run ai_agent for a character action. Re-raises on failure."""
    settings = get_settings()
    fields = log_fields or {}
    log.info("llm_call_start", action=action, model=settings.ai_model, **fields)
    try:
        result: Any = await ai_agent.run(
            user_prompt,
            model=settings.ai_model,
            instructions=instructions,
            output_type=output_type,
            message_history=message_history,
            deps=AICallContext(valid=valid),
        )
        log.info("llm_call_done", action=action, output_len=len(str(result.output)), **fields)
        return result.output, result.all_messages()
    except TimeoutError:
        log.info("ai_agent_timeout", action=action, **fields)
        raise
    except (ModelHTTPError, ModelAPIError) as exc:
        log.warning("ai_agent_api_error", action=action, error=str(exc), **fields)
        raise
    except Exception:
        log.exception("ai_agent_failed", action=action, **fields)
        raise


# ---------------------------------------------------------------------------
# Generate functions — one per action, all through _run_ai_agent
# ---------------------------------------------------------------------------


async def generate_answer(
    user_prompt: str,
    instructions: str,
    message_history: list[ModelMessage] | None = None,
    *,
    fallback: str = "hmm",
    log_fields: dict | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Generate an answer to a prompt in character."""
    try:
        return await _run_ai_agent(
            user_prompt,
            "answer",
            message_history,
            instructions=instructions,
            log_fields=log_fields,
        )
    except Exception:
        return fallback, message_history or []


async def generate_brain_test_answer(
    user_prompt: str,
    instructions: str,
    message_history: list[ModelMessage] | None = None,
    *,
    valid_indices: list[int],
    log_fields: dict | None = None,
) -> tuple[int, list[ModelMessage]]:
    """Pick the best option for a brain test challenge. Auto-retries on invalid index."""
    try:
        result, history = await _run_ai_agent(
            user_prompt,
            "brain_test",
            message_history,
            instructions=instructions,
            output_type=BrainTestResponse,
            valid=valid_indices,
            log_fields=log_fields,
        )
        return result.selected, history
    except Exception:
        return random.choice(valid_indices), message_history or []


async def decide_gallery_vote(
    user_prompt: str,
    instructions: str,
    message_history: list[ModelMessage] | None = None,
    *,
    valid_aliases: list[str],
    log_fields: dict | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Vote for who sounds most human. Auto-retries on invalid alias."""
    try:
        result, history = await _run_ai_agent(
            user_prompt,
            "gallery_vote",
            message_history,
            instructions=instructions,
            output_type=PlayerPickResponse,
            valid=valid_aliases,
            log_fields=log_fields,
        )
        return result.selected, history
    except Exception:
        return random.choice(valid_aliases), message_history or []


async def generate_wager_guess(
    user_prompt: str,
    instructions: str,
    message_history: list[ModelMessage] | None = None,
    *,
    range_min: int = 0,
    range_max: int = 100,
    log_fields: dict | None = None,
) -> tuple[int, list[ModelMessage]]:
    """Generate a numerical estimate for a wager question in character."""
    try:
        result, history = await _run_ai_agent(
            user_prompt,
            "wager_guess",
            message_history,
            instructions=instructions,
            output_type=WagerGuessResponse,
            log_fields=log_fields,
        )
        return result.value, history
    except Exception:
        center = (range_min + range_max) // 2
        spread = (range_max - range_min) // 4
        value = center + random.randint(-spread, spread)
        return max(range_min, min(range_max, value)), message_history or []


async def generate_wager_bet(
    user_prompt: str,
    instructions: str,
    message_history: list[ModelMessage] | None = None,
    *,
    valid_aliases: list[str],
    log_fields: dict | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Choose whose guess is closest. Auto-retries on invalid alias."""
    try:
        result, history = await _run_ai_agent(
            user_prompt,
            "wager_bet",
            message_history,
            instructions=instructions,
            output_type=AliasPickResponse,
            valid=valid_aliases,
            log_fields=log_fields,
        )
        return result.selected, history
    except Exception:
        return random.choice(valid_aliases) if valid_aliases else "", message_history or []


async def generate_signal_guess(
    user_prompt: str,
    instructions: str,
    message_history: list[ModelMessage] | None = None,
    *,
    log_fields: dict | None = None,
) -> tuple[str | None, list[ModelMessage]]:
    """Guess the original phrase from a transformation."""
    try:
        result, history = await _run_ai_agent(
            user_prompt,
            "signal_guess",
            message_history,
            instructions=instructions,
            output_type=SignalGuessResponse,
            log_fields=log_fields,
        )
        return result.guess, history
    except Exception:
        return None, message_history or []


# ---------------------------------------------------------------------------
# Signal judging — system-level, not a player action
# ---------------------------------------------------------------------------


def _fuzzy_match(guess: str, original: str) -> bool:
    """Case-insensitive containment check as fallback for LLM judging."""
    g = guess.lower().strip()
    o = original.lower().strip()
    return g in o or o in g


async def judge_signal_guesses(
    original_phrase: str,
    guesses: dict[str, str],
    *,
    game_id: str | None = None,
) -> dict[str, int]:
    """Batch-judge all guesses for one sub-round. Returns {guesser_id: score (0/1/2)}."""
    if not guesses:
        return {}

    guesser_ids = list(guesses.keys())
    guesses_list = [guesses[gid] for gid in guesser_ids]

    from backend.llm.prompts import build_signal_judge_prompt

    prompt = build_signal_judge_prompt(original_phrase, guesses_list)
    settings = get_settings()

    log.info("llm_judge_call_start", game_id=game_id, num_guesses=len(guesses_list))
    try:
        result = await asyncio.wait_for(
            judge_agent.run(prompt, model=settings.ai_model),
            timeout=5.0,
        )
        log.info("llm_judge_call_done", game_id=game_id)

        judgments: dict[str, int] = {}
        for i, gid in enumerate(guesser_ids):
            if i < len(result.output.judgments):
                judgments[gid] = result.output.judgments[i].score
            else:
                # LLM returned fewer judgments than guesses — fallback
                judgments[gid] = 2 if _fuzzy_match(guesses[gid], original_phrase) else 0
        return judgments

    except TimeoutError:
        log.info("llm_judge_timeout", game_id=game_id)
    except (ModelHTTPError, ModelAPIError) as exc:
        log.warning("llm_judge_api_error", error=str(exc), game_id=game_id)
    except Exception:
        log.exception("llm_judge_failed", game_id=game_id)

    # Full LLM failure — fall back to fuzzy match (binary: 0 or 2)
    return {
        gid: (2 if _fuzzy_match(guess, original_phrase) else 0) for gid, guess in guesses.items()
    }


# ---------------------------------------------------------------------------
# Narrator — owns its own conversation history per game
# ---------------------------------------------------------------------------

_narrator_history: dict[str, list[ModelMessage]] = {}
_narrator_locks: dict[str, asyncio.Lock] = {}


def init_narrator(game_id: str) -> None:
    """Initialize narrator state for a new game."""
    _narrator_history[game_id] = []
    _narrator_locks[game_id] = asyncio.Lock()


def cleanup_narrator(game_id: str) -> None:
    """Clean up narrator state when a game ends."""
    _narrator_history.pop(game_id, None)
    _narrator_locks.pop(game_id, None)


async def generate_narration(
    game_id: str,
    trigger: str,
    context: str,
) -> str | None:
    """Generate a narrator line for a specific game moment."""
    lock = _narrator_locks.get(game_id)
    if not lock:
        lock = asyncio.Lock()
        _narrator_locks[game_id] = lock

    settings = get_settings()
    timeout = 5.0 if trigger == "game_over" else 3.0

    async with lock:
        history = _narrator_history.get(game_id, [])
        log.info("llm_narrator_call_start", trigger=trigger, game_id=game_id)
        try:
            result = await asyncio.wait_for(
                narrator_agent.run(
                    context,
                    model=settings.ai_model,
                    message_history=history,
                ),
                timeout=timeout,
            )
            _narrator_history[game_id] = result.all_messages()
            log.info("llm_narrator_call_done", output_len=len(result.output), game_id=game_id)
            return result.output
        except TimeoutError:
            log.info("llm_narrator_timeout", trigger=trigger, game_id=game_id)
            return None
        except (ModelHTTPError, ModelAPIError) as exc:
            log.warning("llm_narrator_api_error", error=str(exc), trigger=trigger, game_id=game_id)
            return None
        except Exception:
            log.exception("llm_narrator_failed", game_id=game_id)
            return None
