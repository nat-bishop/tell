"""Backend configuration — loaded from config.toml with env var overrides."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.toml"


def _load_toml() -> dict:
    """Read config.toml from the project root."""
    with open(_CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


class Settings:
    """Application settings.

    Reads config.toml for game preferences.
    Environment variables with TELL_ prefix override TOML values.
    """

    def __init__(self) -> None:
        toml = _load_toml()
        game = toml.get("game", {})

        # AI
        self.ai_model: str = os.environ.get("TELL_AI_MODEL", game.get("ai_model", ""))
        self.ai_retries: int = int(os.environ.get("TELL_AI_RETRIES", game.get("ai_retries", 2)))

        # Phase durations (seconds)
        self.prompt_duration: int = int(
            os.environ.get("TELL_PROMPT_DURATION", game.get("prompt_duration", 45))
        )
        self.chat_duration: int = int(
            os.environ.get("TELL_CHAT_DURATION", game.get("chat_duration", 75))
        )
        self.vote_duration: int = int(
            os.environ.get("TELL_VOTE_DURATION", game.get("vote_duration", 20))
        )
        self.elimination_duration: int = int(
            os.environ.get("TELL_ELIMINATION_DURATION", game.get("elimination_duration", 5))
        )

        # Player limits
        self.min_humans: int = int(
            os.environ.get("TELL_MIN_HUMANS", game.get("min_humans", 2))
        )
        self.max_players: int = int(
            os.environ.get("TELL_MAX_PLAYERS", game.get("max_players", 10))
        )
        self.min_ai: int = int(os.environ.get("TELL_MIN_AI", game.get("min_ai", 1)))
        self.max_ai: int = int(os.environ.get("TELL_MAX_AI", game.get("max_ai", 3)))

        # Observability
        self.logfire_enabled: bool = (
            os.environ.get("TELL_LOGFIRE_ENABLED", "false").lower() == "true"
        )

        # Operational (env-only)
        self.backend_port: int = int(os.environ.get("BACKEND_PORT", "8001"))
        self.log_level: str = os.environ.get("TELL_LOG_LEVEL", "INFO")
