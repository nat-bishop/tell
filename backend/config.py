"""Backend configuration — loaded from config.toml with env var overrides."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.toml"

# Load .env so API keys are available to pydantic-ai and other libs
load_dotenv(_PROJECT_ROOT / ".env")


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
        self.question_duration: int = int(
            os.environ.get("TELL_QUESTION_DURATION", game.get("question_duration", 25))
        )
        self.respond_duration: int = int(
            os.environ.get("TELL_RESPOND_DURATION", game.get("respond_duration", 30))
        )
        self.review_duration: int = int(
            os.environ.get("TELL_REVIEW_DURATION", game.get("review_duration", 40))
        )
        self.nominate_duration: int = int(
            os.environ.get("TELL_NOMINATE_DURATION", game.get("nominate_duration", 15))
        )
        self.elimination_duration: int = int(
            os.environ.get("TELL_ELIMINATION_DURATION", game.get("elimination_duration", 8))
        )

        # Player limits
        self.min_humans: int = int(os.environ.get("TELL_MIN_HUMANS", game.get("min_humans", 2)))
        self.max_players: int = int(os.environ.get("TELL_MAX_PLAYERS", game.get("max_players", 10)))
        self.min_ai: int = int(os.environ.get("TELL_MIN_AI", game.get("min_ai", 1)))
        self.max_ai: int = int(os.environ.get("TELL_MAX_AI", game.get("max_ai", 3)))

        # Observability
        self.logfire_enabled: bool = (
            os.environ.get("TELL_LOGFIRE_ENABLED", "false").lower() == "true"
        )

        # Operational (env-only)
        self.backend_port: int = int(os.environ.get("BACKEND_PORT", "8501"))
        self.log_level: str = os.environ.get("TELL_LOG_LEVEL", "INFO")
