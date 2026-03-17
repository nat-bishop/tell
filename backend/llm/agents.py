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
    """Dynamic system prompt — personality + game context. Static per game, cacheable."""
    deps = ctx.deps
    parts = [
        deps.personality.answer_system_prompt,
        "",
        f"You are {deps.player_alias} in a multiplayer game called Tell.",
        "All players claim to be robots. Some are secretly human.",
        f"This is round {deps.round_number}. Round type: {deps.round_type}.",
        f"Alive players: {', '.join(deps.alive_players)}.",
    ]

    if deps.all_answers:
        parts.append("\nAnswers from this round:")
        for alias, answer in deps.all_answers.items():
            parts.append(f"  {alias}: {answer}")

    if deps.questions:
        parts.append("\nQuestions and responses this round:")
        for q in deps.questions:
            line = f'  {q["target_alias"]} was asked: "{q["question"]}"'
            if q.get("response"):
                line += f' → responded: "{q["response"]}"'
            parts.append(line)

    if deps.synthesis:
        parts.append(f"\nSynthesized question: {deps.synthesis}")

    if deps.hot_seat_response:
        parts.append(f"\n{deps.nominated_alias} responded: {deps.hot_seat_response}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# System agent (synthesis, verdict — no personality, no history)
# ---------------------------------------------------------------------------


async def _run_system_agent(
    system_prompt: str, user_prompt: str, timeout: float = 5.0
) -> str | None:
    """Run a system-level LLM call (not personality-based). Returns None on failure."""
    settings = get_settings()
    log.info("llm_system_call_start", model=settings.ai_model)
    try:
        agent = Agent(
            model=settings.ai_model,
            retries=1,
            output_type=str,
            instructions=system_prompt,
        )
        result = await asyncio.wait_for(agent.run(user_prompt), timeout=timeout)
        log.info("llm_system_call_done", output_len=len(result.output))
        return result.output
    except Exception:
        log.exception("llm_system_call_failed")
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
    log.info("llm_call_start", player=deps.player_alias, action="answer", model=settings.ai_model)
    try:
        result = await ai_agent.run(
            deps.action_prompt,
            model=settings.ai_model,
            deps=deps,
            message_history=message_history,
        )
        log.info(
            "llm_call_done",
            player=deps.player_alias,
            action="answer",
            output_len=len(result.output),
        )
        return result.output, result.all_messages()
    except Exception:
        log.exception("ai_agent_failed", player=deps.player_alias, action="answer")
        return deps.personality.fallback_response, message_history or []


async def generate_question(
    deps: AIPlayerDeps,
    message_history: list[ModelMessage] | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Generate a follow-up question about another player's answer."""
    settings = get_settings()
    log.info("llm_call_start", player=deps.player_alias, action="question", model=settings.ai_model)
    try:
        result = await ai_agent.run(
            deps.action_prompt,
            model=settings.ai_model,
            deps=deps,
            message_history=message_history,
        )
        log.info(
            "llm_call_done",
            player=deps.player_alias,
            action="question",
            output_len=len(result.output),
        )
        return result.output, result.all_messages()
    except Exception:
        log.exception("ai_agent_failed", player=deps.player_alias, action="question")
        return deps.personality.fallback_response, message_history or []


async def generate_question_response(
    deps: AIPlayerDeps,
    question: str,
    message_history: list[ModelMessage] | None = None,
) -> tuple[str, list[ModelMessage]]:
    """Respond to an anonymous question about your answer."""
    settings = get_settings()
    log.info("llm_call_start", player=deps.player_alias, action="response", model=settings.ai_model)
    try:
        result = await ai_agent.run(
            deps.action_prompt,
            model=settings.ai_model,
            deps=deps,
            message_history=message_history,
        )
        log.info(
            "llm_call_done",
            player=deps.player_alias,
            action="response",
            output_len=len(result.output),
        )
        return result.output, result.all_messages()
    except Exception:
        log.exception("ai_agent_failed", player=deps.player_alias, action="response")
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
    log.info(
        "llm_call_start", player=deps.player_alias, action="nomination", model=settings.ai_model
    )
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
            player=deps.player_alias,
            action="nomination",
            target=result.output.target_alias,
        )
        return result.output.target_alias, result.all_messages()
    except Exception:
        log.exception("ai_agent_failed", player=deps.player_alias, action="nomination")
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
    log.info("llm_call_start", player=deps.player_alias, action="vote", model=settings.ai_model)
    try:
        result = await ai_agent.run(
            deps.action_prompt,
            model=settings.ai_model,
            deps=deps,
            output_type=VoteResponse,
            message_history=message_history,
        )
        targets = result.output.targets[:max_v]
        log.info("llm_call_done", player=deps.player_alias, action="vote", targets=targets)
        return targets, result.all_messages()
    except Exception:
        log.exception("ai_agent_failed", player=deps.player_alias, action="vote")
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
) -> str:
    """Synthesize multiple questions into one cross-examination paragraph."""
    if not questions:
        return f"The group had no questions for {target_alias}."

    system_prompt = (
        "You are the narrator of Tell, a social deduction game where players pretend to be robots. "
        "One player is being interrogated by the group. Synthesize multiple questions into ONE "
        "cohesive cross-examination paragraph.\n\n"
        "Rules:\n"
        "- Weave all threads together naturally. Do NOT list questions or use bullet points.\n"
        '- Address the target directly: "Your answer...", "The group noticed..."\n'
        "- Tone: sharp, literary, like a cross-examiner at a tribunal "
        "— not aggressive, but pointed.\n"
        "- 2-3 sentences maximum.\n"
        "- Consolidate overlapping questions. Preserve the sharpest angles.\n"
        "- End with something the player must directly address.\n\n"
        "Write ONLY the synthesis paragraph."
    )

    questions_formatted = "\n".join(f"- {q}" for q in questions)
    user_prompt = (
        f'The prompt was: "{prompt_text}"\n'
        f'{target_alias} answered: "{target_answer}"\n\n'
        f"Questions from the group:\n{questions_formatted}"
    )

    result = await _run_system_agent(system_prompt, user_prompt, timeout=5.0)
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
) -> str | None:
    """Generate a one-line dramatic verdict summary after elimination."""
    role = "human" if was_human else "AI"

    system_prompt = (
        "You are the narrator of Tell. A player was just eliminated and their true identity "
        "revealed. Write exactly ONE dramatic sentence — a case summary of their performance.\n\n"
        "Rules:\n"
        "- One sentence only. No more.\n"
        "- Literary tone, like the closing line of a short story.\n"
        "- Reference their actual answer, not generalities.\n"
        '- If human: note what was "too genuine" or what cracked their disguise.\n'
        '- If AI: note what was "too precise" or "too calculated" '
        "or what fooled/didn't fool the group.\n"
        "- Be wry, not cruel. Think: dry wit, not mockery.\n\n"
        "Write ONLY the verdict sentence."
    )

    user_prompt = (
        f"{alias} was revealed as {role}.\n"
        f'The prompt was: "{prompt_text}"\n'
        f'Their answer: "{answer}"\n'
        f"They received {vote_count} votes in round {round_number} of {max_rounds}."
    )

    return await _run_system_agent(system_prompt, user_prompt, timeout=3.0)


async def generate_association(
    seed_word: str,
    personality: Personality,
    chain_history: list[str] | None = None,
) -> str:
    """Generate a single-word association for Word Chain. Personality-aware, lightweight."""
    style_hints = {
        "paranoid": "Think of something unsettling or suspicious.",
        "chill": "Think of the most obvious connection.",
        "overachiever": "Think of a precise, specific connection.",
        "glitchy": "Think of a slightly unexpected connection.",
        "philosopher": "Think of an abstract or existential leap.",
    }
    hint = style_hints.get(personality.name, "")

    history_text = ""
    if chain_history:
        history_text = f"\nChain so far: {' → '.join(chain_history)}"

    system_prompt = (
        "You are playing a word association game. Given a word, respond with ONE single word "
        "that you associate with it. Rules:\n"
        "- Exactly ONE word. No punctuation, no explanation.\n"
        "- Be creative but connected. The association should make sense.\n"
        "- Do NOT repeat any word already in the chain.\n"
        f"- {hint}\n"
        "Respond with ONLY the single word."
    )

    user_prompt = f"Word: {seed_word}{history_text}"

    result = await _run_system_agent(system_prompt, user_prompt, timeout=3.0)
    if result:
        # Clean up: take first word only
        word = result.strip().split()[0].strip(".,!?\"'").lower()
        if word:
            return word

    # Fallback
    from schemas.word_chain import get_fallback_association

    return get_fallback_association(seed_word)
