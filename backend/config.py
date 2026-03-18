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
        self.task_prompt_duration: int = int(
            os.environ.get("TELL_TASK_PROMPT_DURATION", game.get("task_prompt_duration", 25))
        )
        self.prompt_reading_duration: int = int(
            os.environ.get("TELL_PROMPT_READING_DURATION", game.get("prompt_reading_duration", 10))
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
        self.brain_test_duration: int = int(
            os.environ.get("TELL_BRAIN_TEST_DURATION", game.get("brain_test_duration", 75))
        )
        self.brain_test_challenge_duration: int = int(
            os.environ.get(
                "TELL_BRAIN_TEST_CHALLENGE_DURATION",
                game.get("brain_test_challenge_duration", 12),
            )
        )
        self.brain_test_challenges: int = int(
            os.environ.get(
                "TELL_BRAIN_TEST_CHALLENGES",
                game.get("brain_test_challenges", 5),
            )
        )
        self.brain_test_results_duration: int = int(
            os.environ.get(
                "TELL_BRAIN_TEST_RESULTS_DURATION",
                game.get("brain_test_results_duration", 15),
            )
        )

        # Player limits
        self.min_humans: int = int(os.environ.get("TELL_MIN_HUMANS", game.get("min_humans", 2)))
        self.max_players: int = int(os.environ.get("TELL_MAX_PLAYERS", game.get("max_players", 10)))
        self.min_ai: int = int(os.environ.get("TELL_MIN_AI", game.get("min_ai", 1)))
        self.max_ai: int = int(os.environ.get("TELL_MAX_AI", game.get("max_ai", 3)))

        # Discussion AI
        self.discussion_buffer_delay: float = float(
            os.environ.get("TELL_DISCUSSION_BUFFER_DELAY", game.get("discussion_buffer_delay", 1.5))
        )
        self.discussion_react_cooldown: float = float(
            os.environ.get(
                "TELL_DISCUSSION_REACT_COOLDOWN", game.get("discussion_react_cooldown", 5.0)
            )
        )

        # Recording
        self.record_games: bool = os.environ.get(
            "TELL_RECORD_GAMES", str(game.get("record_games", True))
        ).lower() in ("true", "1", "yes")

        # Observability
        self.logfire_enabled: bool = (
            os.environ.get("TELL_LOGFIRE_ENABLED", "false").lower() == "true"
        )

        # Operational (env-only)
        self.backend_port: int = int(os.environ.get("BACKEND_PORT", "8501"))
        self.log_level: str = os.environ.get("TELL_LOG_LEVEL", "INFO")

        # Debug routes enabled when log level is DEBUG
        self.debug: bool = self.log_level.upper() == "DEBUG"

        # Matchmaking
        mm = toml.get("matchmaking", {})
        self.mm_min_humans: int = int(os.environ.get("TELL_MM_MIN_HUMANS", mm.get("min_humans", 2)))
        self.mm_max_humans: int = int(os.environ.get("TELL_MM_MAX_HUMANS", mm.get("max_humans", 5)))
        self.mm_countdown_seconds: int = int(
            os.environ.get("TELL_MM_COUNTDOWN", mm.get("countdown_seconds", 20))
        )
        self.mm_solo_timeout_seconds: int = int(
            os.environ.get("TELL_MM_SOLO_TIMEOUT", mm.get("solo_timeout_seconds", 45))
        )
        self.mm_min_total: int = int(os.environ.get("TELL_MM_MIN_TOTAL", mm.get("min_total", 5)))
        self.mm_max_total: int = int(os.environ.get("TELL_MM_MAX_TOTAL", mm.get("max_total", 7)))
