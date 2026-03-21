"""Game prompts — the engine of social deduction."""

from __future__ import annotations

import enum
import random
from collections.abc import Callable

from pydantic import BaseModel


def _select_diverse[T](items: list[T], count: int, key: Callable[[T], str]) -> list[T]:
    """Select items with category diversity. Pick one per group first, fill randomly."""
    by_group: dict[str, list[T]] = {}
    for item in items:
        by_group.setdefault(key(item), []).append(item)

    selected: list[T] = []
    groups = list(by_group.keys())
    random.shuffle(groups)

    for g in groups:
        if len(selected) >= count:
            break
        selected.append(random.choice(by_group[g]))

    remaining = [x for x in items if x not in selected]
    while len(selected) < count and remaining:
        pick = random.choice(remaining)
        remaining.remove(pick)
        selected.append(pick)

    random.shuffle(selected)
    return selected[:count]


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
    return _select_diverse(BRAIN_TEST_CHALLENGES, count, lambda c: c.challenge_type)


# ---------------------------------------------------------------------------
# Wager questions — numerical estimation for the wager round
# ---------------------------------------------------------------------------


class WagerCategory(enum.StrEnum):
    GEOGRAPHY = "geography"
    SCIENCE = "science"
    HISTORY = "history"
    POP_CULTURE = "pop_culture"
    ECONOMICS = "economics"
    NATURE = "nature"


class WagerQuestionSpec(BaseModel):
    question: str
    correct_answer: int
    range_min: int
    range_max: int
    unit: str
    category: WagerCategory


WAGER_QUESTIONS: list[WagerQuestionSpec] = [
    # --- Geography ---
    WagerQuestionSpec(
        question="How many countries are in Africa?",
        correct_answer=54,
        range_min=10,
        range_max=100,
        unit="countries",
        category=WagerCategory.GEOGRAPHY,
    ),
    WagerQuestionSpec(
        question="How deep is the Mariana Trench in meters?",
        correct_answer=10994,
        range_min=1000,
        range_max=20000,
        unit="meters",
        category=WagerCategory.GEOGRAPHY,
    ),
    WagerQuestionSpec(
        question="How many islands make up the Philippines?",
        correct_answer=7641,
        range_min=100,
        range_max=15000,
        unit="islands",
        category=WagerCategory.GEOGRAPHY,
    ),
    WagerQuestionSpec(
        question="What percentage of Earth's surface is covered by water?",
        correct_answer=71,
        range_min=30,
        range_max=95,
        unit="percent",
        category=WagerCategory.GEOGRAPHY,
    ),
    # --- Science ---
    WagerQuestionSpec(
        question="How many bones are in the adult human body?",
        correct_answer=206,
        range_min=50,
        range_max=500,
        unit="bones",
        category=WagerCategory.SCIENCE,
    ),
    WagerQuestionSpec(
        question="What percentage of the ocean floor has been mapped?",
        correct_answer=5,
        range_min=0,
        range_max=100,
        unit="percent",
        category=WagerCategory.SCIENCE,
    ),
    WagerQuestionSpec(
        question="How many taste buds does the average human tongue have?",
        correct_answer=10000,
        range_min=100,
        range_max=50000,
        unit="taste buds",
        category=WagerCategory.SCIENCE,
    ),
    WagerQuestionSpec(
        question="How long does light from the Sun take to reach Earth in minutes?",
        correct_answer=8,
        range_min=1,
        range_max=60,
        unit="minutes",
        category=WagerCategory.SCIENCE,
    ),
    # --- History ---
    WagerQuestionSpec(
        question="How many years did the Hundred Years' War last?",
        correct_answer=116,
        range_min=50,
        range_max=200,
        unit="years",
        category=WagerCategory.HISTORY,
    ),
    WagerQuestionSpec(
        question="How many paintings did Van Gogh sell during his lifetime?",
        correct_answer=1,
        range_min=0,
        range_max=100,
        unit="paintings",
        category=WagerCategory.HISTORY,
    ),
    WagerQuestionSpec(
        question="In what year was the first email sent?",
        correct_answer=1971,
        range_min=1950,
        range_max=2000,
        unit="year",
        category=WagerCategory.HISTORY,
    ),
    WagerQuestionSpec(
        question="How many years did it take to build the Great Wall of China?",
        correct_answer=2000,
        range_min=10,
        range_max=5000,
        unit="years",
        category=WagerCategory.HISTORY,
    ),
    # --- Pop Culture ---
    WagerQuestionSpec(
        question="How many episodes of The Simpsons have aired?",
        correct_answer=768,
        range_min=100,
        range_max=1500,
        unit="episodes",
        category=WagerCategory.POP_CULTURE,
    ),
    WagerQuestionSpec(
        question="How many words are in the Harry Potter series?",
        correct_answer=1084170,
        range_min=100000,
        range_max=3000000,
        unit="words",
        category=WagerCategory.POP_CULTURE,
    ),
    WagerQuestionSpec(
        question="How many number-one Billboard hits did The Beatles have?",
        correct_answer=20,
        range_min=1,
        range_max=50,
        unit="hits",
        category=WagerCategory.POP_CULTURE,
    ),
    WagerQuestionSpec(
        question="How many keys are on a standard piano?",
        correct_answer=88,
        range_min=20,
        range_max=200,
        unit="keys",
        category=WagerCategory.POP_CULTURE,
    ),
    # --- Economics ---
    WagerQuestionSpec(
        question="How many McDonald's restaurants are in Japan?",
        correct_answer=2975,
        range_min=0,
        range_max=20000,
        unit="restaurants",
        category=WagerCategory.ECONOMICS,
    ),
    WagerQuestionSpec(
        question="How many shipping containers are on the largest cargo ship?",
        correct_answer=24000,
        range_min=1000,
        range_max=50000,
        unit="containers",
        category=WagerCategory.ECONOMICS,
    ),
    WagerQuestionSpec(
        question="How many Starbucks stores are there worldwide?",
        correct_answer=38000,
        range_min=5000,
        range_max=80000,
        unit="stores",
        category=WagerCategory.ECONOMICS,
    ),
    WagerQuestionSpec(
        question="How many languages are spoken in the world?",
        correct_answer=7168,
        range_min=100,
        range_max=15000,
        unit="languages",
        category=WagerCategory.ECONOMICS,
    ),
    # --- Nature ---
    WagerQuestionSpec(
        question="How many bones does a shark have?",
        correct_answer=0,
        range_min=0,
        range_max=500,
        unit="bones",
        category=WagerCategory.NATURE,
    ),
    WagerQuestionSpec(
        question="How many hearts does an octopus have?",
        correct_answer=3,
        range_min=1,
        range_max=10,
        unit="hearts",
        category=WagerCategory.NATURE,
    ),
    WagerQuestionSpec(
        question="How many miles can an Arctic tern migrate in a year?",
        correct_answer=44000,
        range_min=1000,
        range_max=100000,
        unit="miles",
        category=WagerCategory.NATURE,
    ),
    WagerQuestionSpec(
        question="How many species of beetles have been identified?",
        correct_answer=400000,
        range_min=10000,
        range_max=1000000,
        unit="species",
        category=WagerCategory.NATURE,
    ),
    WagerQuestionSpec(
        question="How many teeth does a garden snail have?",
        correct_answer=14000,
        range_min=0,
        range_max=50000,
        unit="teeth",
        category=WagerCategory.NATURE,
    ),
]


def select_wager_questions(
    count: int = 3,
) -> list[WagerQuestionSpec]:
    """Select a category-diverse mix of wager questions."""
    return _select_diverse(WAGER_QUESTIONS, count, lambda q: q.category)


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


# ---------------------------------------------------------------------------
# Signal constraints + phrases
# ---------------------------------------------------------------------------


SIGNAL_CONSTRAINTS: list[str] = [
    "Describe the phrase using only questions. No statements allowed.",
    "Describe the phrase without using any nouns.",
    "Describe the opposite of the phrase. Everything is reversed.",
    "Describe the phrase using exactly five words, separated by periods.",
    "Describe the phrase as if it were a cooking recipe.",
    "Describe the phrase as a breaking news headline.",
    "Describe the phrase as a dramatic movie trailer narrator would.",
    "Describe the phrase as a formal complaint letter.",
    "Describe the phrase as the opening of a children's book.",
    "Describe the phrase as a casual text message to a friend. Use abbreviations.",
    "Describe the phrase as a nature documentary narrator would.",
    "Describe the phrase as a set of step-by-step instructions.",
    "Describe the phrase as a short poem (2-4 lines).",
    "Describe the phrase as live sports commentary.",
    "Describe the phrase as quietly and mysteriously as possible.",
]


SIGNAL_PHRASES: list[str] = [
    "a dog chasing a squirrel",
    "forgetting someone's name at a party",
    "burning dinner",
    "a cat knocking things off a table",
    "getting stuck in an elevator",
    "finding money in your old jacket",
    "a kid refusing to eat vegetables",
    "being the last one picked for a team",
    "waking up five minutes before your alarm",
    "stepping on a Lego barefoot",
    "trying to parallel park while people watch",
    "realizing you left your phone at home",
    "a bird stealing food from your plate",
    "getting caught in the rain without an umbrella",
    "the first sip of coffee in the morning",
    "a toddler discovering bubbles",
    "your WiFi cutting out during a video call",
    "finding the last slice of pizza",
    "accidentally waving back at a stranger",
    "a squirrel raiding a bird feeder",
    "trying to stay awake during a boring meeting",
    "the moment you realize the milk is expired",
    "a dog meeting its reflection for the first time",
    "losing your keys and finding them in your hand",
    "someone singing in the shower",
    "running to catch a bus and missing it",
    "a cat sitting in a box that's too small",
    "getting a paper cut",
    "the awkward silence in an elevator with strangers",
    "watching someone trip and pretending you didn't see",
    "a kid discovering snow for the first time",
    "burning your tongue on hot food",
    "trying to open a pickle jar",
    "a raccoon going through garbage cans",
    "falling asleep on public transport and missing your stop",
    "the relief of finding a public restroom",
    "a baby laughing at peek-a-boo",
    "your favorite song coming on the radio",
    "stepping in a puddle with fresh socks",
    "trying to fold a fitted sheet",
]


def select_signal_constraint(used_indices: list[int]) -> tuple[int, str]:
    """Select a signal constraint that hasn't been used yet."""
    valid = [(i, c) for i, c in enumerate(SIGNAL_CONSTRAINTS) if i not in used_indices]
    if not valid:
        valid = list(enumerate(SIGNAL_CONSTRAINTS))
    idx, constraint = random.choice(valid)
    return idx, constraint


def select_signal_phrases(count: int, used_indices: list[int]) -> list[tuple[int, str]]:
    """Select unique signal phrases that haven't been used yet."""
    valid = [(i, p) for i, p in enumerate(SIGNAL_PHRASES) if i not in used_indices]
    if len(valid) < count:
        # Not enough unused — reset and pick from all
        valid = list(enumerate(SIGNAL_PHRASES))
    return random.sample(valid, min(count, len(valid)))


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
