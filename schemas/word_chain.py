"""Word Chain — seed words and selection logic."""

from __future__ import annotations

import random

SEED_WORDS: list[str] = [
    "ocean",
    "bridge",
    "candle",
    "thunder",
    "garden",
    "mirror",
    "shadow",
    "compass",
    "lantern",
    "fossil",
    "whisper",
    "anchor",
    "crystal",
    "horizon",
    "ember",
    "riddle",
    "velvet",
    "glacier",
    "feather",
    "spiral",
    "harvest",
    "beacon",
    "cinder",
    "marble",
    "needle",
    "pillow",
    "canyon",
    "dagger",
    "puzzle",
    "ribbon",
    "copper",
    "orchid",
    "fortress",
    "chimney",
    "harbor",
    "blanket",
    "cradle",
    "eclipse",
    "fountain",
    "jungle",
    "keystone",
    "labyrinth",
    "meadow",
    "nebula",
    "oxygen",
    "passport",
    "quarry",
    "relic",
    "scaffold",
    "telescope",
    "umbrella",
    "volcano",
    "windmill",
    "bramble",
    "carousel",
    "doorstep",
    "envelope",
    "firefly",
    "granite",
    "hammock",
    "iceberg",
    "jasmine",
    "kaleidoscope",
    "lighthouse",
    "mushroom",
    "nightfall",
    "obelisk",
    "pendulum",
    "quicksand",
    "rosemary",
    "staircase",
    "tapestry",
    "underpass",
    "vineyard",
    "warehouse",
    "abyss",
    "bonfire",
    "cocoon",
    "driftwood",
    "evergreen",
    "folklore",
    "gemstone",
    "hourglass",
    "ivy",
    "junction",
    "kettle",
    "lullaby",
    "monsoon",
    "nomad",
    "outpost",
    "parchment",
    "quilt",
    "rampart",
    "sandstone",
    "threshold",
    "undercurrent",
    "viaduct",
    "waterfall",
    "almanac",
    "blueprint",
    "catalyst",
    "dominion",
]

# Simple fallback associations for when LLM times out
FALLBACK_ASSOCIATIONS: dict[str, list[str]] = {
    "ocean": ["wave", "deep", "salt", "blue", "shore"],
    "bridge": ["crossing", "gap", "arch", "connect", "span"],
    "candle": ["flame", "wax", "light", "wick", "glow"],
    "thunder": ["storm", "loud", "lightning", "rumble", "sky"],
    "garden": ["flower", "grow", "soil", "green", "bloom"],
    "mirror": ["reflection", "glass", "self", "image", "face"],
    "shadow": ["dark", "light", "follow", "ghost", "quiet"],
}


def select_seed_word(used_seeds: list[str] | None = None) -> str:
    """Pick a random seed word, avoiding recent ones."""
    used = set(used_seeds or [])
    available = [w for w in SEED_WORDS if w not in used]
    if not available:
        available = SEED_WORDS
    return random.choice(available)


def get_fallback_association(seed: str) -> str:
    """Get a simple fallback association when LLM times out."""
    if seed in FALLBACK_ASSOCIATIONS:
        return random.choice(FALLBACK_ASSOCIATIONS[seed])
    # Generic fallback: pick a random concrete noun
    return random.choice(["thing", "place", "memory", "feeling", "sound"])
