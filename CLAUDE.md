# Tell

Multiplayer social deduction game — reverse Turing test. Players join a group where some are AI, some human. Humans play as themselves. AI players try to pass as human. Everyone votes each round on who sounds most human. After 5 rounds: big reveal, highest score wins.

## Architecture

```
schemas/          Shared Pydantic models — the contract between backend + frontend
  game_state.py   GamePhase (LOBBY/PROMPT/ACTIVE/RESULTS/GAME_OVER), Player,
                  TellGameState, RoundState, BrainTestChallenge, WagerQuestion, NarratorEntry
  api_models.py   SSE event types + POST request/response models (incl. matchmaking)
  prompts.py      42 task prompts (7 categories) + brain test challenges (multiple-choice)
                  + select_brain_test_challenges() + wager questions (25 numerical
                  estimation) + select_wager_questions()
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
      actions.py      POST join/start/answer/vote/brain-test-answer/wager-guess/wager-bet
      matchmaking.py  POST /matchmaking/join|leave, GET /matchmaking/status|events
      debug.py        POST /debug/seed (only when TELL_LOG_LEVEL=DEBUG)
  services/
    connection_manager.py  Per-game asyncio.Queue broadcast + event log + recording buffer
    game_repository.py     In-memory game session store
    recorder.py            Writes completed game JSON to recordings/ on game over
    game_logic.py          Pure functions: phase transitions, tally_gallery_votes, scoring,
                           round type cycling, get_next_round_type(), check_game_over(),
                           get_interstitial_hold(), get_phase_duration() (data-driven
                           from handler metadata), build_state_sync, make_*_event helpers
    timer_manager.py       asyncio.Task per phase timer
    transitions.py         Minigame-agnostic async phase sequences (start_phase_timer,
                           handle_phase_expiry, do_prompt_complete, do_active_complete,
                           do_results_complete, _start_next_round, _do_game_over,
                           _fire_narration, initialize_and_start_game)
    ai_scheduler.py        Generate-then-lock scheduling; on_phase_change() handles
                           PROMPT only — ACTIVE scheduling delegated to minigame handlers
    matchmaking.py         Rolling lobby: queue, countdown, solo timeout, fire_game
  minigames/               Plugin package — one handler per round type
    base.py                MinigameMeta dataclass + MinigameHandler interface
    task.py                TaskHandler (gallery vote, score = negative votes received)
    brain_test.py          BrainTestHandler + score_brain_test()
    wager.py               WagerHandler + score_wager()
    __init__.py            MINIGAME_REGISTRY dict + get_handler() + register()
  llm/
    agents.py              PydanticAI: answer, vote, brain test answer, wager guess/bet, narration
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
    usePhaseLayout.ts      Hook: getPhaseLayout(phase, roundType) → PhaseLayout
    FacilityScene.tsx      Phase router → MINIGAME_COMPONENTS registry (record mapping
                           round_type → {Active, Results} component pair); hidden during
                           lockdown/reconfigure
    FacilityGameContent.tsx Main orchestrator: cold open, transition timing, background, Narration
    subjectColors.ts       Player color palette (6 named hues)
    usePlayerColors.ts     Hook: maps player IDs → color values
    phaseLayouts.ts        SHARED_LAYOUTS (lobby/prompt/game_over) +
                           ROUND_LAYOUTS[roundType][phase] for active/results
    FacilityTimer.tsx      Timer as facility gauge with warning/urgent/critical states
    FacilityNarration.tsx  PA ticker at bottom of viewport, auto-dismiss after 6s
    HudPanel.tsx           Player info readout
    TransitionOverlay.tsx  Diegetic interstitial in wall-display panel; 5 voice archetypes cycling
                           by round; shows during "reconfigure" state only
    phases/
      FacilityLobby.tsx    wall-display (title + player list) + desk-terminal (host controls)
      FacilityPrompt.tsx   wall-display (prompt) + desk-terminal (textarea input)
      FacilityVote.tsx     active phase for task roundType: gallery of all answers, tap to vote
      FacilityVoteResults.tsx  results phase for task roundType: vote counts per player
      FacilityBrainTest.tsx  active + results phases for brain_test roundType
<<<<<<< HEAD
      FacilityWager.tsx   active + results phases for wager roundType (number line + betting)
=======
      FacilitySignalPrompt.tsx  custom prompt: fetches per-player phrase, shows constraint
      FacilitySignalActive.tsx  sub-round guessing UI with auto-submit on transition
      FacilitySignalResults.tsx results: phrase/guess/judgment cards per player
>>>>>>> 7889f32 (Add Signal minigame: Drawful-style phrase transformation round type)
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
  api/actions.ts           Typed POST helpers (incl. submitVote,
<<<<<<< HEAD
                           submitBrainTestAnswer, submitWagerGuess, submitWagerBet, matchmaking)
=======
                           submitBrainTestAnswer, submitSignalGuess,
                           getSignalPhrase, matchmaking)
>>>>>>> 7889f32 (Add Signal minigame: Drawful-style phrase transformation round type)
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
<<<<<<< HEAD
- `TELL_WAGER_DURATION`, `TELL_WAGER_SUB_ROUND_DURATION`, `TELL_WAGER_QUESTIONS`, `TELL_WAGER_RESULTS_DURATION` — wager timing
=======
- `TELL_SIGNAL_PROMPT_DURATION`, `TELL_SIGNAL_SUB_ROUND_DURATION`, `TELL_SIGNAL_RESULTS_DURATION`, `TELL_SIGNAL_SAFETY_DURATION` — signal timing
>>>>>>> 7889f32 (Add Signal minigame: Drawful-style phrase transformation round type)
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

### State machine — three round types

`GamePhase` has 5 values: `LOBBY, PROMPT, ACTIVE, RESULTS, GAME_OVER`. `ACTIVE` and `RESULTS` are generic — behavior dispatches via `get_handler(round_type)`. Phases never grow; adding a minigame only requires a new handler registered in `backend/minigames/`.

<<<<<<< HEAD
Round types are selected dynamically via `get_next_round_type(state)` — not pre-generated. `state.round_types` is a growing list (appended per round). Selection rule: no consecutive repeat. Three types: Task (gallery vote), Brain Test (Quick Draw), Wager (estimation + betting).
=======
Round types are selected dynamically via `get_next_round_type(state)` — not pre-generated. `state.round_types` is a growing list (appended per round). Selection rule: no consecutive repeat. Three types: Task (gallery vote), Brain Test (Quick Draw), Signal (Drawful-style).
>>>>>>> 7889f32 (Add Signal minigame: Drawful-style phrase transformation round type)

**Task / Gallery Vote** (creative prompt, everyone votes for who sounds most human):
```
PROMPT (45s + 5s reading) → ACTIVE (all see all answers, tap to vote) → RoundResultsEvent → RESULTS (vote counts) → next round
```
All players vote for one other player who sounds most human. Votes received = negative points (`-1` per vote). Task handler (`task.py`) runs `build_results()` to tally and return score deltas.

**Brain Test / Quick Draw** (multiple-choice challenges, scored by correctness):
```
ACTIVE (85s safety timer, 5 challenges × 15s each) → RoundResultsEvent → RESULTS (15s) → next round
```
Each challenge broadcasts `SubRoundEvent(round_type="brain_test", ...)` with question/options. Players select an option; scoring is pure correctness (`selected_index == correct_index`, +1 point).

<<<<<<< HEAD
**Wager** (numerical estimation + social betting):
```
ACTIVE (100s safety, 3 questions × [GUESS 15s + BET 15s]) → RoundResultsEvent → RESULTS (15s) → next round
```
Each question has two sub-rounds: GUESS (place a marker on a number line) and BET (pick whose guess is closest). Scoring: +1 for closest guess, +1 for betting on a closest guesser. Self-bet allowed. Max 2 per question, 6 total across 3 questions.
=======
**Signal** (Drawful-style: transform a phrase under a constraint, others guess the original):
```
PROMPT (20s + 5s reading — each player gets a secret phrase + shared constraint, submits transformation)
→ ACTIVE (120s safety timer, N sub-rounds × 12s each — one per player)
→ LLM batch-judges all guesses (parallelized)
→ RoundResultsEvent → RESULTS (15s) → next round
```
Each sub-round broadcasts `SubRoundEvent(round_type="signal", ...)` showing one player's transformation. Others guess the original phrase. Scoring: guesser +1 per correct guess; transmitter +1 if >= half of guessers got it right. Signal has a custom PROMPT component (`FacilitySignalPrompt`) that fetches per-player phrases via `GET /signal-phrase`. Guesses submitted via `POST /signal-guess`. LLM judging uses batch Y/N format with `_fuzzy_match` fallback.
>>>>>>> 7889f32 (Add Signal minigame: Drawful-style phrase transformation round type)

**After 5 rounds** (`state.round_number == state.total_rounds`):
```
FinalRevealEvent → GameOverEvent
```
All roles revealed simultaneously with final scores. Highest scorer wins. Ties possible.

Phase transitions are in `transitions.py` (minigame-agnostic): `start_phase_timer`, `handle_phase_expiry`, `do_prompt_complete`, `do_active_complete` (calls `handler.build_results()`, broadcasts `RoundResultsEvent`, then → RESULTS or next round based on `handler.meta.has_results`), `do_results_complete`, `_fire_narration`. Also `initialize_and_start_game` (shared by host-start and matchmaking).

### Minigame handler pattern

Each round type is a `MinigameHandler` subclass in `backend/minigames/`:

```python
class MinigameHandler:
    round_type: RoundType
    meta: MinigameMeta           # min_players, has_prompt, has_results,
                                 # active_interstitial, results_interstitial

    def setup_round(state, settings)  # mutates state in place
    def get_prompt_duration(settings) → int  # default: settings.prompt_duration
    def get_active_duration(settings) → int
    def get_results_duration(settings) → int
    def active_event_extras(state) → dict  # extra fields on PhaseChangedEvent
    async def on_active_start(game_id)  # start sub-round loops, schedule AI
    def build_results(state) → (payload, score_deltas)  # called by do_active_complete
    def build_state_sync_extras(state, player_id) → dict  # reconnection
```

To add a new minigame: create `backend/minigames/mytype.py`, subclass `MinigameHandler`, call `register(MyHandler())` in `backend/minigames/__init__.py`.

### Scoring
- **Task**: Each vote received = **-1 point**. `tally_gallery_votes()` in `game_logic.py`, deltas applied in `TaskHandler.build_results()`.
- **Brain Test**: Pure correctness — `selected_index == correct_index` → +1 per challenge. `score_brain_test()` in `brain_test.py`.
<<<<<<< HEAD
- **Wager**: +1 for closest guess, +1 for betting on a closest guesser. Self-bet allowed. Max 2 per question, 6 total across 3 questions. `score_wager()` in `wager.py`.
=======
- **Signal**: Guesser +1 per correct guess. Transmitter +1 if >= half of guessers got it right. LLM-judged with fuzzy match fallback.
>>>>>>> 7889f32 (Add Signal minigame: Drawful-style phrase transformation round type)
- Running scores in `Player.score` (int). `scores` dict (player_id → score) carried on `StateSyncEvent`, `RoundResultsEvent`, and `GameOverEvent`.
- Game over after `total_rounds` (default 5). Winner = highest score; ties produce multiple `winner_ids`.

### Game logic is pure
`game_logic.py` contains pure functions (no I/O, no async). Phase transitions, vote tallying, game-over checks, sanitization. `get_interstitial_hold()` and `get_phase_duration()` are data-driven from handler metadata via `get_handler()`. Routes call these under the lock.

### Matchmaking
`MatchmakingService` (singleton in `deps.py`) maintains a rolling lobby queue. Players join via `POST /matchmaking/join`, connect to `GET /matchmaking/events` SSE for status. When `mm_min_humans` (default 2) are queued, a countdown fires. After `mm_countdown_seconds` (20s), `_fire_game()` pops the queue, creates a real game, adds AI (random count from `mm_min_total`–`mm_max_total`), and calls `initialize_and_start_game()`. All lobby clients receive `game_assigned` event and redirect. Solo player gets a `mm_solo_timeout_seconds` (45s) grace period before starting with AI companions. Frontend: `/queue` page.

### LLM-powered features
- **Narrator** (persistent show host): `generate_narration(trigger, context)` fires as a non-blocking background task at: `game_start`, `post_submissions`, `between_rounds`, `game_over`. Dry, literary voice (the robot running the test). 3s timeout for most triggers, 5s for `game_over`. Result stored in `state.narrator_context` (last 5 kept for continuity) and broadcast as `NarrationEvent`. Never blocks game flow. `_fire_narration()` + `_build_narrator_context()` in `transitions.py`.
- **AI answers** (PROMPT): AI players generate answers trying to pass as human. System prompt is personality-driven via `build_system_prompt()`.
- **AI votes** (ACTIVE / task): Scheduled by `TaskHandler.on_active_start()` via `_ai_vote_task()`.
- **AI brain test** (ACTIVE / brain_test): Scheduled by `BrainTestHandler._brain_loop()` via `on_brain_test_challenge()`.
<<<<<<< HEAD
- **AI wager guesses** (ACTIVE / wager): Character agent with `WagerGuessResponse` structured output, maintains conversation history. Scheduled by `WagerHandler._wager_loop()` via `on_wager_guess()`.
- **AI wager bets** (ACTIVE / wager): Character agent with `WagerBetResponse` structured output, maintains conversation history. Scheduled via `on_wager_bet()`.
=======
- **AI signal transform** (PROMPT / signal): `_ai_answer_task` detects `round_type == SIGNAL` and uses `build_signal_transform_prompt` instead of `build_answer_prompt`.
- **AI signal guess** (ACTIVE / signal): `on_signal_sub_round()` schedules `_ai_signal_guess_task` for each non-featured AI player.
- **Signal judging** (after all sub-rounds): `judge_signal_guesses()` batch-judges via LLM with Y/N format, parallelized per featured player via `asyncio.gather`.
>>>>>>> 7889f32 (Add Signal minigame: Drawful-style phrase transformation round type)

## Gotchas

- **Ports**: Backend defaults to **8501**. Frontend runs on **3500**. Frontend talks directly to backend (no proxy) — CORS allows it.
- **Windows process cleanup**: `uv run uvicorn --reload` spawns a process tree (uv → reloader → worker). `make down` and the `dev` trap use `taskkill /F /T /PID` to kill the full tree; plain `kill` leaves child processes as zombies holding the port.
- **`from __future__ import annotations`** used in all Python files. Use `datetime.now(UTC)`, never `datetime.utcnow()`.
- **`schemas/` is top-level**: Imported by both `backend/` and `scripts/`. Don't nest under `backend/`.
- **No database**: All state is in-memory. Server restart kills all games. Completed games are recorded to `recordings/{game_id}.json` (toggle with `TELL_RECORD_GAMES=false`).
- **Circular import between ai_scheduler and transitions**: Both import each other's functions inside async functions (not at top level) to avoid circular dependency at module init. Also: `BrainTestHandler._brain_loop` imports `do_active_complete` at runtime for the same reason.
- **AI personalities assigned at game start**: `assign_personalities()` in `ai_scheduler.py` maps player IDs to personalities. Must be called before `on_phase_change()`.
- **Task scoring is negative**: Votes received = **negative** points. Players avoid being the most-suspected human/bot. High score means fewer suspicion votes.
- **Gallery vote route**: `/vote` (not `/matchup-vote`). Requires `phase == ACTIVE` and `round_type == TASK`. Votes are changeable (overwrite allowed).
- **Brain test route**: `/brain-test-answer` requires `phase == ACTIVE` and `round_type == BRAIN_TEST`.
- **Sub-round loop in handler**: `BrainTestHandler._brain_loop` is an `asyncio.Task` started by `on_active_start()`. Each iteration broadcasts `SubRoundEvent`, calls `on_brain_test_challenge()` for AI scheduling, sleeps `sub_duration`. After all challenges, cancels safety timer and calls `do_active_complete`.
- **`do_active_complete` is minigame-agnostic**: Calls `handler.build_results()`, applies score deltas, broadcasts `RoundResultsEvent`, then either → RESULTS (if `meta.has_results`) or next round.
- **`do_results_complete`**: Only reached for round types with `has_results=True`. Checks game over or starts next round.
- **Brain test scoring**: `score_brain_test()` in `brain_test.py`. Pure correctness: `selected_index == correct_index` awards 1 point. Responses store an int, not a string.
- **No elimination**: No spectator mode. All players participate all 5 rounds.
- **Game ends by round count**: `check_game_over()` returns `None` until `state.round_number >= state.total_rounds`.
- **FinalReveal before GameOver**: `_do_game_over()` broadcasts `FinalRevealEvent` (roles + scores revealed) then `GameOverEvent`.
- **total_rounds is 5**: Fixed game length — not a safety cap. No early exit.
- **Task prompts**: `used_prompt_indices` + `last_prompt_category` tracked on `TellGameState`. `select_duel_prompt()` in `prompts.py` (no-repeat, no-same-category).
- **Round types selected dynamically**: `get_next_round_type(state)` called at the start of each round. Only rule: no consecutive repeat.
- **Matchmaking join window**: `MatchmakingService._join_window_open` event blocks new joins while a game is being fired.
- **Narrator fires non-blocking**: `_fire_narration()` uses `asyncio.create_task()`. LLM call is outside the lock. Exits silently if game ends first.
- **MinigameMeta lives in `backend/minigames/base.py`**: Not in `game_logic.py`. `game_logic.py` imports `MINIGAME_REGISTRY` and `get_handler` from `backend.minigames`.
<<<<<<< HEAD
- **FacilityScene uses component registry**: `MINIGAME_COMPONENTS` maps `round_type → {Active, Results}` component pairs. Adding a new frontend round type only requires adding an entry here and a handler entry in `backend/minigames/`.
- **Wager self-bet is allowed**: Unlike gallery vote which rejects self-votes, wager bet route accepts `target_player_id == player_id`.
- **Wager loop controls timing**: No early completion on all-submitted — the wager loop drives sub-round timing.
- **Wager routes validate sub-round phase**: Guess route rejects during bet sub-rounds and vice versa. Routes check `current_sub_round % 2` and `current_sub_round // 2`.
- **Wager bet route validates target has a guess**: `target_player_id` must be in `q.guesses` for the current question. Prevents betting on a player who timed out.
- **`WagerHandler._wager_loop`** imports `do_active_complete` at runtime to avoid circular dep (same pattern as `_brain_loop`).
=======
- **FacilityScene uses component registry**: `MINIGAME_COMPONENTS` maps `round_type → {Active, Results, Prompt?}` component pairs. Signal uses a custom `Prompt` component. Adding a new frontend round type only requires adding an entry here and a handler entry in `backend/minigames/`.
- **Signal phrase route**: `GET /{game_id}/signal-phrase?player_id=X` returns per-player secret phrase + constraint. Only works during PROMPT phase for signal rounds.
- **Signal guess route**: `POST /{game_id}/signal-guess` requires `phase == ACTIVE`, `round_type == SIGNAL`. Featured player cannot guess their own phrase. Overwrites allowed.
- **Signal sub-round loop**: `SignalHandler._signal_loop` iterates `signal_player_order`, broadcasting `SubRoundEvent` per player. After all sub-rounds, calls `_judge_all_guesses` (parallelized LLM) then `do_active_complete`.
- **Signal guesses/judgments keyed by featured_player_id**: Not sub-round index. JSON serializes int keys as strings — player ID avoids this.
- **Signal PROMPT duration is 20s**: Shorter than Task (45s). `get_prompt_duration()` on the handler is used by `_start_next_round` and `get_phase_duration`.
- **Signal prompts are concrete scenarios**: "a dog chasing a squirrel", not idioms. Must be visually evocable for constraint-based transformation.
- **Signal `signal_player_order`**: Snapshot at `setup_round` time. Without this, player list order shifts (disconnect/reconnect) could break sub-round iteration.
>>>>>>> 7889f32 (Add Signal minigame: Drawful-style phrase transformation round type)

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
