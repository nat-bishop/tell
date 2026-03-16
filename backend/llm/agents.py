"""AI player agent — generates answers, questions, responses,
votes, nominations, synthesis, and verdicts."""

from __future__ import annotations

import random
from dataclasses import dataclass

import structlog
from pydantic_ai import Agent

from backend.api.deps import get_settings
from backend.llm.personalities import Personality

log = structlog.get_logger(__name__)


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


def _build_game_context(deps: AIPlayerDeps) -> str:
    """Build game context string for the system prompt."""
    context_parts = [
        f"You are {deps.player_alias} in a multiplayer game called Tell.",
        "All players claim to be robots. Some are secretly human.",
        f"This is round {deps.round_number}. Round type: {deps.round_type}.",
        f"Alive players: {', '.join(deps.alive_players)}.",
    ]

    if deps.all_answers:
        context_parts.append("\nAnswers from this round:")
        for alias, answer in deps.all_answers.items():
            context_parts.append(f"  {alias}: {answer}")

    if deps.questions:
        context_parts.append("\nQuestions and responses this round:")
        for q in deps.questions:
            line = f'  {q["target_alias"]} was asked: "{q["question"]}"'
            if q.get("response"):
                line += f' → responded: "{q["response"]}"'
            context_parts.append(line)

    if deps.synthesis:
        context_parts.append(f"\nSynthesized question: {deps.synthesis}")

    if deps.hot_seat_response:
        context_parts.append(f"\n{deps.nominated_alias} responded: {deps.hot_seat_response}")

    return "\n".join(context_parts)


async def _run_agent(deps: AIPlayerDeps, system_prompt: str, suffix: str, user_prompt: str) -> str:
    """Run an AI agent with the given prompts. Returns generated text or fallback."""
    settings = get_settings()
    action = user_prompt.split()[0].lower().rstrip(".")
    log.info("llm_call_start", player=deps.player_alias, action=action, model=settings.ai_model)
    try:
        agent = Agent(
            model=settings.ai_model,
            retries=settings.ai_retries,
            output_type=str,
            instructions=(system_prompt + "\n\n" + _build_game_context(deps) + suffix),
        )
        result = await agent.run(user_prompt)
        log.info(
            "llm_call_done",
            player=deps.player_alias,
            action=action,
            output_len=len(result.output),
        )
        return result.output
    except Exception:
        log.exception("ai_agent_failed", player=deps.player_alias, action=action)
        return deps.personality.fallback_response


async def _run_system_agent(
    system_prompt: str, user_prompt: str, timeout: float = 5.0
) -> str | None:
    """Run a system-level LLM call (not personality-based). Returns None on failure."""
    settings = get_settings()
    log.info("llm_system_call_start", model=settings.ai_model)
    try:
        import asyncio

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


async def generate_answer(deps: AIPlayerDeps) -> str:
    """Generate an answer to a prompt in character."""
    return await _run_agent(
        deps,
        deps.personality.answer_system_prompt,
        f"\n\nThe prompt is: {deps.current_prompt}"
        "\n\nRespond in character. 1-3 sentences. Do not include your name.",
        "Generate your answer to this prompt.",
    )


async def generate_question(deps: AIPlayerDeps) -> str:
    """Generate a follow-up question about another player's answer."""
    target_alias = deps.assigned_target or deps.nominated_alias or "unknown"
    target_answer = deps.all_answers.get(target_alias, "")

    system_prompt = (
        f"You are {deps.player_alias}, a robot unit in a game called Tell. All players claim to be "
        "robots, but some are secretly human. Your job is to ask a follow-up question that might "
        "reveal whether another player is human.\n\n"
        f"{deps.personality.question_style}"
    )

    suffix = (
        f'\n\nThe prompt was: "{deps.current_prompt}"'
        f'\n{target_alias} answered: "{target_answer}"'
        "\n\nWrite ONE short follow-up question (1 sentence, max 120 characters). "
        "Probe for emotional authenticity, suspicious specificity, or logical gaps. "
        "Your question is anonymous — they won't know who asked."
        "\n\nRespond with ONLY the question."
    )

    return await _run_agent(deps, system_prompt, suffix, "Generate your question.")


async def generate_question_response(deps: AIPlayerDeps, question: str) -> str:
    """Respond to an anonymous question about your answer."""
    system_prompt = (
        f"You are {deps.player_alias}, a robot unit in Tell. "
        "You received a follow-up question about your answer. "
        "Respond in character — you are a robot, act like one.\n\n"
        f"{deps.personality.answer_system_prompt}"
    )

    suffix = (
        f'\n\nThe prompt was: "{deps.current_prompt}"'
        f'\nYour answer was: "{deps.my_answer}"'
        f'\nQuestion you received: "{question}"'
        "\n\nWrite a brief response (1-2 sentences). Elaborate on or defend your answer naturally. "
        "Robots don't get defensive or emotional — they clarify and compute."
        "\n\nRespond with ONLY your response."
    )

    return await _run_agent(deps, system_prompt, suffix, "Generate your response.")


async def generate_nomination(deps: AIPlayerDeps) -> str:
    """Pick a player to nominate for the hot seat (Interrogation)."""
    other_players = [a for a in deps.alive_players if a != deps.player_alias]
    if not other_players:
        return deps.alive_players[0] if deps.alive_players else ""

    system_prompt = (
        f"You are {deps.player_alias} in a game called Tell. Choose one player to put on the "
        "hot seat for interrogation. Pick the player whose answer is most worth scrutinizing.\n\n"
        f"{deps.personality.vote_strategy}"
    )

    answers_text = "\n".join(
        f"  {alias}: {answer}"
        for alias, answer in deps.all_answers.items()
        if alias != deps.player_alias
    )

    suffix = (
        f"\n\nAnswers this round:\n{answers_text}"
        f'\n\nRespond with ONLY the alias of the player you nominate (e.g., "UNIT-7").'
    )

    nomination = await _run_agent(deps, system_prompt, suffix, "Who do you nominate?")
    nomination = nomination.strip()

    # Fuzzy match
    for alias in other_players:
        if alias.lower() in nomination.lower() or nomination.lower() in alias.lower():
            return alias

    log.warning("ai_nomination_no_match", player=deps.player_alias, raw=nomination)
    return random.choice(other_players)


async def decide_vote(deps: AIPlayerDeps) -> list[str]:
    """Decide who to vote for. Returns list of target aliases (up to max_votes)."""
    other_players = [a for a in deps.alive_players if a != deps.player_alias]
    if not other_players:
        return []

    from backend.services.game_logic import max_votes_for_player

    max_v = max_votes_for_player(len(deps.alive_players))

    system_prompt = (
        f"You are {deps.player_alias} in a game called Tell. Time to vote. "
        f"Choose up to {max_v} players you suspect of being human.\n\n"
        f"{deps.personality.vote_strategy}"
    )

    suffix = (
        f"\n\nPlayers you can vote for: {', '.join(other_players)}"
        f"\n\nRespond with {max_v} aliases, one per line. Nothing else. Example:\nUNIT-7\nBOT-42"
    )

    vote_text = await _run_agent(deps, system_prompt, suffix, "Who do you vote for?")

    # Parse multi-line output
    lines = [line.strip() for line in vote_text.strip().split("\n") if line.strip()]
    matched: list[str] = []
    for line in lines:
        for alias in other_players:
            if alias.lower() in line.lower() or line.lower() in alias.lower():
                if alias not in matched:
                    matched.append(alias)
                break

    # Pad with random if needed
    remaining = [a for a in other_players if a not in matched]
    while len(matched) < max_v and remaining:
        pick = random.choice(remaining)
        matched.append(pick)
        remaining.remove(pick)

    # Trim to max
    return matched[:max_v]


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
