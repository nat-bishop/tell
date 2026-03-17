"""Robot alias and ID generation."""

from __future__ import annotations

import random
import uuid

PREFIXES = [
    "UNIT",
    "BOT",
    "NODE",
    "BYTE",
    "CORE",
    "CHIP",
    "WIRE",
    "FLUX",
    "GRID",
    "NANO",
    "PING",
    "PORT",
    "HASH",
    "LOOP",
    "NULL",
]


def generate_game_id() -> str:
    """Generate a short hex game ID."""
    return uuid.uuid4().hex[:8]


def generate_player_id() -> str:
    """Generate a hex player ID."""
    return uuid.uuid4().hex[:12]


def generate_aliases(n: int, exclude: set[str] | None = None) -> list[str]:
    """Generate n unique robot aliases like UNIT-7, BOT-42."""
    exclude = exclude or set()
    aliases = []
    attempts = 0
    while len(aliases) < n and attempts < 100:
        prefix = random.choice(PREFIXES)
        suffix = random.randint(1, 99)
        alias = f"{prefix}-{suffix}"
        if alias not in exclude and alias not in aliases:
            aliases.append(alias)
        attempts += 1
    return aliases
