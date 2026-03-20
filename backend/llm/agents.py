"""AI player agent — generates answers, votes, brain test answers, and narration.

Two agent tiers:
  Character agents (ai_agent, narrator_agent) — personality-driven, maintain
  message history across a game.
  Utility agents (brain_test) — stateless one-shot calls with fixed purpose.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.messages import ModelMessage

from backend.api.deps import get_settings
from backend.llm.personalities import Personality
from backend.llm.prompts import (
    NARRATOR_SYSTEM_PROMPT,
    build_gallery_vote_prompt,
    build_system_prompt,
)
from schemas.game_state import RoundType

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Deps
# ---------------------------------------------------------------------------


@dataclass
class AIPlayerDeps:
    """Context for AI player actions."""

    personality: Personality
    player_alias: str
    current_prompt: str
    all_answers: dict[str, str]  # alias -> answer text
    players: list[str]  # list of aliases
    round_number: int
    round_type: RoundType = RoundType.TASK
    my_answer: str | None = None
    # Action-specific context injected by the caller
    action_prompt: str = ""


# ---------------------------------------------------------------------------
# Structured output models
# ---------------------------------------------------------------------------


class VoteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[str] = Field(description="Player aliases you think sound most human")
    reasoning: str = Field(description="Brief reasoning (1 sentence)")

    @field_validator("targets")
    @classmethod
    def check_targets(cls, v: list[str], info: ValidationInfo) -> list[str]:
        valid = info.context
        if valid:
            bad = [t for t in v if t not in valid]
            if bad:
                raise ValueError(f"Invalid: {bad}. Choose from: {', '.join(valid)}")
        return v


# ---------------------------------------------------------------------------
# Character agents — personality-driven, maintain message history
# ---------------------------------------------------------------------------

ai_agent: Agent[AIPlayerDeps, str] = Agent(
    output_type=str,
    deps_type=AIPlayerDeps,
    retries=2,
    model_settings={"max_tokens": 200},
    validation_context=lambda ctx: [a for a in ctx.deps.players if a != ctx.deps.player_alias],
)

narrator_agent: Agent[None, str] = Agent(
    output_type=str,
    retries=1,
    instructions=NARRATOR_SYSTEM_PROMPT,
    model_settings={"max_tokens": 200},
)


@ai_agent.instructions
def _build_instructions(ctx: RunContext[AIPlayerDeps]) -> str:
    """Dynamic system prompt — personality + game context."""
    return build_system_prompt(ctx.deps)


# ---------------------------------------------------------------------------
# Utility agents — stateless one-shot calls
# ---------------------------------------------------------------------------

brain_test_agent: Agent[None, str] = Agent(
    output_type=str,
    retries=1,
    instructions="Pick the best option. Reply with ONLY the number (0, 1, 2, or 3).",
    model_settings={"max_tokens": 10},
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _log_fields(deps: AIPlayerDeps) -> dict:
    """Common structured log fields for LLM calls."""
    return {
        "player": deps.player_alias,
        "personality": deps.personality.name,
        "round": deps.round_number,
        "round_type": deps.round_type,
    }


async def _run_ai_agent(
    deps: AIPlayerDeps,
    action: str,
    message_history: list[ModelMessage] | None = None,
    *,
    output_type: type = str,
) -> tuple[Any, list[ModelMessage]]:
    """Run ai_agent for a character action. Logs with tiered severity, re-raises on failure."""
    settings = get_settings()
    fields = _log_fields(deps)
    log.info("llm_call_start", action=action, model=settings.ai_model, **fields)
    try:
        result: Any = await ai_agent.run(
            deps.action_prompt,
            model=settings.ai_model,
            deps=deps,
            output_type=output_type,
            message_history=message_history,
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


async def _run_system_call(
    agent: Agent[None, str],
    user_prompt: str,
    timeout: float = 5.0,
    *,
    game_id: str | None = None,
    instructions: str | None = None,
) -> str | None:
    """Run a stateless utility agent. Returns None on any failure."""
    settings = get_settings()
    log.info("llm_system_call_start", game_id=game_id)
    try:
        result = await asyncio.wait_for(
            agent.run(user_prompt, model=settings.ai_model, instructions=instructions),
            timeout=timeout,
        )
        log.info("llm_system_call_done", output_len=len(result.output), game_id=game_id)
        return result.output
    except TimeoutError:
        log.info("llm_system_timeout", game_id=game_id)
        return None
    except (ModelHTTPError, ModelAPIError) as exc:
        log.warning("llm_system_api_error", error=str(exc), game_id=game_id)
        return None
    except Exception:
        log.exception("llm_system_failed", game_id=game_id)
        return None


# ---------------------------------------------------------------------------
# Character-agent generate functions
# ---------------------------------------------------------------------------


async def generate_answer(
    deps: AIPlayerDeps,
    message_history: list[ModelMessage] | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Generate an answer to a prompt in character."""
    try:
        return await _run_ai_agent(deps, "answer", message_history)
    except Exception:
        return deps.personality.fallback_response, message_history or []


async def decide_gallery_vote(
    prompt_text: str,
    answers_by_alias: dict[str, str],
    *,
    game_id: str | None = None,
) -> str | None:
    """Decide who to vote for in gallery vote. Returns the alias of the chosen player.

    Falls back to None on timeout/failure (caller should pick random).
    """
    vote_prompt = build_gallery_vote_prompt(prompt_text, answers_by_alias)
    result = await _run_system_call(
        brain_test_agent,  # reuse simple agent
        vote_prompt,
        timeout=3.0,
        game_id=game_id,
        instructions="Pick the answer that sounds most like it was written by a human. "
        "Reply with ONLY the alias (e.g., UNIT-7). Nothing else.",
    )
    if result:
        stripped = result.strip().upper()
        # Try to match against known aliases
        for alias in answers_by_alias:
            if alias.upper() in stripped or stripped in alias.upper():
                return alias
    return None


# ---------------------------------------------------------------------------
# Utility-agent generators (no personality, no history)
# ---------------------------------------------------------------------------


async def generate_brain_test_answer(
    question: str,
    options: list[str],
    *,
    game_id: str | None = None,
) -> int:
    """Select an option for a brain test challenge. Returns the selected index (0-3).

    Falls back to random selection on timeout/failure.
    """
    options_text = "\n".join(f"{i}. {opt}" for i, opt in enumerate(options))
    prompt = f"Question: {question}\n\nOptions:\n{options_text}\n\nReply with ONLY the number."

    result = await _run_system_call(brain_test_agent, prompt, timeout=3.0, game_id=game_id)
    if result:
        # Parse the number from the response
        stripped = result.strip()
        for ch in stripped:
            if ch in "0123":
                return int(ch)

    # Fallback: random selection
    return random.randint(0, len(options) - 1)


async def generate_narration(
    trigger: str,
    context: str,
    *,
    game_id: str | None = None,
    message_history: list[ModelMessage] | None = None,
) -> tuple[str | None, list[ModelMessage]]:
    """Generate a narrator line for a specific game moment.

    Returns (text, updated_history). Text is None on timeout/failure.
    """
    settings = get_settings()
    timeout = 5.0 if trigger == "game_over" else 3.0
    log.info("llm_narrator_call_start", trigger=trigger, game_id=game_id)
    try:
        result = await asyncio.wait_for(
            narrator_agent.run(
                context,
                model=settings.ai_model,
                message_history=message_history,
            ),
            timeout=timeout,
        )
        log.info("llm_narrator_call_done", output_len=len(result.output), game_id=game_id)
        return result.output, result.all_messages()
    except TimeoutError:
        log.info("llm_narrator_timeout", trigger=trigger, game_id=game_id)
        return None, message_history or []
    except (ModelHTTPError, ModelAPIError) as exc:
        log.warning("llm_narrator_api_error", error=str(exc), trigger=trigger, game_id=game_id)
        return None, message_history or []
    except Exception:
        log.exception("llm_narrator_failed", game_id=game_id)
        return None, message_history or []
