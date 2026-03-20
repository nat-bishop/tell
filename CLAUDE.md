# Tell

Multiplayer social deduction game — reverse Turing test. Players join a group where some are AI, some human. Humans play as themselves. AI players try to pass as human. Everyone votes each matchup on who sounds more human. After 5 rounds: big reveal, highest score wins.

## Architecture

```
schemas/          Shared Pydantic models — the contract between backend + frontend
  game_state.py   GamePhase (LOBBY/PROMPT/ACTIVE/RESULTS/GAME_OVER), Player,
                  TellGameState, RoundState, Matchup, BrainTestChallenge, NarratorEntry
  api_models.py   SSE event types + POST request/response models (incl. matchmaking)
  prompts.py      42 task prompts (7 categories) + brain test challenges (multiple-choice)
                  + select_brain_test_challenges()
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
      actions.py      POST join/start/answer/matchup-vote/brain-test-answer
      matchmaking.py  POST /matchmaking/join|leave, GET /matchmaking/status|events
      debug.py        POST /debug/seed (only when TELL_LOG_LEVEL=DEBUG)
  services/
    connection_manager.py  Per-game asyncio.Queue broadcast + event log + recording buffer
    game_repository.py     In-memory game session store
    recorder.py            Writes completed game JSON to recordings/ on game over
    game_logic.py          Pure functions: transitions, matchup vote resolution, scoring,
                           brain test selection, round type cycling,
                           MinigameMeta/MINIGAMES registry, select_next_round_type(),
                           resolve_matchup_votes(), score_brain_test(), check_game_over()
    timer_manager.py       asyncio.Task per phase timer
    transitions.py         Async phase transition sequences (start_phase_timer,
                           handle_phase_expiry, do_prompt_complete, do_active_complete,
                           do_results_complete, _initialize_round(), _start_sub_round_loop(),
                           _start_matchup_loop, _start_brain_test_loop,
                           _fire_narration, initialize_and_start_game)
    ai_scheduler.py        Generate-then-lock AI player scheduling + brain test
                           sub-rounds; on_brain_test_challenge(), on_matchup_challenge()
    matchmaking.py         Rolling lobby: queue, countdown, solo timeout, fire_game
  llm/
    agents.py              PydanticAI: answer, vote, brain test answer, narration
    personalities.py       5 AI personalities with system prompts + vote styles
    prompts.py             NARRATOR_SYSTEM_PROMPT + build_* helpers

tests/
  conftest.py     Fixtures: standard_game (4p, 2h/2ai, PROMPT), game_state/player/round_state factories
  factories.py    Plain functions building Pydantic models with sensible defaults
  test_game_logic.py  Tests for all pure functions in game_logic.py
  test_schemas.py     Tests for schema models, prompt selection, alias generation
  test_routes.py      Integration tests for API routes
  test_services.py    Tests for service layer (transitions, timer, matchmaking)
  test_transitions.py Tests for async phase transition sequences

frontend/src/
  app/page.tsx             Landing: "play" (→ queue) + "private game" (→ create)
  app/queue/page.tsx       Matchmaking queue: name input, SSE lobby updates, redirect
  app/game/[id]/page.tsx   Game page: join → renders FacilityGameContent after join
  facility/                Verification Facility UI — diegetic themed rewrite
    zones.ts               PanelZone interface + ZONES layout registry (9 named zones)
    Panel.tsx              Frosted-glass panel at absolute zone position; enter/exit anims
    FacilityBackground.tsx CSS atmospheric background (radial gradients, ambient glow)
    FacilityProvider.tsx   React context: transition state + snapTo
    useTransitionMachine.ts State machine: idle → lockdown(300ms) → reconfigure → boot(400ms) → idle
    FacilityScene.tsx      Phase router → facility phase components; `active`/`results` dispatch
                           by `roundType` (task → FacilityMatchup, brain_test → FacilityBrainTest);
                           hidden during lockdown/reconfigure
    FacilityGameContent.tsx Main orchestrator: cold open, transition timing, background, Narration
    subjectColors.ts       Player color palette (6 named hues)
    usePlayerColors.ts     Hook: maps player IDs → color values
    phaseLayouts.ts        `getPhaseLayout(phase, roundType)` — two-tier lookup:
                           SHARED_LAYOUTS (lobby/prompt/game_over) then
                           ROUND_LAYOUTS[roundType][phase] for active/results
    FacilityTimer.tsx      Timer as facility gauge with warning/urgent/critical states
    FacilityNarration.tsx  PA ticker at bottom of viewport, auto-dismiss after 6s
    HudPanel.tsx           Player info readout (replaces PlayerBar)
    TransitionOverlay.tsx  Diegetic interstitial in wall-display panel; 5 voice archetypes cycling
                           by round; shows during "reconfigure" state only
    phases/
      FacilityLobby.tsx    wall-display (title + player list) + desk-terminal (host controls)
      FacilityPrompt.tsx   wall-display (prompt) + desk-terminal (textarea input)
      FacilityBrainTest.tsx  active + results phases for brain_test roundType
      FacilityMatchup.tsx  active phase for task roundType: left-screen + right-screen + readout
      FacilityGameOver.tsx full-screen panel: headline, scoreboard, narration, play again
  components/              Shared primitives — used by app screens and facility phases
    Stage.tsx              Full-screen centered layout wrapper
    SystemText.tsx         Mono-font system text (IBM Plex Mono)
    GameTextarea.tsx       Auto-resize textarea with Enter-to-submit
  hooks/useGameStore.ts    Zustand store — all game state + SSE event handlers;
                           narrationText/narrationTrigger; totalRounds; winnerIds;
                           generic round fields: subRoundIndex, subRoundPayload,
                           roundPayload, roundResults, roundScores
  hooks/useGameEvents.ts   EventSource connection → store dispatch
  hooks/useTimer.ts        Client-side countdown from server deadline
  api/actions.ts           Typed POST helpers (incl. submitMatchupVote,
                           submitBrainTestAnswer, matchmaking)
  api/events.ts            SSE client with typed event routing
  api/matchmaking-events.ts  SSE client for matchmaking lobby (LobbyStatus, GameAssigned)
  api/client.ts            API_URL config + base fetch wrapper
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

Frontend env var:
- `NEXT_PUBLIC_API_URL` — backend URL for REST + SSE (default: `http://localhost:8501`). In production behind a reverse proxy, set to the backend origin or `/api`.

Optional overrides via `TELL_*` env vars (see `config.py`):
- `TELL_LOG_LEVEL=DEBUG` — enables debug logging **and** mounts debug routes (`/debug/seed`, etc.)
- `TELL_LOGFIRE_ENABLED=true` — Pydantic Logfire tracing
- `TELL_CORS_ORIGINS` — comma-separated allowed origins (default: `*`). Set for production.
- `TELL_AI_MODEL`, `TELL_AI_RETRIES` — override AI model and retry count
- `TELL_PROMPT_DURATION`, `TELL_TASK_PROMPT_DURATION`, `TELL_PROMPT_READING_DURATION` — prompt phase timing
- `TELL_BRAIN_TEST_DURATION`, `TELL_BRAIN_TEST_CHALLENGE_DURATION`, `TELL_BRAIN_TEST_CHALLENGES`, `TELL_BRAIN_TEST_RESULTS_DURATION` — brain test timing
- `TELL_MATCHUP_DURATION`, `TELL_MATCHUP_CHALLENGE_DURATION` — matchup safety timer and per-sub-round duration
- `TELL_TOTAL_ROUNDS` — override fixed game length (default 5)
- `TELL_MIN_HUMANS`, `TELL_MAX_PLAYERS`, `TELL_MIN_AI`, `TELL_MAX_AI` — player count limits
- `TELL_RECORD_GAMES=false` — disable writing game recordings to `recordings/`
- `TELL_MM_MIN_HUMANS`, `TELL_MM_MAX_HUMANS`, `TELL_MM_COUNTDOWN`, `TELL_MM_SOLO_TIMEOUT`, `TELL_MM_MIN_TOTAL`, `TELL_MM_MAX_TOTAL` — matchmaking thresholds (see `config.toml [matchmaking]`)

**Logging convention**: INFO for game actions (player_joined, answer_submitted, vote_cast, phase transitions). DEBUG for SSE internals (sse_connected, sse_replay, queue ops).

## Critical Patterns

### Real-time: SSE, not WebSockets
GET-based `EventSource` for persistent game stream, POST for actions. Each client gets an `asyncio.Queue`. Server broadcasts `GameEvent`s to all queues. Events carry monotonic `seq` numbers. Reconnection replays missed events from a 200-event log, or falls back to full `state_sync`.

### Concurrency: generate-then-lock
AI players call LLM **outside** the lock, then acquire `asyncio.Lock` only to write result + broadcast. If phase changed during LLM generation, result is discarded. One lock per game, held for microseconds (never during I/O).

### Type pipeline
Pydantic models → OpenAPI → `openapi-typescript` → generated TS types. Run `make codegen` after changing any schema or route signature. SSE event types in `schemas/api_models.py` use `Literal["event_name"]` for the `event_type` field — ensures exhaustive matching on the frontend.

### State machine — two round types

`GamePhase` has 5 values: `LOBBY, PROMPT, ACTIVE, RESULTS, GAME_OVER`. `ACTIVE` and `RESULTS` are generic — behavior dispatches by `round_type`. Phases never grow; adding a minigame only requires a `MinigameMeta` registry entry.

Round types are selected dynamically via `get_next_round_type(state)` (wraps `select_next_round_type`) — not pre-generated. `state.round_types` is a growing list (appended per round). Selection rule: no consecutive repeat. `MinigameMeta` in `game_logic.py` stores `min_players`, `has_prompt`, `has_results`, `active_interstitial`, `results_interstitial` per type. Two types: Task (Matchup), Brain Test (Quick Draw).

**Task / Matchup** (constrained creative prompt, 1v1 voting):
```
PROMPT (45s + 10s reading) → ACTIVE (matchup sub-round loop, 12s each) → RoundResultsEvent → next round
```
Players answer the prompt, then are paired for head-to-head voting. Each sub-round broadcasts `SubRoundEvent(round_type="task", ...)`. All players vote on which answer sounds more human. Matchup winner earns +1 point. Odd player out gets a bye. No results phase (`has_results=False`).

**Brain Test / Quick Draw** (multiple-choice challenges, scored by correctness):
```
ACTIVE (85s safety timer, 5 challenges × 15s each) → RoundResultsEvent → RESULTS (15s) → next round
```
Each challenge broadcasts `SubRoundEvent(round_type="brain_test", ...)` with question/options. Players select an option; scoring is pure correctness (`selected_index == correct_index`, 1 point). Results phase used (`has_results=True`).

**After 5 rounds** (`state.round_number == state.total_rounds`):
```
FinalRevealEvent → GameOverEvent
```
All roles revealed simultaneously with final scores. Highest scorer wins. Ties possible. Winner determined by `check_game_over()` in `game_logic.py`.

Phase transitions are in `transitions.py`: `start_phase_timer`, `handle_phase_expiry`, `do_prompt_complete`, `do_active_complete` (dispatches by round_type), `do_results_complete`, `_initialize_round()`, `_start_sub_round_loop()`, `_fire_narration`. Also `initialize_and_start_game` (shared by host-start and matchmaking) — delegates to `_start_next_round()`. AI scheduler hooks in via `on_phase_change()`, `on_matchup_challenge()`, `on_brain_test_challenge()`.

### Scoring
- **Matchup**: Each voter picks the answer that sounds more human. Winning side gets +1 point per matchup. `resolve_matchup_votes()` returns `(state, matchup_results_list, scores_dict)`.
- **Brain Test**: Pure correctness — `selected_index == correct_index` → +1 point per challenge.
- Running scores in `Player.score` (int). `scores` dict (player_id → score) carried on `StateSyncEvent`, `RoundResultsEvent`, and `GameOverEvent`.
- Game over after `total_rounds` (default 5). Winner = highest score; ties produce multiple `winner_ids`.

### Game logic is pure
`game_logic.py` contains pure functions (no I/O, no async). State transitions, vote tallying, game-over checks, assignment logic, client state sanitization. Routes call these under the lock.

### Matchmaking
`MatchmakingService` (singleton in `deps.py`) maintains a rolling lobby queue. Players join via `POST /matchmaking/join`, connect to `GET /matchmaking/events` SSE for status. When `mm_min_humans` (default 2) are queued, a countdown fires. After `mm_countdown_seconds` (20s), `_fire_game()` pops the queue, creates a real game, adds AI (random count from `mm_min_total`–`mm_max_total`), and calls `initialize_and_start_game()`. All lobby clients receive `game_assigned` event and redirect. Solo player gets a `mm_solo_timeout_seconds` (45s) grace period before starting with AI companions. Frontend: `/queue` page.

### LLM-powered features
- **Narrator** (persistent show host): `generate_narration(trigger, context)` fires as a non-blocking background task at: `game_start`, `post_submissions`, `between_rounds`, `game_over`. Dry, literary voice (the robot running the test). 3s timeout for most triggers, 5s for `game_over`. Result stored in `state.narrator_context` (last 5 kept for continuity) and broadcast as `NarrationEvent`. Never blocks game flow. `_fire_narration()` + `_build_narrator_context()` in `transitions.py`.
- **AI answers** (PROMPT): AI players generate answers trying to pass as human. System prompt is personality-driven via `build_system_prompt()`.
- **AI matchup votes** (ACTIVE / task): AI votes on which answer sounds more human using `decide_vote()`.
- **AI brain test** (ACTIVE / brain_test): AI selects a multiple-choice option via stateless `brain_test_agent`.

## Gotchas

- **Ports**: Backend defaults to **8501**. Frontend runs on **3500**. Frontend talks directly to backend (no proxy) — CORS allows it.
- **Windows process cleanup**: `uv run uvicorn --reload` spawns a process tree (uv → reloader → worker). `make down` and the `dev` trap use `taskkill /F /T /PID` to kill the full tree; plain `kill` leaves child processes as zombies holding the port.
- **`from __future__ import annotations`** used in all Python files. Use `datetime.now(UTC)`, never `datetime.utcnow()`.
- **`schemas/` is top-level**: Imported by both `backend/` and `scripts/`. Don't nest under `backend/`.
- **No database**: All state is in-memory. Server restart kills all games. Completed games are recorded to `recordings/{game_id}.json` (toggle with `TELL_RECORD_GAMES=false`).
- **Circular import between ai_scheduler and transitions**: Both import each other's functions inside async functions (not at top level) to avoid circular dependency at module init.
- **AI personalities assigned at game start**: `assign_personalities()` in `ai_scheduler.py` maps player IDs to personalities. Must be called before `on_phase_change()`.
- **Matchup pairings**: Players paired in order — player `i` vs player `i+1`. Odd player out gets `bye_player_id` on `RoundState` and skips the current matchup loop iteration. Pairs determined in `transition_to_matchup()` in `game_logic.py`.
- **Sub-round loops**: `_start_matchup_loop` and `_start_brain_test_loop` background tasks cycle sequentially through sub-rounds. Each iteration broadcasts a `SubRoundEvent(round_type, sub_round_index, payload)`. Dispatched by `_start_sub_round_loop()`. When all sub-rounds complete, calls `do_active_complete()`.
- **`do_active_complete` dispatches by round_type**: Scores the round, broadcasts `RoundResultsEvent`, then either transitions to `RESULTS` phase (if `meta.has_results`) or calls `_start_next_round()` directly.
- **`do_results_complete`**: Ends the RESULTS phase — checks game over or starts next round. Only reached for round types with `has_results=True` (Brain Test).
- **Brain test scoring**: `score_brain_test()` in `game_logic.py`. Pure correctness: `selected_index == correct_index` awards 1 point. Responses store an int (selected option index), not a string.
- **Action routes check ACTIVE + round_type**: `/matchup-vote` requires `phase == ACTIVE` and `round_type == TASK`; `/brain-test-answer` requires `phase == ACTIVE` and `round_type == BRAIN_TEST`.
- **No elimination**: No `ELIMINATION` phase. No spectator mode. All players participate all 5 rounds.
- **Game ends by round count**: `check_game_over()` returns `None` until `state.round_number >= state.total_rounds`. Then returns winner info. Ties produce multiple `winner_ids`.
- **FinalReveal before GameOver**: `_do_game_over()` broadcasts `FinalRevealEvent` (roles + scores revealed) then `GameOverEvent`. Frontend shows reveal screen first.
- **total_rounds is 5**: Fixed game length — not a safety cap. No early exit by player count.
- **Task prompts use separate pool**: `used_task_prompt_indices` + `last_task_prompt_category` tracked separately. `select_task_prompt()` in `prompts.py`.
- **Round types selected dynamically**: `get_next_round_type(state)` (wraps `select_next_round_type`) called at the start of each round. `state.round_types` grows as rounds are played. Only rule: no consecutive repeat.
- **Matchmaking join window**: `MatchmakingService._join_window_open` event blocks new joins while a game is being fired. Clears after lobby SSE clients are disconnected.
- **Narrator fires non-blocking**: `_fire_narration()` uses `asyncio.create_task()`. It acquires the lock only for the state read and write — LLM call is outside the lock. If the game ends before the narration resolves, it exits silently.

## Code Conventions

- **Python**: Pydantic v2 models, type hints, `ruff` formatting (line-length 100)
- **TypeScript**: Strict mode, path aliases (`@/*` → `src/*`), Zustand for state
- **Fonts**: Cormorant (literary content), Cormorant SC (character names), IBM Plex Mono (system text)
- **Color**: `--page` `--ink` `--dim` `--rule` `--surface` `--raised` `--cold` `--cold-glow` `--glow`. `--warm` (#E07A5F) reserved for timer warning, vote selection, and "human" reveals.
- **Animation**: CSS only, no libraries. `animate-fade-in`, `animate-headline-reveal`, `animate-panel-enter`, `animate-panel-exit`.
- **Facility CSS classes**: `facility-viewport` (fixed full-screen, grid overlay), `facility-vignette` (edge darkening), `facility-panel` (frosted glass + CRT scanline overlay via `backdrop-filter`). Defined in `globals.css`.
- **Textarea submit**: All gameplay textareas submit on Enter (no Shift). Auto-resize via `scrollHeight`. `maxLength` enforced per field.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — real-time system, state machine, AI scheduling
- [Game Design](docs/GAME_DESIGN.md) — mechanics, prompts, design rationale
