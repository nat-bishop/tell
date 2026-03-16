"""FastAPI application entry point."""

from __future__ import annotations

import logging

import logfire
import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.actions import router as actions_router
from backend.api.routes.events import router as events_router
from backend.api.routes.game import router as game_router
from backend.config import Settings


def configure_logging() -> None:
    """Configure logging via structlog with unified formatting for backend + uvicorn."""
    settings = Settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Shared structlog processors
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    # Configure structlog — events pass through shared processors then into stdlib
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    # Route stdlib logging through structlog's formatter
    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            foreign_pre_chain=shared_processors,
        )
    )

    # Backend logger
    backend_logger = logging.getLogger("backend")
    backend_logger.setLevel(level)
    backend_logger.handlers = [handler]
    backend_logger.propagate = False

    # Uvicorn loggers — same structlog formatter for uniform output
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = [handler]
        uv_logger.propagate = False


configure_logging()

# --- Logfire observability (opt-in via TELL_LOGFIRE_ENABLED=true) ---
_settings = Settings()
if _settings.logfire_enabled:
    logfire.configure(service_name="tell")
    logfire.instrument_pydantic_ai()
    logfire.instrument_google_genai()

app = FastAPI(
    title="Tell",
    version="0.1.0",
    description="Multiplayer social deduction game — reverse Turing test",
)

# CORS — allow all origins for dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if _settings.logfire_enabled:

    def _game_id_attributes_mapper(request, attributes):  # type: ignore[no-untyped-def]
        """Extract game_id from path and add it to span attributes."""
        attrs = {
            "values": attributes["values"],
            "errors": attributes["errors"],
        }
        values = attributes.get("values") or {}
        if "game_id" in values:
            attrs["game_id"] = values["game_id"]
        return attrs

    logfire.instrument_fastapi(app, request_attributes_mapper=_game_id_attributes_mapper)

app.include_router(game_router, prefix="/games", tags=["games"])
app.include_router(events_router, prefix="/games", tags=["events"])
app.include_router(actions_router, prefix="/games", tags=["actions"])


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    settings = Settings()
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=settings.backend_port,
        reload=True,
        log_level="info",
    )
