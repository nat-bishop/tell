"""AI player agent — generates answers, questions, responses,
votes, nominations, synthesis, and verdicts.

Two agent tiers:
  Character agents (ai_agent, narrator_agent) — personality-driven, maintain
  message history across a game.
  Utility agents (synthesis, verdict, association, brain_test) — stateless
  one-shot calls with fixed purpose.
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
    ASSOCIATION_SYSTEM_PROMPT_TEMPLATE,
    NARRATOR_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
    VERDICT_SYSTEM_PROMPT,
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
    alive_players: list[str]  # list of aliases
    round_number: int
    round_type: RoundType = RoundType.TASK
    assigned_target: str | None = None  # alias of assigned target
    my_answer: str | None = None
    questions: list[dict] | None = None  # [{target_alias, question, response}]
    # Interrogation-specific
    nominated_alias: str | None = None
    synthesis: str | None = None
    hot_seat_response: str | None = None
    # Action-specific context injected by the caller
    action_prompt: str = ""


# ---------------------------------------------------------------------------
# Structured output models
# ---------------------------------------------------------------------------


class NominationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_alias: str = Field(description="Alias of the player you nominate (e.g. UNIT-7)")
    reasoning: str = Field(description="Brief reasoning (1 sentence)")

    @field_validator("target_alias")
    @classmethod
    def check_alias(cls, v: str, info: ValidationInfo) -> str:
        valid = info.context
        if valid and v not in valid:
            raise ValueError(f"'{v}' not valid. Choose from: {', '.join(valid)}")
        return v


class VoteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[str] = Field(description="Player aliases you suspect are human")
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
    validation_context=lambda ctx: [
        a for a in ctx.deps.alive_players if a != ctx.deps.player_alias
    ],
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

synthesis_agent: Agent[None, str] = Agent(
    output_type=str,
    retries=1,
    instructions=SYNTHESIS_SYSTEM_PROMPT,
    model_settings={"max_tokens": 300},
)

verdict_agent: Agent[None, str] = Agent(
    output_type=str,
    retries=1,
    instructions=VERDICT_SYSTEM_PROMPT,
    model_settings={"max_tokens": 100},
)

association_agent: Agent[None, str] = Agent(
    output_type=str,
    retries=1,
    model_settings={"max_tokens": 20},
)

brain_test_agent: Agent[None, str] = Agent(
    output_type=str,
    retries=1,
    instructions="Answer concisely.",
    model_settings={"max_tokens": 50},
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
        result = await ai_agent.run(
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


async def generate_question(
    deps: AIPlayerDeps,
    message_history: list[ModelMessage] | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Generate a follow-up question about another player's answer."""
    try:
        return await _run_ai_agent(deps, "question", message_history)
    except Exception:
        return deps.personality.fallback_response, message_history or []


async def generate_question_response(
    deps: AIPlayerDeps,
    question: str,
    message_history: list[ModelMessage] | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Respond to an anonymous question about your answer."""
    try:
        return await _run_ai_agent(deps, "response", message_history)
    except Exception:
        return deps.personality.fallback_response, message_history or []


async def generate_nomination(
    deps: AIPlayerDeps,
    message_history: list[ModelMessage] | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Pick a player to nominate for the hot seat (Interrogation)."""
    other_players = [a for a in deps.alive_players if a != deps.player_alias]
    if not other_players:
        alias = deps.alive_players[0] if deps.alive_players else ""
        return alias, message_history or []
    try:
        output, messages = await _run_ai_agent(
            deps,
            "nomination",
            message_history,
            output_type=NominationResponse,
        )
        return output.target_alias, messages
    except Exception:
        return random.choice(other_players), message_history or []


async def decide_vote(
    deps: AIPlayerDeps,
    message_history: list[ModelMessage] | None = None,
) -> tuple[list[str], list[ModelMessage]]:
    """Decide who to vote for. Returns list of target aliases (up to max_votes)."""
    other_players = [a for a in deps.alive_players if a != deps.player_alias]
    if not other_players:
        return [], message_history or []

    from backend.services.game_logic import max_votes_for_player

    max_v = max_votes_for_player(len(deps.alive_players))
    try:
        output, messages = await _run_ai_agent(
            deps,
            "vote",
            message_history,
            output_type=VoteResponse,
        )
        return output.targets[:max_v], messages
    except Exception:
        picks = random.sample(other_players, min(max_v, len(other_players)))
        return picks, message_history or []


async def generate_discussion_message(
    deps: AIPlayerDeps,
    message_history: list[ModelMessage] | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Generate a discussion chat message in character."""
    try:
        output, messages = await _run_ai_agent(deps, "discussion", message_history)
        return output[:100], messages
    except Exception:
        return "", message_history or []


# ---------------------------------------------------------------------------
# Utility-agent generators (no personality, no history)
# ---------------------------------------------------------------------------


async def synthesize_questions(
    questions: list[str],
    target_alias: str,
    target_answer: str,
    prompt_text: str,
    *,
    game_id: str | None = None,
) -> str:
    """Synthesize multiple questions into one cross-examination paragraph."""
    if not questions:
        return f"The group had no questions for {target_alias}."

    questions_formatted = "\n".join(f"- {q}" for q in questions)
    user_prompt = (
        f'The prompt was: "{prompt_text}"\n'
        f'{target_alias} answered: "{target_answer}"\n\n'
        f"Questions from the group:\n{questions_formatted}"
    )

    result = await _run_system_call(synthesis_agent, user_prompt, timeout=5.0, game_id=game_id)
    if result:
        return result

    # Fallback: numbered list
    return "The group asks:\n" + "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))


async def generate_verdict(
    alias: str,
    was_human: bool,
    prompt_text: str,
    answer: str,
    vote_count: int,
    round_number: int,
    max_rounds: int,
    *,
    game_id: str | None = None,
) -> str | None:
    """Generate a one-line dramatic verdict summary after elimination."""
    role = "human" if was_human else "AI"

    user_prompt = (
        f"{alias} was revealed as {role}.\n"
        f'The prompt was: "{prompt_text}"\n'
        f'Their answer: "{answer}"\n'
        f"They received {vote_count} votes in round {round_number} of {max_rounds}."
    )

    return await _run_system_call(verdict_agent, user_prompt, timeout=3.0, game_id=game_id)


async def generate_association(
    seed_word: str,
    personality: Personality,
    chain_history: list[str] | None = None,
    *,
    game_id: str | None = None,
) -> str:
    """Generate a single-word association for Word Chain. Personality-aware, lightweight."""
    history_text = f"\nChain so far: {' → '.join(chain_history)}" if chain_history else ""
    user_prompt = f"Word: {seed_word}{history_text}"

    result = await _run_system_call(
        association_agent,
        user_prompt,
        timeout=3.0,
        game_id=game_id,
        instructions=ASSOCIATION_SYSTEM_PROMPT_TEMPLATE.format(hint=personality.chain_style_hint),
    )
    if result:
        # Clean up: take first word only
        word = result.strip().split()[0].strip(".,!?\"'").lower()
        if word:
            return word

    # Fallback
    from schemas.word_chain import get_fallback_association

    return get_fallback_association(seed_word)


async def generate_brain_test_answer(
    question: str,
    personality_name: str,
    *,
    game_id: str | None = None,
) -> str | None:
    """Generate a short answer to a brain test challenge.

    Returns None on timeout/failure.
    """
    prompt = (
        f"You are playing a brain test game. "
        f"Your personality: {personality_name}. "
        f"Question: {question}\n"
        "Give a short answer (a few words). Just the answer, nothing else."
    )
    return await _run_system_call(brain_test_agent, prompt, timeout=3.0, game_id=game_id)


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
    timeout = 5.0 if trigger in ("game_over", "verdict") else 3.0
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
