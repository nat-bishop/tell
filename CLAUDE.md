# Tell

Multiplayer social deduction game — reverse Turing test meets Among Us. Players join a group where some are AI, some human. Everyone pretends to be a robot. Each round: answer a prompt, question each other through structured minigames, vote on who's human.

## Architecture

```
schemas/          Shared Pydantic models — the contract between backend + frontend
  game_state.py   GamePhase, Player, TellGameState, QuestionEntry, RoundState,
                  ChainRound, BrainTestChallenge, NarratorEntry, ActiveAbility
  api_models.py   SSE event types + POST request/response models (incl. matchmaking)
  prompts.py      30 game prompts (5 categories) + 42 task prompts (7 categories)
                  + 19 brain test challenges (4 types) + select_brain_test_challenges()
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
      actions.py      POST join/start/answer/question/respond/nominate/vote/
                      chain-word/comedy-vote/brain-test-answer/discussion-message
      matchmaking.py  POST /matchmaking/join|leave, GET /matchmaking/status|events
  services/
    connection_manager.py  Per-game asyncio.Queue broadcast + event log + recording buffer
    game_repository.py     In-memory game session store
    recorder.py            Writes completed game JSON to recordings/ on game over
    game_logic.py          Pure functions: transitions, vote resolution, validation,
                           word chain/brain test selection, round type cycling,
                           resolve_comedy_votes(), score_brain_test(),
                           determine_challenge_winner()
    timer_manager.py       asyncio.Task per phase timer
    transitions.py         Async phase transition sequences (start_phase_timer,
                           handle_phase_expiry, do_*_complete helpers,
                           do_chain_complete, do_brain_test_complete, do_after_brain_test,
                           _trigger_ability_on_review, _fire_narration,
                           initialize_and_start_game)
    ai_scheduler.py        Generate-then-lock AI player scheduling + chain/brain test
                           sub-rounds; on_brain_test_challenge();
                           _ai_discussion_task()
    matchmaking.py         Rolling lobby: queue, countdown, solo timeout, fire_game
  llm/
    agents.py              PydanticAI: answer, question, response, vote, nomination,
                           synthesis, verdict, word association, narration,
                           discussion (generate_discussion_message)
    personalities.py       5 AI personalities with system prompts + question styles
    prompts.py             NARRATOR_SYSTEM_PROMPT + build_* helpers incl.
                           build_discussion_prompt()

tests/
  conftest.py     Fixtures: standard_game (4p, 2h/2ai, PROMPT), game_state/player/round_state factories
  factories.py    Plain functions building Pydantic models with sensible defaults
  test_game_logic.py  Tests for all pure functions in game_logic.py
  test_schemas.py     Tests for schema models, prompt selection, alias generation
  test_routes.py      Integration tests for API routes
  test_services.py    Tests for service layer (transitions, timer, matchmaking)
  test_transitions.py Tests for async phase transition sequences
  test_word_chain.py  Tests for word chain logic and selection

frontend/src/
  app/page.tsx             Landing: "play" (→ queue) + "private game" (→ create)
  app/queue/page.tsx       Matchmaking queue: name input, SSE lobby updates, redirect
  app/game/[id]/page.tsx   Game page: join → phase routing + cold open sequence on start
  components/
    AnswerCard.tsx         Shared answer-first card (alias pinned to bottom, button/div)
    PlayerBar.tsx          Persistent player strip during gameplay; DOUBLE VOTE badge
    VoteOverlay.tsx        Multi-vote selection overlay (up to 3 votes)
    PhaseInterstitial.tsx  Phase transition overlay — 5 rotating robot voice archetypes,
                           directive subtitles, spectator variants, situation lines;
                           ability announcements
    Narration.tsx          Narrator overlay (Narration) + inline for game over
                           (NarrationInline); auto-dismiss after 6s, game_over persists
    BrainTestPhase.tsx     BRAIN_TEST/BRAIN_TEST_RESULTS — challenge input + scored results
    WordChainPhase.tsx     CHAIN phase — seed word display, growing chain, word input
    QuestionPhase.tsx      QUESTION phase — shows target's answer, write follow-up
    RespondPhase.tsx       RESPOND phase — answer received questions
    NominatePhase.tsx      NOMINATE phase — pick who to interrogate
    ReviewPhase.tsx        REVIEW phase — 3 sub-phases (REVEAL/DISCUSS/VOTE) via
                           useSubPhase(); DiscussionChat + ScanResults components
    Prompt.tsx, Elimination.tsx, GameOver.tsx, Lobby.tsx
    GameTextarea.tsx   Shared textarea with auto-resize + Enter-to-submit
    LabeledCard.tsx    Card wrapper with label
    Stage.tsx, Timer.tsx, Dialogue.tsx, SystemText.tsx
  hooks/useGameStore.ts    Zustand store — all game state + SSE event handlers;
                           narrationText/narrationTrigger; brain test state + scores;
                           totalRounds/lastEliminationWasHuman/humansEliminated/aisEliminated;
                           discussionMessages/myDiscussionCount/discussStartsAt/voteStartsAt;
                           activeAbility/scanResults
  hooks/useGameEvents.ts   EventSource connection → store dispatch
  hooks/useTimer.ts        Client-side countdown from server deadline
  api/actions.ts           Typed POST helpers (incl. submitChainWord, castComedyVote,
                           submitBrainTestAnswer, sendDiscussionMessage, matchmaking)
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
- `TELL_MM_MIN_HUMANS`, `TELL_MM_COUNTDOWN`, `TELL_MM_SOLO_TIMEOUT`, `TELL_MM_MIN_TOTAL`, `TELL_MM_MAX_TOTAL` — matchmaking thresholds (see `config.toml [matchmaking]`)
- `TELL_CHAIN_DURATION`, `TELL_CHAIN_SUB_ROUND_DURATION`, `TELL_CHAIN_SUB_ROUNDS` — word chain timing
- `TELL_BRAIN_TEST_DURATION`, `TELL_BRAIN_TEST_CHALLENGE_DURATION`, `TELL_BRAIN_TEST_CHALLENGES`, `TELL_BRAIN_TEST_RESULTS_DURATION` — brain test timing
- `TELL_RECORD_GAMES=false` — disable writing game recordings to `recordings/`

**Logging convention**: INFO for game actions (player_joined, answer_submitted, vote_cast, phase transitions). DEBUG for SSE internals (sse_connected, sse_replay, queue ops).

## Critical Patterns

### Real-time: SSE, not WebSockets
GET-based `EventSource` for persistent game stream, POST for actions. Each client gets an `asyncio.Queue`. Server broadcasts `GameEvent`s to all queues. Events carry monotonic `seq` numbers. Reconnection replays missed events from a 200-event log, or falls back to full `state_sync`.

### Concurrency: generate-then-lock
AI players call LLM **outside** the lock, then acquire `asyncio.Lock` only to write result + broadcast. If phase changed during LLM generation, result is discarded. One lock per game, held for microseconds (never during I/O).

### Type pipeline
Pydantic models → OpenAPI → `openapi-typescript` → generated TS types. Run `make codegen` after changing any schema or route signature. SSE event types in `schemas/api_models.py` use `Literal["event_name"]` for the `event_type` field — ensures exhaustive matching on the frontend.

### State machine — four round types

Round types cycle: **Task → Word Chain → Brain Test → Interrogation → Task → ...**. Generated at game start in `state.round_types` via `select_round_types()`.

**Task** (constrained creative prompt, no Q&A):
```
PROMPT (25s) → REVIEW (40s) → ELIMINATION (12s) → next round
```

**Word Chain** (word association sub-rounds, no prompt):
```
CHAIN (64s safety timer, 8 sub-rounds × 8s each) → REVIEW (40s) → ELIMINATION (12s) → next round
```

**Brain Test** (competitive challenges, no voting):
```
BRAIN_TEST (75s safety timer, 5 challenges × 12s each) → BRAIN_TEST_RESULTS (15s) → next round
```
Brain Test has no voting or elimination. Challenges scored: `trick`/`pattern` types use fuzzy match against `correct_answer` (1 point), `estimation`/`common_knowledge` types award 1 point for a unique answer. Winner receives a random ability (PARTIAL SCAN or DOUBLE VOTE). Results + scores + ability broadcast via `BrainTestResultsEvent`; ability announced via `AbilityAwardedEvent`.

**Interrogation** (hot seat, LLM synthesis):
```
PROMPT (45s) → NOMINATE (15s) → QUESTION (25s) → RESPOND (30s) → REVIEW (40s) → ELIMINATION (12s) → next round
```

**REVIEW sub-phases** (server-driven, no new `GamePhase` enum values):
```
REVEAL (0-8s) → DISCUSS (8-26s) → VOTE (26-40s)
```
`PhaseChangedEvent` carries `discuss_starts_at` and `vote_starts_at` timestamps. Frontend (`useSubPhase()` hook in `ReviewPhase.tsx`) transitions locally. During DISCUSS: live `DiscussionMessageEvent` chat (screenplay aesthetic, no bubbles), PARTIAL SCAN results shown if applicable. During VOTE: standard multi-vote UI. AI players send 1-2 chat messages (10-22s window) then vote (28-37s window).

Phase transitions are in `transitions.py`: `start_phase_timer`, `handle_phase_expiry`, `do_prompt_complete`, `do_nominate_complete`, `do_question_complete`, `do_respond_complete`, `do_vote_resolution`, `do_after_elimination`, `do_chain_complete`, `do_brain_test_complete`, `do_after_brain_test`, `_trigger_ability_on_review`. Also `initialize_and_start_game` (shared by host-start and matchmaking). AI scheduler hooks into each transition via `ai_on_phase_change()`.

### Game logic is pure
`game_logic.py` contains pure functions (no I/O, no async). State transitions, vote tallying, game-over checks, assignment logic, client state sanitization. Routes call these under the lock.

### Voting: multi-vote
Players get `min(3, alive_count - 1)` votes during the VOTE sub-phase of REVIEW. Votes are changeable until timer expires. No early-complete for REVIEW. DOUBLE VOTE ability doubles the holder's vote weight in `resolve_votes()`.

### Matchmaking
`MatchmakingService` (singleton in `deps.py`) maintains a rolling lobby queue. Players join via `POST /matchmaking/join`, connect to `GET /matchmaking/events` SSE for status. When `mm_min_humans` (default 2) are queued, a countdown fires. After `mm_countdown_seconds` (20s), `_fire_game()` pops the queue, creates a real game, adds AI (random count from `mm_min_total`–`mm_max_total`), and calls `initialize_and_start_game()`. All lobby clients receive `game_assigned` event and redirect. Solo player gets a `mm_solo_timeout_seconds` (45s) grace period before starting with AI companions. Frontend: `/queue` page.

### LLM-powered features
- **Question synthesis** (Interrogation): all submitted questions → LLM → one cohesive cross-examination paragraph. 5s timeout, fallback: numbered list.
- **Verdict summary** (Elimination): one-line dramatic summary after role reveal. 3s timeout, fallback: no verdict.
- **Word association** (Word Chain): each sub-round, AI generates a single-word association via `generate_association()`. Personality-aware style hints. 3s timeout, fallback: `get_fallback_association()` from `word_chain.py`.
- **Discussion messages** (REVIEW DISCUSS sub-phase): AI players send 1-2 messages via `generate_discussion_message()` reusing `ai_agent` + conversation history. Scheduled by `_ai_discussion_task()` in `ai_scheduler.py`. Rate limit: 3 msgs/player, 120 chars max. Tracked in `_discussion_messages` dict in scheduler for AI chat context.
- **Narrator** (persistent show host): `generate_narration(trigger, context)` fires as a non-blocking background task at: `game_start`, `post_submissions`, `between_rounds`, `game_over`. Dry, literary voice (the robot running the test). 3s timeout for most triggers, 5s for `game_over`. Result stored in `state.narrator_context` (last 5 kept for continuity) and broadcast as `NarrationEvent`. Never blocks game flow. `_fire_narration()` + `_build_narrator_context()` in `transitions.py`.

## Gotchas

- **Ports**: Backend defaults to **8501**. Frontend runs on **3500**. Frontend talks directly to backend (no proxy) — CORS allows it.
- **Windows process cleanup**: `uv run uvicorn --reload` spawns a process tree (uv → reloader → worker). `make down` and the `dev` trap use `taskkill /F /T /PID` to kill the full tree; plain `kill` leaves child processes as zombies holding the port.
- **`from __future__ import annotations`** used in all Python files. Use `datetime.now(UTC)`, never `datetime.utcnow()`.
- **`schemas/` is top-level**: Imported by both `backend/` and `scripts/`. Don't nest under `backend/`.
- **No database**: All state is in-memory. Server restart kills all games. Completed games are recorded to `recordings/{game_id}.json` (toggle with `TELL_RECORD_GAMES=false`).
- **Circular import between ai_scheduler and transitions**: Both import each other's functions inside async functions (not at top level) to avoid circular dependency at module init.
- **AI personalities assigned at game start**: `assign_personalities()` in `ai_scheduler.py` maps player IDs to personalities. Must be called before `on_phase_change()`.
- **Eliminated players see spectator views**: `game/[id]/page.tsx` checks `isAlive` and passes `spectator` prop to phase components.
- **Round-robin assignments** (Interrogation only): player `i` questions player `(i+1) % len(alive)`. Generated in `assign_question_targets()`.
- **Hot-seated player** (Interrogation): nominated player can't submit questions, only responds to synthesis.
- **Word Chain sub-rounds**: The CHAIN phase runs 8 sub-rounds of 8s each inside a background loop (`_start_chain_loop`). A safety timer of 64s also runs. Sub-round winner is chosen by `select_chain_next_word()` (prefers unique words). Next seed = chosen word.
- **Brain Test sub-rounds**: BRAIN_TEST mirrors the Word Chain architecture — `_start_brain_test_loop` background task cycles through 5 challenges at 12s each. Safety timer 75s. AI answers via `on_brain_test_challenge()` → `_ai_brain_test_task()`. No elimination; `do_after_brain_test()` starts the next round directly.
- **Brain test scoring**: `score_brain_test()` in `game_logic.py`. `trick`/`pattern` challenges: `_score_with_answer()` using `_fuzzy_match()` (lowercased, stripped). `estimation`/`common_knowledge`: `_score_by_uniqueness()` (unique answer = 1 point). Winner picked by `determine_challenge_winner()`. Results not injected into AI prompts for subsequent rounds.
- **Abilities lifecycle**: Assigned in `do_brain_test_complete()` → stored in `state.active_ability` → announced via `AbilityAwardedEvent` and PhaseInterstitial → triggered at REVIEW start by `_trigger_ability_on_review()` in `transitions.py` → cleared in `_start_next_round()`. Only one ability active at a time.
- **PARTIAL SCAN**: Triggered automatically when REVIEW starts. Picks 2 random alive players (not the holder): one true role, one random (50/50 correct). Results shuffled. Broadcast via `ScanResultEvent`. Shown in `ScanResults` component at top of DISCUSS sub-phase.
- **DOUBLE VOTE**: Holder's votes count 2× in `resolve_votes()`. Badge shown in `PlayerBar.tsx`.
- **Discussion sub-phases**: REVIEW has no new `GamePhase` values. `PhaseChangedEvent` carries `discuss_starts_at` and `vote_starts_at` ISO timestamps. `useSubPhase()` hook in `ReviewPhase.tsx` drives local transitions. `discussion_counts` on `RoundState` enforces 3-message rate limit per player (validated in the route). AI discussion scheduled in `_ai_discussion_task()`; AI chat context tracked in `_discussion_messages[game_id]` dict (keyed by player_id).
- **Comedy Cup**: During REVIEW, players can cast one comedy vote (`POST /{game_id}/comedy-vote`) alongside their deduction votes. `resolve_comedy_votes()` in `game_logic.py`. Winner broadcast via `ComedyWinnerEvent` at vote resolution. Shown in Elimination step 5 alongside verdict. Can vote for self.
- **Narrator fires non-blocking**: `_fire_narration()` uses `asyncio.create_task()`. It acquires the lock only for the state read and write — LLM call is outside the lock. If the game ends before the narration resolves, it exits silently.
- **Elimination is 12s** (was 8s). 5-step reveal sequence in `Elimination.tsx` with a "beat" gap. Step 1 shows the vote map (who voted for whom).
- **Matchmaking join window**: `MatchmakingService._join_window_open` event blocks new joins while a game is being fired. Clears after lobby SSE clients are disconnected.
- **Task prompts use separate pool**: `used_task_prompt_indices` + `last_task_prompt_category` tracked separately from regular prompts. `select_task_prompt()` in `prompts.py`.

## Code Conventions

- **Python**: Pydantic v2 models, type hints, `ruff` formatting (line-length 100)
- **TypeScript**: Strict mode, path aliases (`@/*` → `src/*`), Zustand for state
- **Fonts**: Cormorant (literary content), Cormorant SC (character names), IBM Plex Mono (system text)
- **Color**: `--page` `--ink` `--dim` `--rule` `--surface` `--raised` `--cold`. `--warm` (#B85C38) reserved for timer warning, vote selection, and "human" reveals.
- **Animation**: CSS only, no libraries. `animate-fade-in`, `animate-elimination-reveal`.
- **Textarea submit**: All gameplay textareas submit on Enter (no Shift). Auto-resize via `scrollHeight`. `maxLength` enforced per field.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — real-time system, state machine, AI scheduling
- [Game Design](docs/GAME_DESIGN.md) — mechanics, prompts, design rationale
