"""AI player agent — generates answers, chat messages, and vote decisions."""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from pydantic_ai import Agent

from backend.config import Settings
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


def _get_model() -> str:
    """Get the AI model from settings."""
    settings = Settings()
    return settings.ai_model


def _get_retries() -> int:
    settings = Settings()
    return settings.ai_retries


async def generate_answer(deps: AIPlayerDeps) -> str:
    """Generate an answer to a prompt in character."""
    try:
        agent = Agent(
            model=_get_model(),
            retries=_get_retries(),
            output_type=str,
            instructions=(
                deps.personality.answer_system_prompt
                + "\n\n"
                + _build_game_context(deps)
                + f"\n\nThe prompt is: {deps.current_prompt}"
                + "\n\nRespond in character. 1-3 sentences. Do not include your name."
            ),
        )
        result = await agent.run("Generate your answer to this prompt.")
        return result.output
    except Exception:
        log.exception("ai_generate_answer_failed", player=deps.player_alias)
        return deps.personality.fallback_response


async def generate_chat_message(deps: AIPlayerDeps) -> str:
    """Generate a chat message in character."""
    try:
        agent = Agent(
            model=_get_model(),
            retries=_get_retries(),
            output_type=str,
            instructions=(
                deps.personality.chat_system_prompt
                + "\n\n"
                + _build_game_context(deps)
                + "\n\nSay something in the group discussion. Reference what other players have said. "
                + "1-2 sentences. Do not include your name."
            ),
        )
        result = await agent.run("Generate your chat message.")
        return result.output
    except Exception:
        log.exception("ai_generate_chat_failed", player=deps.player_alias)
        return deps.personality.fallback_response


async def decide_vote(deps: AIPlayerDeps) -> str:
    """Decide who to vote for. Returns the alias of the vote target."""
    try:
        other_players = [a for a in deps.alive_players if a != deps.player_alias]
        if not other_players:
            return deps.alive_players[0] if deps.alive_players else ""

        agent = Agent(
            model=_get_model(),
            retries=_get_retries(),
            output_type=str,
            instructions=(
                deps.personality.chat_system_prompt
                + "\n\n"
                + _build_game_context(deps)
                + f"\n\nVoting strategy: {deps.personality.vote_strategy}"
                + f"\n\nYou must vote for exactly one player from this list: {', '.join(other_players)}"
                + "\n\nRespond with ONLY the alias of the player you vote for. Nothing else."
            ),
        )
        result = await agent.run("Who do you vote for?")
        vote = result.output.strip()

        # Try to match the vote to an actual player alias
        for alias in other_players:
            if alias.lower() in vote.lower() or vote.lower() in alias.lower():
                return alias

        # Fallback: pick randomly if LLM gave garbage
        log.warning("ai_vote_no_match", player=deps.player_alias, raw_vote=vote)
        import random
        return random.choice(other_players)

    except Exception:
        log.exception("ai_decide_vote_failed", player=deps.player_alias)
        import random
        other_players = [a for a in deps.alive_players if a != deps.player_alias]
        return random.choice(other_players) if other_players else deps.player_alias
