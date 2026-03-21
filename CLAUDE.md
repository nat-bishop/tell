# Tell

Multiplayer social deduction game — reverse Turing test. Players join a group where some are AI, some human. Humans play as themselves. AI players try to pass as human. Everyone votes each round on who sounds most human. After 5 rounds: big reveal, highest score wins.

## Architecture

```
schemas/           Shared Pydantic models — contract between backend + frontend
                   NOT nested under backend/ — imported by both backend/ and scripts/
backend/
  config.py        Settings from config.toml + TELL_* env overrides
  api/routes/      FastAPI routes (game, events, actions, matchmaking, debug)
  services/        Game logic (pure functions in game_logic.py), transitions,
                   timer, AI scheduling, matchmaking, connection manager
  minigames/       Plugin package — one MinigameHandler subclass per round type.
                   Registry in __init__.py. To add a minigame: new handler + register().
  llm/             PydanticAI agents (ai_agent, judge_agent, narrator_agent),
                   AI personalities, prompt builders
tests/             pytest. Factories in factories.py, fixtures in conftest.py.
frontend/src/
  facility/        "Verification Facility" diegetic UI theme
    phases/        Per-phase components (lobby, prompt, vote, brain test, wager, signal, game over)
    FacilityScene.tsx  MINIGAME_COMPONENTS registry: round_type -> {Active, Results, Prompt?}
  hooks/useGameStore.ts  Zustand store — all game state + SSE event handlers
  api/             Typed POST helpers + SSE clients (game events, matchmaking)
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
make typecheck    # mypy
make coverage     # pytest with coverage report
make down         # Kill dev servers (cleans up zombie processes)
make clean        # Remove caches and build artifacts
```

Dependencies auto-install via sentinel files when `pyproject.toml` or `package.json` change.

## Environment

Copy `.env.example` -> `.env` and set `GOOGLE_API_KEY`. AI model configured in `config.toml`.

- `NEXT_PUBLIC_API_URL` — backend URL for REST + SSE (default: `http://localhost:8501`)
- `TELL_LOG_LEVEL=DEBUG` — enables debug logging **and** mounts debug routes (`/debug/seed`, etc.)
- All other `TELL_*` overrides (durations, player limits, etc.): see `config.py`

**Logging**: INFO for game actions (joins, answers, votes, phase transitions). DEBUG for SSE internals.

## Critical Patterns

### Real-time: SSE, not WebSockets
GET-based `EventSource` for persistent game stream, POST for actions. Each client gets an `asyncio.Queue`. Events carry monotonic `seq` numbers. Reconnection replays missed events from a 200-event log, or falls back to full `state_sync`.

### Concurrency: generate-then-lock
AI players call LLM **outside** the lock, then acquire `asyncio.Lock` only to write result + broadcast. If phase changed during generation, result is discarded. One lock per game, held for microseconds (never during I/O).

### Type pipeline
Pydantic models -> OpenAPI -> `openapi-typescript` -> generated TS types. Run `make codegen` after changing any schema or route signature. SSE event types use `Literal["event_name"]` for exhaustive frontend matching.

### State machine
5 phases: `LOBBY, PROMPT, ACTIVE, RESULTS, GAME_OVER`. 4 round types: `TASK, BRAIN_TEST, WAGER, SIGNAL`. `ACTIVE` and `RESULTS` are generic — behavior dispatches via `get_handler(round_type)` in `backend/minigames/`. Round types selected dynamically by `get_next_round_type()`, no consecutive repeat. Phase transitions in `transitions.py` are minigame-agnostic.

### Scoring: 100x integers
All scores are integers scaled by 100 for granularity without floats. Task scoring is **negative** (votes received = -100 points). Per-minigame formulas in their respective handlers.

### Game logic is pure
`game_logic.py` contains pure functions (no I/O, no async). Routes call these under the lock.

## Gotchas

- **Ports**: Backend **8501**, frontend **3500**. Frontend talks directly to backend — CORS, no proxy.
- **`from __future__ import annotations`** in all Python files. Use `datetime.now(UTC)`, never `datetime.utcnow()`.
- **`schemas/` is top-level**: Don't nest under `backend/`. Imported by both backend and scripts.
- **No database**: All state in-memory. Server restart kills all games. Recordings written to `recordings/`.
- **Circular imports**: `ai_scheduler <-> transitions` and minigame `_brain_loop`/`_wager_loop`/`_signal_loop` all import `do_active_complete` **at runtime inside async functions**, not at top level. This is intentional — don't "fix" by adding top-level imports.
- **PydanticAI `validation_context`**: This is a **constructor** parameter on `Agent()`, not a `run()` parameter. Per-call validation data (valid indices, valid aliases) goes through `deps=AICallContext(valid=...)`. See `llm/agents.py`.
- **AI players are persistent characters**: One `ai_agent` instance handles ALL player actions (answers, votes, guesses, bets). Each AI player has conversation history (`_conversation_history` in `ai_scheduler.py`) passed via `message_history=` — they remember everything across rounds. New player actions MUST go through `_run_ai_agent()`, never create new Agent instances. Separate stateless agents (like `judge_agent`) are fine for system-level tasks that aren't player-facing.
- **Signal judgments are graded ints**: `signal_judgments` values are 0 (wrong), 1 (close), 2 (correct). Not booleans.
- **Wager self-bet allowed**: Unlike gallery vote which rejects self-votes, wager bet accepts `target_player_id == player_id`.
- **No elimination**: All players participate all 5 rounds. No spectator mode.
- **`TELL_MAX_PLAYERS`** actually limits **humans**, not total players (total = humans + AI).

## Code Conventions

- **Fonts**: Cormorant (literary content), Cormorant SC (character names), IBM Plex Mono (system text)
- **Color**: `--warm` (#E07A5F) reserved for timer warning, vote selection, and "human" reveals. Full palette in `globals.css`.
- **Animation**: CSS only, no libraries. Classes in `globals.css`.
- **Textarea submit**: Enter to submit (no Shift). Auto-resize via `scrollHeight`.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — real-time system, state machine, AI scheduling
- [Game Design](docs/GAME_DESIGN.md) — mechanics, prompts, design rationale
- [Design Principles](docs/DESIGN_PRINCIPLES.md) — design philosophy and decisions
- [Research](docs/RESEARCH.md) — game theory research, mechanic validation
