# Tell

Multiplayer social deduction game — reverse Turing test meets Among Us. Players join a group where some are AI, some human. Everyone pretends to be a robot. Each round: answer a prompt, question each other through structured minigames, vote on who's human.

## Architecture

```
schemas/          Shared Pydantic models — the contract between backend + frontend
  game_state.py   GamePhase, Player, TellGameState, QuestionEntry, RoundState
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
      actions.py  POST join/start/answer/question/respond/nominate/vote
  services/
    connection_manager.py  Per-game asyncio.Queue broadcast + event log
    game_repository.py     In-memory game session store
    game_logic.py          Pure functions: transitions, vote resolution, validation
    timer_manager.py       asyncio.Task per phase timer
    transitions.py         Async phase transition sequences (start_phase_timer,
                           handle_phase_expiry, do_*_complete helpers)
    ai_scheduler.py        Generate-then-lock AI player scheduling
  llm/
    agents.py              PydanticAI: answer, question, response, vote, nomination,
                           synthesis, verdict generation
    personalities.py       5 AI personalities with system prompts + question styles

tests/
  conftest.py     Fixtures: standard_game (4p, 2h/2ai, PROMPT), game_state/player/round_state factories
  factories.py    Plain functions building Pydantic models with sensible defaults
  test_game_logic.py  Tests for all pure functions in game_logic.py
  test_schemas.py     Tests for schema models, prompt selection, alias generation

frontend/src/
  app/page.tsx             Landing: "tell — a game of words and suspicion"
  app/game/[id]/page.tsx   Game page: join → phase routing (spectator for eliminated)
  components/
    AnswerCard.tsx         Shared answer-first card (alias pinned to bottom, button/div)
    PlayerBar.tsx          Persistent player strip during gameplay
    VoteOverlay.tsx        Multi-vote selection overlay (up to 3 votes)
    QuestionPhase.tsx      QUESTION phase — shows target's answer, write follow-up
    RespondPhase.tsx       RESPOND phase — answer received questions
    NominatePhase.tsx      NOMINATE phase — pick who to interrogate
    ReviewPhase.tsx        REVIEW phase — AnswerCard grid + voting
    Prompt.tsx, Elimination.tsx, GameOver.tsx, Lobby.tsx
    Stage.tsx, Timer.tsx, Dialogue.tsx, SystemText.tsx
  hooks/useGameStore.ts    Zustand store — all game state + SSE event handlers
  hooks/useGameEvents.ts   EventSource connection → store dispatch
  hooks/useTimer.ts        Client-side countdown from server deadline
  hooks/useAnswerEntries.ts Maps answers dict → [{alias, text}] for display
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
make down         # Kill dev servers (cleans up zombie processes)
make clean        # Remove caches and build artifacts
```

Dependencies auto-install via sentinel files when `pyproject.toml` or `package.json` change.

## Environment

Copy `.env.example` → `.env` and set `GOOGLE_API_KEY`. AI model: `google-gla:gemini-3.1-flash-lite-preview` (configured in `config.toml`).

Optional overrides via `TELL_*` env vars (see `config.py`):
- `TELL_LOG_LEVEL=DEBUG` — enables debug logging **and** mounts debug routes (`/debug/seed`, etc.)
- `TELL_LOGFIRE_ENABLED=true` — Pydantic Logfire tracing

**Logging convention**: INFO for game actions (player_joined, answer_submitted, vote_cast, phase transitions). DEBUG for SSE internals (sse_connected, sse_replay, queue ops).

## Critical Patterns

### Real-time: SSE, not WebSockets
GET-based `EventSource` for persistent game stream, POST for actions. Each client gets an `asyncio.Queue`. Server broadcasts `GameEvent`s to all queues. Events carry monotonic `seq` numbers. Reconnection replays missed events from a 200-event log, or falls back to full `state_sync`.

### Concurrency: generate-then-lock
AI players call LLM **outside** the lock, then acquire `asyncio.Lock` only to write result + broadcast. If phase changed during LLM generation, result is discarded. One lock per game, held for microseconds (never during I/O).

### Type pipeline
Pydantic models → OpenAPI → `openapi-typescript` → generated TS types. Run `make codegen` after changing any schema or route signature.

### State machine — two round types

**Probe** (round-robin chain, anonymous questions):
```
LOBBY → PROMPT (45s) → QUESTION (25s) → RESPOND (30s) → REVIEW (40s) → ELIMINATION (8s) → PROMPT → ... → GAME_OVER
```

**Interrogation** (hot seat, LLM synthesis):
```
LOBBY → PROMPT (45s) → NOMINATE (15s) → QUESTION (20s) → RESPOND (30s) → REVIEW (40s) → ELIMINATION (8s) → ...
```

Round types alternate: round 1 = probe, round 2 = interrogation, etc. Generated at game start in `state.round_types`.

Phase transitions are in `transitions.py` (extracted from `actions.py`): `start_phase_timer`, `handle_phase_expiry`, `do_prompt_complete`, `do_nominate_complete`, `do_question_complete`, `do_respond_complete`, `do_vote_resolution`, `do_after_elimination`. Timer callbacks and early-completion checks both call these same helpers. AI scheduler hooks into each transition via `ai_on_phase_change()`.

### Game logic is pure
`game_logic.py` contains pure functions (no I/O, no async). State transitions, vote tallying, game-over checks, assignment logic, client state sanitization. Routes call these under the lock.

### Voting: multi-vote
Players get `min(3, alive_count - 1)` votes during REVIEW phase. Votes are changeable until timer expires. No early-complete for REVIEW.

### LLM-powered features
- **Question synthesis** (Interrogation): all submitted questions → LLM → one cohesive cross-examination paragraph. 5s timeout, fallback: numbered list.
- **Verdict summary** (Elimination): one-line dramatic summary after role reveal. 3s timeout, fallback: no verdict.

## Gotchas

- **Ports**: Backend defaults to **8501**. Frontend runs on **3500**. Next.js rewrites `/api/*` → backend via `next.config.ts`.
- **Windows process cleanup**: `uv run uvicorn --reload` spawns a process tree (uv → reloader → worker). `make down` and the `dev` trap use `taskkill /F /T /PID` to kill the full tree; plain `kill` leaves child processes as zombies holding the port.
- **`from __future__ import annotations`** used in all Python files. Use `datetime.now(UTC)`, never `datetime.utcnow()`.
- **`schemas/` is top-level**: Imported by both `backend/` and `scripts/`. Don't nest under `backend/`.
- **No database**: All state is in-memory. Server restart kills all games.
- **Circular import between ai_scheduler and transitions**: Both import each other's functions inside async functions (not at top level) to avoid circular dependency at module init.
- **AI personalities assigned at game start**: `assign_personalities()` in `ai_scheduler.py` maps player IDs to personalities. Must be called before `on_phase_change()`.
- **Eliminated players see spectator views**: `game/[id]/page.tsx` checks `isAlive` and passes `spectator` prop to phase components.
- **Round-robin assignments** (Probe): player `i` questions player `(i+1) % len(alive)`. Generated in `assign_question_targets()`.
- **Hot-seated player** (Interrogation): nominated player can't submit questions, only responds to synthesis.

## Code Conventions

- **Python**: Pydantic v2 models, type hints, `ruff` formatting (line-length 100)
- **TypeScript**: Strict mode, path aliases (`@/*` → `src/*`), Zustand for state
- **Fonts**: Cormorant (literary content), Cormorant SC (character names), IBM Plex Mono (system text)
- **Color**: `--page` `--ink` `--dim` `--rule` only. `--warm` (#B85C38) reserved for timer warning, vote selection, and "human" reveals.
- **Animation**: CSS only, no libraries. `animate-fade-in`, `animate-elimination-reveal`.
- **Textarea submit**: All gameplay textareas submit on Enter (no Shift). Auto-resize via `scrollHeight`. `maxLength` enforced per field.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — real-time system, state machine, AI scheduling
- [Game Design](docs/GAME_DESIGN.md) — mechanics, prompts, design rationale
