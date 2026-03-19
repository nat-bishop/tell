"""Game prompts — the engine of social deduction."""

from __future__ import annotations

import enum
import random

from pydantic import BaseModel


class DuelCategory(enum.StrEnum):
    STYLE_TRANSFER = "style_transfer"
    TRANSLATION = "translation"
    PATTERN = "pattern"
    GRAMMAR = "grammar"
    FORMAT_CONVERSION = "format_conversion"
    SUMMARY = "summary"
    REWRITE = "rewrite"


class DuelPrompt(BaseModel):
    text: str
    category: DuelCategory


# ---------------------------------------------------------------------------
# Brain Test challenges — competitive minigame questions
# ---------------------------------------------------------------------------


class BrainTestChallengeType(enum.StrEnum):
    ESTIMATION = "estimation"
    COMMON_KNOWLEDGE = "common_knowledge"
    TRICK = "trick"
    PATTERN = "pattern"


class BrainTestChallengeSpec(BaseModel):
    challenge_type: BrainTestChallengeType
    question: str
    options: list[str]  # exactly 4 choices
    correct_index: int  # index into options


BRAIN_TEST_CHALLENGES: list[BrainTestChallengeSpec] = [
    # --- Estimation ---
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.ESTIMATION,
        question="How many piano tuners are in London?",
        options=["About 20", "About 200", "About 2,000", "About 20,000"],
        correct_index=1,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.ESTIMATION,
        question="How many golf balls fit in a school bus?",
        options=["About 500", "About 5,000", "About 500,000", "About 5 million"],
        correct_index=2,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.ESTIMATION,
        question="How many words are in the average novel?",
        options=["About 10,000", "About 40,000", "About 80,000", "About 200,000"],
        correct_index=2,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.ESTIMATION,
        question="How many flights take off worldwide each day?",
        options=["About 1,000", "About 10,000", "About 100,000", "About 1,000,000"],
        correct_index=2,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.ESTIMATION,
        question="How many slices of pizza are eaten in the US per second?",
        options=["About 10", "About 100", "About 350", "About 1,000"],
        correct_index=2,
    ),
    # --- Common Knowledge ---
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.COMMON_KNOWLEDGE,
        question="Which planet is closest to the Sun?",
        options=["Venus", "Mercury", "Mars", "Earth"],
        correct_index=1,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.COMMON_KNOWLEDGE,
        question="What is the hardest natural substance?",
        options=["Titanium", "Quartz", "Diamond", "Graphene"],
        correct_index=2,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.COMMON_KNOWLEDGE,
        question="Which country has the most time zones?",
        options=["Russia", "USA", "France", "China"],
        correct_index=2,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.COMMON_KNOWLEDGE,
        question="What is the most spoken native language in the world?",
        options=["English", "Hindi", "Mandarin Chinese", "Spanish"],
        correct_index=2,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.COMMON_KNOWLEDGE,
        question="Which ocean is the largest?",
        options=["Atlantic", "Indian", "Arctic", "Pacific"],
        correct_index=3,
    ),
    # --- Trick Questions ---
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.TRICK,
        question=(
            "A bat and ball cost $1.10 together. "
            "The bat costs $1 more than the ball. "
            "How much is the ball?"
        ),
        options=["$0.10", "$0.05", "$0.15", "$0.01"],
        correct_index=1,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.TRICK,
        question="If you have 3 apples and take away 2, how many do you have?",
        options=["1", "2", "3", "0"],
        correct_index=1,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.TRICK,
        question="A rooster lays an egg on a roof. Which side does it roll down?",
        options=["The left side", "The right side", "Both sides", "Roosters don't lay eggs"],
        correct_index=3,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.TRICK,
        question="A farmer has 17 sheep. All but 9 run away. How many are left?",
        options=["8", "9", "17", "0"],
        correct_index=1,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.TRICK,
        question="What weighs more, a pound of feathers or a pound of steel?",
        options=["Feathers", "Steel", "They weigh the same", "Depends on gravity"],
        correct_index=2,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.TRICK,
        question="How many months have 28 days?",
        options=["1", "2", "6", "All 12"],
        correct_index=3,
    ),
    # --- Pattern ---
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.PATTERN,
        question="What comes next: 2, 6, 12, 20, ?",
        options=["24", "26", "28", "30"],
        correct_index=3,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.PATTERN,
        question="What comes next: O, T, T, F, F, S, S, ?",
        options=["T", "E", "N", "O"],
        correct_index=1,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.PATTERN,
        question="What comes next: 1, 1, 2, 3, 5, 8, ?",
        options=["11", "12", "13", "15"],
        correct_index=2,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.PATTERN,
        question="What comes next: J, F, M, A, M, J, ?",
        options=["A", "J", "S", "O"],
        correct_index=1,
    ),
    BrainTestChallengeSpec(
        challenge_type=BrainTestChallengeType.PATTERN,
        question="What comes next: 3, 6, 9, 12, ?",
        options=["14", "15", "16", "18"],
        correct_index=1,
    ),
]


def select_brain_test_challenges(
    count: int = 5,
) -> list[BrainTestChallengeSpec]:
    """Select a mix of challenges for a brain test round."""
    by_type: dict[str, list[BrainTestChallengeSpec]] = {}
    for c in BRAIN_TEST_CHALLENGES:
        by_type.setdefault(c.challenge_type, []).append(c)

    selected: list[BrainTestChallengeSpec] = []
    types = list(by_type.keys())
    random.shuffle(types)

    for t in types:
        if len(selected) >= count:
            break
        selected.append(random.choice(by_type[t]))

    remaining = [c for c in BRAIN_TEST_CHALLENGES if c not in selected]
    while len(selected) < count and remaining:
        pick = random.choice(remaining)
        remaining.remove(pick)
        selected.append(pick)

    random.shuffle(selected)
    return selected[:count]


# --- Duel prompts — AI-friendly tasks for the reverse Turing test ---

DUEL_PROMPTS: list[DuelPrompt] = [
    # --- Style Transfer ---
    DuelPrompt(
        text="Rewrite 'I had a terrible day at work' as a pirate would say it.",
        category=DuelCategory.STYLE_TRANSFER,
    ),
    DuelPrompt(
        text="Rewrite 'The meeting is at 3pm' in the style of a dramatic movie trailer narrator.",
        category=DuelCategory.STYLE_TRANSFER,
    ),
    DuelPrompt(
        text="Rewrite 'Please close the door' as Shakespeare would say it.",
        category=DuelCategory.STYLE_TRANSFER,
    ),
    DuelPrompt(
        text="Rewrite 'I'm hungry' as a Victorian gentleman would express it.",
        category=DuelCategory.STYLE_TRANSFER,
    ),
    DuelPrompt(
        text="Rewrite 'The wifi is down' as a breaking news headline.",
        category=DuelCategory.STYLE_TRANSFER,
    ),
    # --- Translation ---
    DuelPrompt(
        text="Translate to French: 'The meeting has been rescheduled to Thursday.'",
        category=DuelCategory.TRANSLATION,
    ),
    DuelPrompt(
        text="Translate to Spanish: 'Could you please pass me the salt?'",
        category=DuelCategory.TRANSLATION,
    ),
    DuelPrompt(
        text="Translate to German: 'I would like a table for two, please.'",
        category=DuelCategory.TRANSLATION,
    ),
    DuelPrompt(
        text="Translate to Italian: 'The train departs at half past nine.'",
        category=DuelCategory.TRANSLATION,
    ),
    DuelPrompt(
        text="Translate to Japanese (romanized): 'Thank you for your help today.'",
        category=DuelCategory.TRANSLATION,
    ),
    # --- Pattern ---
    DuelPrompt(
        text="Complete the sequence: A, C, E, G, ___",
        category=DuelCategory.PATTERN,
    ),
    DuelPrompt(
        text="Complete the sequence: 2, 6, 18, 54, ___",
        category=DuelCategory.PATTERN,
    ),
    DuelPrompt(
        text="Complete the sequence: red, orange, yellow, green, ___",
        category=DuelCategory.PATTERN,
    ),
    DuelPrompt(
        text="Complete the analogy: hot is to cold as day is to ___",
        category=DuelCategory.PATTERN,
    ),
    DuelPrompt(
        text="Complete the sequence: 1, 4, 9, 16, ___",
        category=DuelCategory.PATTERN,
    ),
    # --- Grammar ---
    DuelPrompt(
        text="Fix the grammar: 'Me and him went to the store yesterday, we buyed milk.'",
        category=DuelCategory.GRAMMAR,
    ),
    DuelPrompt(
        text="Fix the grammar: 'Their going to there house over they're.'",
        category=DuelCategory.GRAMMAR,
    ),
    DuelPrompt(
        text="Fix the grammar: 'The datas shows that less people is coming.'",
        category=DuelCategory.GRAMMAR,
    ),
    DuelPrompt(
        text="Fix the grammar: 'Between you and I, she don't know nothing about it.'",
        category=DuelCategory.GRAMMAR,
    ),
    DuelPrompt(
        text="Fix the grammar: 'Him and me seen the movie what was real good.'",
        category=DuelCategory.GRAMMAR,
    ),
    # --- Format Conversion ---
    DuelPrompt(
        text="Rewrite as a haiku: 'The sunset was beautiful over the calm ocean.'",
        category=DuelCategory.FORMAT_CONVERSION,
    ),
    DuelPrompt(
        text="Rewrite as a limerick: 'My cat always sleeps on my keyboard.'",
        category=DuelCategory.FORMAT_CONVERSION,
    ),
    DuelPrompt(
        text="Rewrite as bullet points: 'We need to buy eggs, milk, and bread, "
        "then pick up the dry cleaning and drop off the package.'",
        category=DuelCategory.FORMAT_CONVERSION,
    ),
    DuelPrompt(
        text="Rewrite as a single sentence: 'It was raining. The streets were empty. "
        "Nobody wanted to go outside.'",
        category=DuelCategory.FORMAT_CONVERSION,
    ),
    DuelPrompt(
        text="Rewrite as a telegram (short, punchy): 'I arrived safely at the hotel "
        "and will call you tomorrow morning.'",
        category=DuelCategory.FORMAT_CONVERSION,
    ),
    # --- Summary ---
    DuelPrompt(
        text="Summarize in one sentence: 'The Industrial Revolution began in Britain in the late "
        "18th century. It transformed manufacturing from hand production to machine processes. "
        "This shift fundamentally changed society, economics, and daily life.'",
        category=DuelCategory.SUMMARY,
    ),
    DuelPrompt(
        text="Summarize in one sentence: 'Photosynthesis is the process by which plants convert "
        "sunlight into energy. They absorb carbon dioxide and water, then release oxygen. "
        "This process is essential for life on Earth.'",
        category=DuelCategory.SUMMARY,
    ),
    DuelPrompt(
        text="Summarize in one sentence: 'The Mona Lisa was painted by Leonardo da Vinci in the "
        "early 16th century. It is famous for the subject's enigmatic smile. The painting hangs "
        "in the Louvre Museum in Paris.'",
        category=DuelCategory.SUMMARY,
    ),
    DuelPrompt(
        text="Summarize in one sentence: 'Sleep is crucial for memory consolidation. During deep "
        "sleep, the brain processes and stores information from the day. Lack of sleep impairs "
        "cognitive function and decision-making.'",
        category=DuelCategory.SUMMARY,
    ),
    DuelPrompt(
        text="Summarize in one sentence: 'The Great Wall of China stretches over 13,000 miles. "
        "It was built over many centuries by multiple dynasties. Its original purpose was to "
        "protect against invasions from the north.'",
        category=DuelCategory.SUMMARY,
    ),
    # --- Rewrite ---
    DuelPrompt(
        text="Make this sentence formal: 'yo can we push the meeting back lol'",
        category=DuelCategory.REWRITE,
    ),
    DuelPrompt(
        text="Make this sentence casual: 'I would like to inquire about the availability "
        "of the aforementioned product.'",
        category=DuelCategory.REWRITE,
    ),
    DuelPrompt(
        text="Make this shorter without losing meaning: 'In my personal opinion, I believe "
        "that the current situation is not at all ideal and could be significantly improved.'",
        category=DuelCategory.REWRITE,
    ),
    DuelPrompt(
        text="Make this sound more polite: 'Send me the report by Friday.'",
        category=DuelCategory.REWRITE,
    ),
    DuelPrompt(
        text="Make this sound more confident: 'I think maybe this could possibly work, "
        "but I'm not really sure about it.'",
        category=DuelCategory.REWRITE,
    ),
]


def select_duel_prompt(
    used_indices: list[int],
    last_category: str | None,
) -> tuple[int, DuelPrompt]:
    """Select next duel prompt. Rules: no repeats, no same-category back-to-back."""
    valid = []
    for i, prompt in enumerate(DUEL_PROMPTS):
        if i in used_indices:
            continue
        if last_category and prompt.category.value == last_category:
            continue
        valid.append((i, prompt))

    if not valid:
        # Fallback: relax the category constraint
        valid = [(i, p) for i, p in enumerate(DUEL_PROMPTS) if i not in used_indices]

    if not valid:
        # All prompts used — reset
        valid = list(enumerate(DUEL_PROMPTS))

    idx, prompt = random.choice(valid)
    return idx, prompt
