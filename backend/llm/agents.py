"""AI player agent — generates answers, questions, responses,
votes, nominations, synthesis, and verdicts."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

import structlog
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage

from backend.api.deps import get_settings
from backend.llm.personalities import Personality
from backend.llm.prompts import (
    ASSOCIATION_SYSTEM_PROMPT_TEMPLATE,
    SYNTHESIS_SYSTEM_PROMPT,
    VERDICT_SYSTEM_PROMPT,
    build_system_prompt,
)

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
    round_type: str = "probe"
    # Probe-specific
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
# Module-level agent
# ---------------------------------------------------------------------------

ai_agent: Agent[AIPlayerDeps, str] = Agent(
    output_type=str,
    deps_type=AIPlayerDeps,
    retries=2,
    validation_context=lambda ctx: [
        a for a in ctx.deps.alive_players if a != ctx.deps.player_alias
    ],
)


@ai_agent.instructions
def _build_instructions(ctx: RunContext[AIPlayerDeps]) -> str:
    """Dynamic system prompt — personality + game context."""
    return build_system_prompt(ctx.deps)


# ---------------------------------------------------------------------------
# Shared log fields
# ---------------------------------------------------------------------------


def _log_fields(deps: AIPlayerDeps) -> dict:
    """Common structured log fields for LLM calls."""
    return {
        "player": deps.player_alias,
        "personality": deps.personality.name,
        "round": deps.round_number,
        "round_type": deps.round_type,
    }


# ---------------------------------------------------------------------------
# System agent (synthesis, verdict — no personality, no history)
# ---------------------------------------------------------------------------


async def _run_system_agent(
    system_prompt: str,
    user_prompt: str,
    timeout: float = 5.0,
    *,
    game_id: str | None = None,
) -> str | None:
    """Run a system-level LLM call (not personality-based). Returns None on failure."""
    settings = get_settings()
    log.info("llm_system_call_start", model=settings.ai_model, game_id=game_id)
    try:
        agent = Agent(
            model=settings.ai_model,
            retries=1,
            output_type=str,
            instructions=system_prompt,
        )
        result = await asyncio.wait_for(agent.run(user_prompt), timeout=timeout)
        log.info("llm_system_call_done", output_len=len(result.output), game_id=game_id)
        return result.output
    except Exception:
        log.exception("llm_system_call_failed", game_id=game_id)
        return None


# ---------------------------------------------------------------------------
# Generate functions — all accept/return message_history
# ---------------------------------------------------------------------------


async def generate_answer(
    deps: AIPlayerDeps,
    message_history: list[ModelMessage] | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Generate an answer to a prompt in character."""
    settings = get_settings()
    fields = _log_fields(deps)
    log.info("llm_call_start", action="answer", model=settings.ai_model, **fields)
    try:
        result = await ai_agent.run(
            deps.action_prompt,
            model=settings.ai_model,
            deps=deps,
            message_history=message_history,
        )
        log.info("llm_call_done", action="answer", output_len=len(result.output), **fields)
        return result.output, result.all_messages()
    except Exception:
        log.exception("ai_agent_failed", action="answer", **fields)
        return deps.personality.fallback_response, message_history or []


async def generate_question(
    deps: AIPlayerDeps,
    message_history: list[ModelMessage] | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Generate a follow-up question about another player's answer."""
    settings = get_settings()
    fields = _log_fields(deps)
    log.info("llm_call_start", action="question", model=settings.ai_model, **fields)
    try:
        result = await ai_agent.run(
            deps.action_prompt,
            model=settings.ai_model,
            deps=deps,
            message_history=message_history,
        )
        log.info("llm_call_done", action="question", output_len=len(result.output), **fields)
        return result.output, result.all_messages()
    except Exception:
        log.exception("ai_agent_failed", action="question", **fields)
        return deps.personality.fallback_response, message_history or []


async def generate_question_response(
    deps: AIPlayerDeps,
    question: str,
    message_history: list[ModelMessage] | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Respond to an anonymous question about your answer."""
    settings = get_settings()
    fields = _log_fields(deps)
    log.info("llm_call_start", action="response", model=settings.ai_model, **fields)
    try:
        result = await ai_agent.run(
            deps.action_prompt,
            model=settings.ai_model,
            deps=deps,
            message_history=message_history,
        )
        log.info("llm_call_done", action="response", output_len=len(result.output), **fields)
        return result.output, result.all_messages()
    except Exception:
        log.exception("ai_agent_failed", action="response", **fields)
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

    settings = get_settings()
    fields = _log_fields(deps)
    log.info("llm_call_start", action="nomination", model=settings.ai_model, **fields)
    try:
        result = await ai_agent.run(
            deps.action_prompt,
            model=settings.ai_model,
            deps=deps,
            output_type=NominationResponse,
            message_history=message_history,
        )
        log.info(
            "llm_call_done",
            action="nomination",
            target=result.output.target_alias,
            **fields,
        )
        return result.output.target_alias, result.all_messages()
    except Exception:
        log.exception("ai_agent_failed", action="nomination", **fields)
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

    settings = get_settings()
    fields = _log_fields(deps)
    log.info("llm_call_start", action="vote", model=settings.ai_model, **fields)
    try:
        result = await ai_agent.run(
            deps.action_prompt,
            model=settings.ai_model,
            deps=deps,
            output_type=VoteResponse,
            message_history=message_history,
        )
        targets = result.output.targets[:max_v]
        log.info("llm_call_done", action="vote", targets=targets, **fields)
        return targets, result.all_messages()
    except Exception:
        log.exception("ai_agent_failed", action="vote", **fields)
        # Fallback: random votes
        picks = random.sample(other_players, min(max_v, len(other_players)))
        return picks, message_history or []


# ---------------------------------------------------------------------------
# System-level generators (no personality, no history)
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

    result = await _run_system_agent(
        SYNTHESIS_SYSTEM_PROMPT, user_prompt, timeout=5.0, game_id=game_id
    )
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

    return await _run_system_agent(
        VERDICT_SYSTEM_PROMPT, user_prompt, timeout=3.0, game_id=game_id
    )


async def generate_association(
    seed_word: str,
    personality: Personality,
    chain_history: list[str] | None = None,
    *,
    game_id: str | None = None,
) -> str:
    """Generate a single-word association for Word Chain. Personality-aware, lightweight."""
    system_prompt = ASSOCIATION_SYSTEM_PROMPT_TEMPLATE.format(hint=personality.chain_style_hint)

    history_text = ""
    if chain_history:
        history_text = f"\nChain so far: {' → '.join(chain_history)}"

    user_prompt = f"Word: {seed_word}{history_text}"

    result = await _run_system_agent(system_prompt, user_prompt, timeout=3.0, game_id=game_id)
    if result:
        # Clean up: take first word only
        word = result.strip().split()[0].strip(".,!?\"'").lower()
        if word:
            return word

    # Fallback
    from schemas.word_chain import get_fallback_association

    return get_fallback_association(seed_word)
