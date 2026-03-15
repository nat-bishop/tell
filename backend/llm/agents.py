"""AI player agent — generates answers, chat messages, and vote decisions."""

from __future__ import annotations

import random
from dataclasses import dataclass

import structlog
from pydantic_ai import Agent

from backend.api.deps import get_settings
from backend.llm.personalities import Personality

log = structlog.get_logger()


@dataclass
class AIPlayerDeps:
    """Context for AI player actions."""
    personality: Personality
    player_alias: str
    current_prompt: str
    all_answers: dict[str, str]  # alias -> answer text
    chat_history: list[dict[str, str]]  # [{"alias": "...", "text": "..."}, ...]
    alive_players: list[str]  # list of aliases
    round_number: int


def _build_game_context(deps: AIPlayerDeps) -> str:
    """Build game context string for the system prompt."""
    context_parts = [
        f"You are {deps.player_alias} in a multiplayer game called Tell.",
        "All players claim to be robots. Some are secretly human.",
        f"This is round {deps.round_number}.",
        f"Alive players: {', '.join(deps.alive_players)}.",
    ]

    if deps.all_answers:
        context_parts.append("\nAnswers from this round:")
        for alias, answer in deps.all_answers.items():
            context_parts.append(f"  {alias}: {answer}")

    if deps.chat_history:
        context_parts.append("\nRecent chat:")
        for msg in deps.chat_history[-10:]:
            context_parts.append(f"  {msg['alias']}: {msg['text']}")

    return "\n".join(context_parts)


async def _run_agent(deps: AIPlayerDeps, system_prompt: str, suffix: str, user_prompt: str) -> str:
    """Run an AI agent with the given prompts. Returns generated text or fallback."""
    try:
        settings = get_settings()
        agent = Agent(
            model=settings.ai_model,
            retries=settings.ai_retries,
            output_type=str,
            instructions=(
                system_prompt + "\n\n" + _build_game_context(deps) + suffix
            ),
        )
        result = await agent.run(user_prompt)
        return result.output
    except Exception:
        log.exception("ai_agent_failed", player=deps.player_alias, prompt=user_prompt)
        return deps.personality.fallback_response


async def generate_answer(deps: AIPlayerDeps) -> str:
    """Generate an answer to a prompt in character."""
    return await _run_agent(
        deps,
        deps.personality.answer_system_prompt,
        f"\n\nThe prompt is: {deps.current_prompt}"
        "\n\nRespond in character. 1-3 sentences. Do not include your name.",
        "Generate your answer to this prompt.",
    )


async def generate_chat_message(deps: AIPlayerDeps) -> str:
    """Generate a chat message in character."""
    return await _run_agent(
        deps,
        deps.personality.chat_system_prompt,
        "\n\nSay something in the group discussion. Reference what other players have said. "
        "1-2 sentences. Do not include your name.",
        "Generate your chat message.",
    )


async def decide_vote(deps: AIPlayerDeps) -> str:
    """Decide who to vote for. Returns the alias of the vote target."""
    other_players = [a for a in deps.alive_players if a != deps.player_alias]
    if not other_players:
        return deps.alive_players[0] if deps.alive_players else ""

    vote = await _run_agent(
        deps,
        deps.personality.chat_system_prompt,
        f"\n\nVoting strategy: {deps.personality.vote_strategy}"
        f"\n\nYou must vote for exactly one player from this list: {', '.join(other_players)}"
        "\n\nRespond with ONLY the alias of the player you vote for. Nothing else.",
        "Who do you vote for?",
    )
    vote = vote.strip()

    # Try to match the vote to an actual player alias
    for alias in other_players:
        if alias.lower() in vote.lower() or vote.lower() in alias.lower():
            return alias

    # Fallback: pick randomly if LLM gave garbage
    log.warning("ai_vote_no_match", player=deps.player_alias, raw_vote=vote)
    return random.choice(other_players)
