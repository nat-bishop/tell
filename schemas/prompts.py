"""Game prompts — the engine of social deduction."""

from __future__ import annotations

import enum
import random

from pydantic import BaseModel


class PromptCategory(str, enum.Enum):
    EMOTIONAL = "emotional"
    LOGICAL = "logical"
    CREATIVE = "creative"
    PHILOSOPHICAL = "philosophical"
    SOCIAL = "social"


class Prompt(BaseModel):
    text: str
    category: PromptCategory
    min_round: int = 1  # social prompts require round 2+


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
