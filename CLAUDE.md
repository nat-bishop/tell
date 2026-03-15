# Tell

Multiplayer social deduction game — reverse Turing test meets Among Us. Players join a group chat where some are AI, some human. Everyone pretends to be a robot. Each round: answer a prompt, discuss, vote on who's human.

## Architecture

```
schemas/          Shared Pydantic models — the contract between backend + frontend
  game_state.py   GamePhase, Player, TellGameState (core state machine)
  api_models.py   SSE event types + POST request/response models
  prompts.py      30 game prompts with category-aware selection
  aliases.py      Robot alias generator (UNIT-7, BOT-42)
  constants.py    Timer durations, player limits

backend/
  main.py         FastAPI entry point (CORS, structlog, Logfire opt-in)
  config.py       Settings from config.toml + TELL_* env overrides
  api/
    deps.py       Singletons: ConnectionManager, GameRepository, TimerManager
    routes/
      game.py     POST /games, GET /games/{id}
      events.py   GET /games/{id}/events (SSE stream)
      actions.py  POST join/start/answer/chat/vote + phase transition helpers
  services/
    connection_manager.py  Per-game asyncio.Queue broadcast + event log (reconnection replay)
    game_repository.py     In-memory game session store
    game_logic.py          Pure functions: transitions, vote resolution, validation
    timer_manager.py       asyncio.Task per phase timer
    ai_scheduler.py        Generate-then-lock AI player scheduling
  llm/
    agents.py              PydanticAI agent: answer, chat, vote generation
    personalities.py       5 AI personalities with system prompts + fallbacks

frontend/src/
  app/page.tsx             Landing: "tell — a game of words and suspicion"
  app/game/[id]/page.tsx   Game page: join screen → phase routing (spectator view for eliminated)
  components/              Lobby, Prompt, Chat, Vote, Elimination, GameOver, Stage, Timer, Dialogue, SystemText
  hooks/useGameStore.ts    Zustand store — all game state + SSE event handlers
  hooks/useGameEvents.ts   EventSource connection → store dispatch
  hooks/useTimer.ts        Client-side countdown from server deadline
  api/actions.ts           Typed POST helpers
  api/events.ts            SSE client with typed event routing
  api/client.ts            Base fetch wrapper
```

## Running

```bash
make              # Show all targets
make dev          # Backend (port 8501) + frontend (port 3500) together
make backend      # FastAPI only
make frontend     # Next.js only
make codegen      # Regenerate TS types from backend OpenAPI spec
make lint         # Ruff check + format
make test         # pytest
make clean        # Remove caches and build artifacts
```

Dependencies auto-install via sentinel files when `pyproject.toml` or `package.json` change.

## Environment

Copy `.env.example` → `.env` and set `GOOGLE_API_KEY`. AI model: `google-gla:gemini-3.1-flash-lite-preview` (configured in `config.toml`).

Optional: `TELL_LOGFIRE_ENABLED=true` for Pydantic Logfire tracing.

## Critical Patterns

### Real-time: SSE, not WebSockets
GET-based `EventSource` for persistent game stream, POST for actions. Each client gets an `asyncio.Queue`. Server broadcasts `GameEvent`s to all queues. Events carry monotonic `seq` numbers. Reconnection replays missed events from a 200-event log, or falls back to full `state_sync`.

### Concurrency: generate-then-lock
AI players call LLM **outside** the lock, then acquire `asyncio.Lock` only to write result + broadcast. If phase changed during LLM generation, result is discarded. One lock per game, held for microseconds (never during I/O).

### Type pipeline
Pydantic models → OpenAPI → `openapi-typescript` → generated TS types. Run `make codegen` after changing any schema or route signature.

### State machine
```
LOBBY → PROMPT (45s) → CHAT (75s) → VOTE (20s) → ELIMINATION (5s) → PROMPT → ... → GAME_OVER
```

Phase transitions happen in `actions.py` helper functions (`_handle_phase_expiry`, `_do_vote_resolution`, `_after_elimination`). Timer callbacks and early-completion checks both funnel through these same helpers. AI scheduler hooks into each transition via `ai_on_phase_change()`.

### Game logic is pure
`game_logic.py` contains pure functions (no I/O, no async). State transitions, vote tallying, game-over checks, client state sanitization. Routes call these under the lock.

## Gotchas

- **Ports**: Backend defaults to **8501**. Frontend runs on **3500**. Next.js rewrites `/api/*` → backend via `next.config.ts`.
- **`from __future__ import annotations`** used in all Python files. Use `datetime.now(UTC)`, never `datetime.utcnow()`.
- **`schemas/` is top-level**: Imported by both `backend/` and `scripts/`. Don't nest under `backend/`.
- **No database**: All state is in-memory. Server restart kills all games.
- **Circular import in ai_scheduler**: It imports from `actions.py` inside functions (not at top level) to avoid circular dependency with route helpers.
- **AI personalities assigned at game start**: `assign_personalities()` in `ai_scheduler.py` maps player IDs to personalities. Must be called before `on_phase_change()`.
- **Eliminated players see spectator views**: `game/[id]/page.tsx` checks `isAlive` and renders `SpectatorPrompt`/`SpectatorVote` instead of interactive components.

## Code Conventions

- **Python**: Pydantic v2 models, type hints, `ruff` formatting (line-length 100)
- **TypeScript**: Strict mode, path aliases (`@/*` → `src/*`), Zustand for state
- **Fonts**: Cormorant (literary content), Cormorant SC (character names), IBM Plex Mono (system text)
- **Color**: `--page` `--ink` `--dim` `--rule` only. `--warm` (#B85C38) reserved for timer warning, vote selection, and "human" reveals.
- **Animation**: CSS only, no libraries. `animate-fade-in`, `animate-elimination-reveal`.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — real-time system, state machine, AI scheduling
- [Game Design](docs/GAME_DESIGN.md) — mechanics, prompts, design rationale
