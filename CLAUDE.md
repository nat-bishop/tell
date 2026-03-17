# Tell

Multiplayer social deduction game — reverse Turing test meets Among Us. Players join a group where some are AI, some human. Everyone pretends to be a robot. Each round: answer a prompt, question each other through structured minigames, vote on who's human.

## Architecture

```
schemas/          Shared Pydantic models — the contract between backend + frontend
  game_state.py   GamePhase, Player, TellGameState, QuestionEntry, RoundState, ChainRound
  api_models.py   SSE event types + POST request/response models (incl. matchmaking)
  prompts.py      30 game prompts (5 categories) + 42 task prompts (7 categories)
  word_chain.py   SEED_WORDS list, select_seed_word, get_fallback_association
  aliases.py      Robot alias generator (UNIT-7, BOT-42)
  constants.py    MISSING_ALIAS, NO_RESPONSE, MATCHMAKING_LOBBY_ID

backend/
  main.py         FastAPI entry point (CORS, structlog, Logfire opt-in)
  config.py       Settings from config.toml + TELL_* env overrides
  api/
    deps.py       Singletons: ConnectionManager, GameRepository, TimerManager,
                  MatchmakingService
    routes/
      game.py         POST /games, GET /games/{id}
      events.py       GET /games/{id}/events (SSE stream)
      actions.py      POST join/start/answer/question/respond/nominate/vote/chain-word
      matchmaking.py  POST /matchmaking/join|leave, GET /matchmaking/status|events
  services/
    connection_manager.py  Per-game asyncio.Queue broadcast + event log + recording buffer
    game_repository.py     In-memory game session store
    recorder.py            Writes completed game JSON to recordings/ on game over
    game_logic.py          Pure functions: transitions, vote resolution, validation,
                           word chain selection, round type cycling
    timer_manager.py       asyncio.Task per phase timer
    transitions.py         Async phase transition sequences (start_phase_timer,
                           handle_phase_expiry, do_*_complete helpers,
                           do_chain_complete, initialize_and_start_game)
    ai_scheduler.py        Generate-then-lock AI player scheduling + chain sub-rounds
    matchmaking.py         Rolling lobby: queue, countdown, solo timeout, fire_game
  llm/
    agents.py              PydanticAI: answer, question, response, vote, nomination,
                           synthesis, verdict, word association (generate_association)
    personalities.py       5 AI personalities with system prompts + question styles

tests/
  conftest.py     Fixtures: standard_game (4p, 2h/2ai, PROMPT), game_state/player/round_state factories
  factories.py    Plain functions building Pydantic models with sensible defaults
  test_game_logic.py  Tests for all pure functions in game_logic.py
  test_schemas.py     Tests for schema models, prompt selection, alias generation

frontend/src/
  app/page.tsx             Landing: "play" (→ queue) + "private game" (→ create)
  app/queue/page.tsx       Matchmaking queue: name input, SSE lobby updates, redirect
  app/game/[id]/page.tsx   Game page: join → phase routing (spectator for eliminated)
  components/
    AnswerCard.tsx         Shared answer-first card (alias pinned to bottom, button/div)
    PlayerBar.tsx          Persistent player strip during gameplay
    VoteOverlay.tsx        Multi-vote selection overlay (up to 3 votes)
    PhaseInterstitial.tsx  Phase transition overlay (round N + type label, fade in/out)
    WordChainPhase.tsx     CHAIN phase — seed word display, growing chain, word input
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
  api/actions.ts           Typed POST helpers (incl. submitChainWord, matchmaking)
  api/events.ts            SSE client with typed event routing
  api/matchmaking-events.ts  SSE client for matchmaking lobby (LobbyStatus, GameAssigned)
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
- `TELL_MM_MIN_HUMANS`, `TELL_MM_COUNTDOWN`, `TELL_MM_SOLO_TIMEOUT`, `TELL_MM_MIN_TOTAL`, `TELL_MM_MAX_TOTAL` — matchmaking thresholds (see `config.toml [matchmaking]`)
- `TELL_CHAIN_DURATION`, `TELL_CHAIN_SUB_ROUND_DURATION`, `TELL_CHAIN_SUB_ROUNDS` — word chain timing
- `TELL_RECORD_GAMES=false` — disable writing game recordings to `recordings/`

**Logging convention**: INFO for game actions (player_joined, answer_submitted, vote_cast, phase transitions). DEBUG for SSE internals (sse_connected, sse_replay, queue ops).

## Critical Patterns

### Real-time: SSE, not WebSockets
GET-based `EventSource` for persistent game stream, POST for actions. Each client gets an `asyncio.Queue`. Server broadcasts `GameEvent`s to all queues. Events carry monotonic `seq` numbers. Reconnection replays missed events from a 200-event log, or falls back to full `state_sync`.

### Concurrency: generate-then-lock
AI players call LLM **outside** the lock, then acquire `asyncio.Lock` only to write result + broadcast. If phase changed during LLM generation, result is discarded. One lock per game, held for microseconds (never during I/O).

### Type pipeline
Pydantic models → OpenAPI → `openapi-typescript` → generated TS types. Run `make codegen` after changing any schema or route signature.

### State machine — three round types

Round types cycle: **Task → Interrogation → Word Chain → Task → ...**. Generated at game start in `state.round_types` via `select_round_types()`.

**Task** (constrained creative prompt, no Q&A):
```
PROMPT (25s) → REVIEW (40s) → ELIMINATION (8s) → next round
```

**Interrogation** (hot seat, LLM synthesis):
```
PROMPT (45s) → NOMINATE (15s) → QUESTION (25s) → RESPOND (30s) → REVIEW (40s) → ELIMINATION (8s) → next round
```

**Word Chain** (word association sub-rounds, no prompt):
```
CHAIN (64s safety timer, 8 sub-rounds × 8s each) → REVIEW (40s) → ELIMINATION (8s) → next round
```

Phase transitions are in `transitions.py`: `start_phase_timer`, `handle_phase_expiry`, `do_prompt_complete`, `do_nominate_complete`, `do_question_complete`, `do_respond_complete`, `do_vote_resolution`, `do_after_elimination`, `do_chain_complete`. Also `initialize_and_start_game` (shared by host-start and matchmaking). AI scheduler hooks into each transition via `ai_on_phase_change()`.

### Game logic is pure
`game_logic.py` contains pure functions (no I/O, no async). State transitions, vote tallying, game-over checks, assignment logic, client state sanitization. Routes call these under the lock.

### Voting: multi-vote
Players get `min(3, alive_count - 1)` votes during REVIEW phase. Votes are changeable until timer expires. No early-complete for REVIEW.

### Matchmaking
`MatchmakingService` (singleton in `deps.py`) maintains a rolling lobby queue. Players join via `POST /matchmaking/join`, connect to `GET /matchmaking/events` SSE for status. When `mm_min_humans` (default 2) are queued, a countdown fires. After `mm_countdown_seconds` (20s), `_fire_game()` pops the queue, creates a real game, adds AI (random count from `mm_min_total`–`mm_max_total`), and calls `initialize_and_start_game()`. All lobby clients receive `game_assigned` event and redirect. Solo player gets a `mm_solo_timeout_seconds` (45s) grace period before starting with AI companions. Frontend: `/queue` page.

### LLM-powered features
- **Question synthesis** (Interrogation): all submitted questions → LLM → one cohesive cross-examination paragraph. 5s timeout, fallback: numbered list.
- **Verdict summary** (Elimination): one-line dramatic summary after role reveal. 3s timeout, fallback: no verdict.
- **Word association** (Word Chain): each sub-round, AI generates a single-word association via `generate_association()`. Personality-aware style hints. 3s timeout, fallback: `get_fallback_association()` from `word_chain.py`.

## Gotchas

- **Ports**: Backend defaults to **8501**. Frontend runs on **3500**. Next.js rewrites `/api/*` → backend via `next.config.ts`.
- **Windows process cleanup**: `uv run uvicorn --reload` spawns a process tree (uv → reloader → worker). `make down` and the `dev` trap use `taskkill /F /T /PID` to kill the full tree; plain `kill` leaves child processes as zombies holding the port.
- **`from __future__ import annotations`** used in all Python files. Use `datetime.now(UTC)`, never `datetime.utcnow()`.
- **`schemas/` is top-level**: Imported by both `backend/` and `scripts/`. Don't nest under `backend/`.
- **No database**: All state is in-memory. Server restart kills all games. Completed games are recorded to `recordings/{game_id}.json` (toggle with `TELL_RECORD_GAMES=false`).
- **Circular import between ai_scheduler and transitions**: Both import each other's functions inside async functions (not at top level) to avoid circular dependency at module init.
- **AI personalities assigned at game start**: `assign_personalities()` in `ai_scheduler.py` maps player IDs to personalities. Must be called before `on_phase_change()`.
- **Eliminated players see spectator views**: `game/[id]/page.tsx` checks `isAlive` and passes `spectator` prop to phase components.
- **Round-robin assignments** (Interrogation only now): player `i` questions player `(i+1) % len(alive)`. Generated in `assign_question_targets()` — Probe round type is no longer in rotation.
- **Hot-seated player** (Interrogation): nominated player can't submit questions, only responds to synthesis.
- **Word Chain sub-rounds**: The CHAIN phase runs 8 sub-rounds of 8s each inside a background loop (`_start_chain_loop`). A safety timer of 64s also runs. Sub-round winner is chosen by `select_chain_next_word()` (prefers unique words). Next seed = chosen word.
- **Matchmaking join window**: `MatchmakingService._join_window_open` event blocks new joins while a game is being fired. Clears after lobby SSE clients are disconnected.
- **Task prompts use separate pool**: `used_task_prompt_indices` + `last_task_prompt_category` tracked separately from regular prompts. `select_task_prompt()` in `prompts.py`.

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
