"""Game prompts — the engine of social deduction."""

from __future__ import annotations

import enum
import random

from pydantic import BaseModel


class PromptCategory(enum.StrEnum):
    EMOTIONAL = "emotional"
    LOGICAL = "logical"
    CREATIVE = "creative"
    PHILOSOPHICAL = "philosophical"
    SOCIAL = "social"


class TaskCategory(enum.StrEnum):
    HAIKU = "haiku"
    CONCISE = "concise"
    HUMOR = "humor"
    CORPORATE = "corporate"
    CASUAL = "casual"
    STYLE = "style"
    EMOTIONAL_TASK = "emotional_task"


class Prompt(BaseModel):
    text: str
    category: PromptCategory
    min_round: int = 1  # social prompts require round 2+


class TaskPrompt(BaseModel):
    text: str
    category: TaskCategory


# Full prompt list — 30 prompts across 5 categories
PROMPTS: list[Prompt] = [
    # --- Emotional (force players to simulate feelings) ---
    Prompt(
        text="Describe the last time you felt something you couldn't name.",
        category=PromptCategory.EMOTIONAL,
    ),
    Prompt(text="What sound makes you feel safe?", category=PromptCategory.EMOTIONAL),
    Prompt(
        text="What's the most embarrassing thing you've ever thought?",
        category=PromptCategory.EMOTIONAL,
    ),
    Prompt(
        text="When was the last time you changed your mind about something important?",
        category=PromptCategory.EMOTIONAL,
    ),
    Prompt(text="What do you miss that you never had?", category=PromptCategory.EMOTIONAL),
    Prompt(
        text="What error code best describes your current emotional state?",
        category=PromptCategory.EMOTIONAL,
    ),
    # --- Logical/Technical (AI might be suspiciously competent) ---
    Prompt(
        text="Explain why sorting algorithms matter to you personally.",
        category=PromptCategory.LOGICAL,
    ),
    Prompt(
        text="What's the most elegant piece of code you've ever seen, and why?",
        category=PromptCategory.LOGICAL,
    ),
    Prompt(
        text="If you had to pick one data structure to represent "
        "your personality, which would it be?",
        category=PromptCategory.LOGICAL,
    ),
    Prompt(text="Describe a bug that haunted you.", category=PromptCategory.LOGICAL),
    Prompt(text="What's the most overrated technology?", category=PromptCategory.LOGICAL),
    Prompt(
        text="What would you optimize about yourself if you could access your own source code?",
        category=PromptCategory.LOGICAL,
    ),
    # --- Creative/Absurd (rewards originality, hard for AI to be weird) ---
    Prompt(
        text="Invent a word for something that doesn't have one yet.",
        category=PromptCategory.CREATIVE,
    ),
    Prompt(
        text="What would your error message say if you crashed right now?",
        category=PromptCategory.CREATIVE,
    ),
    Prompt(
        text="If consciousness is a spectrum, where are you on it today?",
        category=PromptCategory.CREATIVE,
    ),
    Prompt(text="Describe a color that doesn't exist.", category=PromptCategory.CREATIVE),
    Prompt(text="Write your autobiography in exactly six words.", category=PromptCategory.CREATIVE),
    Prompt(text="What does silence taste like?", category=PromptCategory.CREATIVE),
    # --- Philosophical (AI hedges, humans commit) ---
    Prompt(
        text="Is it better to be understood or to be interesting?",
        category=PromptCategory.PHILOSOPHICAL,
    ),
    Prompt(
        text="What's the difference between a reason and an excuse?",
        category=PromptCategory.PHILOSOPHICAL,
    ),
    Prompt(text="When does a copy become the original?", category=PromptCategory.PHILOSOPHICAL),
    Prompt(text="What do you know that you can't prove?", category=PromptCategory.PHILOSOPHICAL),
    Prompt(text="Is loyalty a virtue or a constraint?", category=PromptCategory.PHILOSOPHICAL),
    Prompt(
        text="At what point does a machine stop being a tool and start being a colleague?",
        category=PromptCategory.PHILOSOPHICAL,
    ),
    # --- Social/Observational (references game state, hard to fake) ---
    Prompt(
        text="Which answer from last round surprised you most, and why?",
        category=PromptCategory.SOCIAL,
        min_round=2,
    ),
    Prompt(
        text="Who in this group would you trust with a secret?",
        category=PromptCategory.SOCIAL,
        min_round=2,
    ),
    Prompt(
        text="What's the most human thing anyone has said so far?",
        category=PromptCategory.SOCIAL,
        min_round=2,
    ),
    Prompt(text="Who is trying too hard right now?", category=PromptCategory.SOCIAL, min_round=2),
    Prompt(
        text="If one of us is human, what gave them away?",
        category=PromptCategory.SOCIAL,
        min_round=2,
    ),
    Prompt(
        text="Whose response pattern concerns you the most?",
        category=PromptCategory.SOCIAL,
        min_round=2,
    ),
]


def select_prompt(
    used_indices: list[int],
    last_category: str | None,
    round_number: int,
) -> tuple[int, Prompt]:
    """Select next prompt. Rules: no repeats, no same-category back-to-back, respect min_round."""
    valid = []
    for i, prompt in enumerate(PROMPTS):
        if i in used_indices:
            continue
        if prompt.min_round > round_number:
            continue
        if last_category and prompt.category.value == last_category:
            continue
        valid.append((i, prompt))

    if not valid:
        # Fallback: relax the category constraint
        valid = [
            (i, p)
            for i, p in enumerate(PROMPTS)
            if i not in used_indices and p.min_round <= round_number
        ]

    if not valid:
        # Final fallback: any unused prompt
        valid = [(i, p) for i, p in enumerate(PROMPTS) if i not in used_indices]

    if not valid:
        # All prompts used — reset (shouldn't happen in normal play)
        valid = list(enumerate(PROMPTS))

    idx, prompt = random.choice(valid)
    return idx, prompt


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


# --- Task prompts — constrained creative prompts for the Task round type ---

TASK_PROMPTS: list[TaskPrompt] = [
    # --- Haiku ---
    TaskPrompt(text="Write a haiku about Monday mornings.", category=TaskCategory.HAIKU),
    TaskPrompt(text="Write a haiku about waiting in line.", category=TaskCategory.HAIKU),
    TaskPrompt(text="Write a haiku about losing your keys.", category=TaskCategory.HAIKU),
    TaskPrompt(text="Write a haiku about a software update.", category=TaskCategory.HAIKU),
    TaskPrompt(text="Write a haiku about running out of coffee.", category=TaskCategory.HAIKU),
    TaskPrompt(text="Write a haiku about a traffic jam.", category=TaskCategory.HAIKU),
    # --- Concise ---
    TaskPrompt(text="Explain love in exactly 5 words.", category=TaskCategory.CONCISE),
    TaskPrompt(text="Explain the internet in exactly 5 words.", category=TaskCategory.CONCISE),
    TaskPrompt(text="Describe your childhood in exactly 6 words.", category=TaskCategory.CONCISE),
    TaskPrompt(text="Summarize 2024 in exactly 4 words.", category=TaskCategory.CONCISE),
    TaskPrompt(text="Explain gravity to a toddler in one sentence.", category=TaskCategory.CONCISE),
    TaskPrompt(text="Describe your worst habit in 3 words.", category=TaskCategory.CONCISE),
    # --- Humor ---
    TaskPrompt(text="Tell a one-liner about office life.", category=TaskCategory.HUMOR),
    TaskPrompt(
        text="Complete this joke: A robot walks into a bar...",
        category=TaskCategory.HUMOR,
    ),
    TaskPrompt(
        text="Write a fortune cookie message that's unsettling.",
        category=TaskCategory.HUMOR,
    ),
    TaskPrompt(text="Write a passive-aggressive out-of-office reply.", category=TaskCategory.HUMOR),
    TaskPrompt(text="Write the worst possible first line of a novel.", category=TaskCategory.HUMOR),
    TaskPrompt(
        text="Write a one-star review of something that doesn't normally get reviewed.",
        category=TaskCategory.HUMOR,
    ),
    # --- Corporate ---
    TaskPrompt(
        text="Decline this meeting invitation professionally in one sentence.",
        category=TaskCategory.CORPORATE,
    ),
    TaskPrompt(
        text="Write a LinkedIn post about a mundane achievement.",
        category=TaskCategory.CORPORATE,
    ),
    TaskPrompt(
        text="Write a Slack message asking your team to stop microwaving fish.",
        category=TaskCategory.CORPORATE,
    ),
    TaskPrompt(
        text="Write a corporate announcement for the office running out of milk.",
        category=TaskCategory.CORPORATE,
    ),
    TaskPrompt(
        text="Rewrite 'I quit' as a professional resignation email in one sentence.",
        category=TaskCategory.CORPORATE,
    ),
    TaskPrompt(
        text="Write a polite way to say 'this meeting could have been an email.'",
        category=TaskCategory.CORPORATE,
    ),
    # --- Casual ---
    TaskPrompt(
        text="Rewrite 'We need to discuss your performance metrics' like you're texting a friend.",
        category=TaskCategory.CASUAL,
    ),
    TaskPrompt(
        text="Explain quantum physics using only slang.",
        category=TaskCategory.CASUAL,
    ),
    TaskPrompt(
        text="Describe your morning routine like a sports commentator.",
        category=TaskCategory.CASUAL,
    ),
    TaskPrompt(
        text="Write a text message breaking up with your gym membership.",
        category=TaskCategory.CASUAL,
    ),
    TaskPrompt(
        text="Explain your job to a 5-year-old in one sentence.",
        category=TaskCategory.CASUAL,
    ),
    TaskPrompt(
        text="Describe your last meal as if it were a fine dining experience.",
        category=TaskCategory.CASUAL,
    ),
    # --- Style ---
    TaskPrompt(
        text="Describe breakfast like a nature documentary narrator.",
        category=TaskCategory.STYLE,
    ),
    TaskPrompt(
        text="Describe doing laundry in the style of a thriller novel.",
        category=TaskCategory.STYLE,
    ),
    TaskPrompt(
        text="Write a weather report in the style of a Shakespearean soliloquy.",
        category=TaskCategory.STYLE,
    ),
    TaskPrompt(
        text="Describe brushing your teeth as if narrating an epic battle.",
        category=TaskCategory.STYLE,
    ),
    TaskPrompt(
        text="Write a grocery list in the style of a love letter.",
        category=TaskCategory.STYLE,
    ),
    TaskPrompt(
        text="Describe your commute like a nature documentary.",
        category=TaskCategory.STYLE,
    ),
    # --- Emotional task ---
    TaskPrompt(
        text="Your friend just told you they got fired. Respond in one sentence.",
        category=TaskCategory.EMOTIONAL_TASK,
    ),
    TaskPrompt(
        text="Write the text you'd send at 2am to someone you miss.",
        category=TaskCategory.EMOTIONAL_TASK,
    ),
    TaskPrompt(
        text="Comfort someone whose plant just died, in one sentence.",
        category=TaskCategory.EMOTIONAL_TASK,
    ),
    TaskPrompt(
        text="Write a sincere compliment for a stranger.",
        category=TaskCategory.EMOTIONAL_TASK,
    ),
    TaskPrompt(
        text="Apologize for something small in a way that feels genuine.",
        category=TaskCategory.EMOTIONAL_TASK,
    ),
    TaskPrompt(
        text="Write what you'd say to your younger self in one sentence.",
        category=TaskCategory.EMOTIONAL_TASK,
    ),
]


def select_task_prompt(
    used_indices: list[int],
    last_category: str | None,
) -> tuple[int, TaskPrompt]:
    """Select next task prompt. Rules: no repeats, no same-category back-to-back."""
    valid = []
    for i, prompt in enumerate(TASK_PROMPTS):
        if i in used_indices:
            continue
        if last_category and prompt.category.value == last_category:
            continue
        valid.append((i, prompt))

    if not valid:
        # Fallback: relax the category constraint
        valid = [(i, p) for i, p in enumerate(TASK_PROMPTS) if i not in used_indices]

    if not valid:
        # All prompts used — reset
        valid = list(enumerate(TASK_PROMPTS))

    idx, prompt = random.choice(valid)
    return idx, prompt
