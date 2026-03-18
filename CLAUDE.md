# Tell

Multiplayer social deduction game — reverse Turing test meets Among Us. Players join a group where some are AI, some human. Everyone pretends to be a robot. Each round: answer a prompt, question each other through structured minigames, vote on who's human.

## Architecture

```
schemas/          Shared Pydantic models — the contract between backend + frontend
  game_state.py   GamePhase, Player, TellGameState, QuestionEntry, RoundState,
                  BrainTestChallenge, Matchup, NarratorEntry, ActiveAbility
  api_models.py   SSE event types + POST request/response models (incl. matchmaking,
                  MatchupChallengeEvent, MatchupResultsEvent)
  prompts.py      30 game prompts (5 categories) + 42 task prompts (7 categories)
                  + brain test challenges (multiple-choice) + select_brain_test_challenges()
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
                      comedy-vote/brain-test-answer/discussion-message/matchup-vote
      matchmaking.py  POST /matchmaking/join|leave, GET /matchmaking/status|events
  services/
    connection_manager.py  Per-game asyncio.Queue broadcast + event log + recording buffer
    game_repository.py     In-memory game session store
    recorder.py            Writes completed game JSON to recordings/ on game over
    game_logic.py          Pure functions: transitions, vote resolution, validation,
                           brain test selection, round type cycling,
                           MinigameMeta/MINIGAMES registry, select_next_round_type(),
                           resolve_comedy_votes(), resolve_matchup_votes(),
                           generate_matchup_pairs(), score_brain_test(),
                           determine_challenge_winner()
    timer_manager.py       asyncio.Task per phase timer
    transitions.py         Async phase transition sequences (start_phase_timer,
                           handle_phase_expiry, do_*_complete helpers,
                           do_matchup_complete, do_brain_test_complete, do_after_brain_test,
                           _start_matchup_loop, _start_brain_test_loop,
                           _trigger_ability_on_review, _fire_narration,
                           initialize_and_start_game)
    ai_scheduler.py        Generate-then-lock AI player scheduling + brain test and
                           matchup sub-rounds; on_brain_test_challenge();
                           on_matchup_challenge(); _ai_discussion_task()
    matchmaking.py         Rolling lobby: queue, countdown, solo timeout, fire_game
  llm/
    agents.py              PydanticAI: answer, question, response, vote, nomination,
                           synthesis, verdict, narration,
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

frontend/src/
  app/page.tsx             Landing: "play" (→ queue) + "private game" (→ create)
  app/queue/page.tsx       Matchmaking queue: name input, SSE lobby updates, redirect
  app/game/[id]/page.tsx   Game page: join → phase routing + cold open sequence on start
  components/
    AnswerCard.tsx         Shared answer-first card (alias pinned to bottom, button/div)
    PlayerBar.tsx          Persistent player strip during gameplay; DOUBLE VOTE badge
    PhaseInterstitial.tsx  Phase transition overlay — 5 rotating robot voice archetypes,
                           directive subtitles, spectator variants, situation lines;
                           ability announcements
    Narration.tsx          Narrator overlay (Narration) + inline for game over
                           (NarrationInline); auto-dismiss after 6s, game_over persists
    BrainTestPhase.tsx     BRAIN_TEST/BRAIN_TEST_RESULTS — multiple-choice Quick Draw + scored results
    MatchupPhase.tsx       MATCHUP phase — sequential 1v1 split-screen voting for Task rounds
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
                           activeAbility/scanResults; winnerIds; Quick Draw challenge state;
                           matchup state (matchupIndex/Left/Right/Prompt/Results/MyVote/byePlayerId)
  hooks/useGameEvents.ts   EventSource connection → store dispatch
  hooks/useTimer.ts        Client-side countdown from server deadline
  api/actions.ts           Typed POST helpers (incl. castComedyVote,
                           submitBrainTestAnswer, sendDiscussionMessage,
                           submitMatchupVote, matchmaking)
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
- `TELL_BRAIN_TEST_DURATION`, `TELL_BRAIN_TEST_CHALLENGE_DURATION`, `TELL_BRAIN_TEST_CHALLENGES`, `TELL_BRAIN_TEST_RESULTS_DURATION` — brain test timing
- `TELL_MATCHUP_DURATION`, `TELL_MATCHUP_CHALLENGE_DURATION` — task matchup timing
- `TELL_RECORD_GAMES=false` — disable writing game recordings to `recordings/`

**Logging convention**: INFO for game actions (player_joined, answer_submitted, vote_cast, phase transitions). DEBUG for SSE internals (sse_connected, sse_replay, queue ops).

## Critical Patterns

### Real-time: SSE, not WebSockets
GET-based `EventSource` for persistent game stream, POST for actions. Each client gets an `asyncio.Queue`. Server broadcasts `GameEvent`s to all queues. Events carry monotonic `seq` numbers. Reconnection replays missed events from a 200-event log, or falls back to full `state_sync`.

### Concurrency: generate-then-lock
AI players call LLM **outside** the lock, then acquire `asyncio.Lock` only to write result + broadcast. If phase changed during LLM generation, result is discarded. One lock per game, held for microseconds (never during I/O).

### Type pipeline
Pydantic models → OpenAPI → `openapi-typescript` → generated TS types. Run `make codegen` after changing any schema or route signature. SSE event types in `schemas/api_models.py` use `Literal["event_name"]` for the `event_type` field — ensures exhaustive matching on the frontend.

### State machine — three round types

Round types are selected dynamically as each round begins via `select_next_round_type(last_round_type, alive_count)` — not pre-generated. `state.round_types` is a growing list (appended per round). Selection rules: no consecutive repeat, Interrogation requires ≥4 alive, no consecutive non-eliminating rounds. `MinigameMeta` registry in `game_logic.py` stores `min_players` and `has_elimination` per type. Three types: Task, Brain Test (Quick Draw), Interrogation.

**Task** (constrained creative prompt, 1v1 matchup voting):
```
PROMPT (45s) → MATCHUP (120s safety, N pairs × 12s each) → ELIMINATION (15s) → next round
```
Players are shuffled into 1v1 pairs, each with their own prompt. During MATCHUP, `_start_matchup_loop` sequences through pairs via `MatchupChallengeEvent`. Spectators and non-paired players vote LEFT/RIGHT per matchup (`POST /{game_id}/matchup-vote`). Paired players cannot vote on their own matchup. Odd player count → one bye player (skips voting). `resolve_matchup_votes()` eliminates the widest-margin loser across all pairs; random tiebreak if all tied. No REVIEW sub-phases, no Comedy Cup in Task rounds.

**Brain Test / Quick Draw** (multiple-choice challenges, no voting):
```
BRAIN_TEST (85s safety timer, 5 challenges × 15s each) → BRAIN_TEST_RESULTS (15s) → next round
```
Brain Test has no voting or elimination. Each challenge presents a question with multiple-choice options and a `correct_index`. Players select an option; scoring is pure correctness (`selected_index == correct_index`, 1 point). Winner receives a random ability (PARTIAL SCAN or DOUBLE VOTE). Results + scores + ability broadcast via `BrainTestResultsEvent`; ability announced via `AbilityAwardedEvent`.

**Interrogation** (hot seat, LLM synthesis):
```
PROMPT (60s) → NOMINATE (20s) → QUESTION (30s) → RESPOND (35s) → REVIEW (55s) → ELIMINATION (15s) → next round
```

**REVIEW sub-phases** (Interrogation only, server-driven, no new `GamePhase` enum values):
```
REVEAL (0-10s) → DISCUSS (10-33s) → VOTE (33-55s)
```
`PhaseChangedEvent` carries `discuss_starts_at` and `vote_starts_at` timestamps. Frontend (`useSubPhase()` hook in `ReviewPhase.tsx`) transitions locally. During DISCUSS: live `DiscussionMessageEvent` chat (screenplay aesthetic, no bubbles), PARTIAL SCAN results shown if applicable. During VOTE: standard multi-vote UI. AI players send 1-2 chat messages (10-17s delay) then vote (36-50s delay from REVIEW start).

Phase transitions are in `transitions.py`: `start_phase_timer`, `handle_phase_expiry`, `do_prompt_complete`, `do_nominate_complete`, `do_question_complete`, `do_respond_complete`, `do_vote_resolution`, `do_after_elimination`, `do_matchup_complete`, `do_brain_test_complete`, `do_after_brain_test`, `_trigger_ability_on_review`. Also `initialize_and_start_game` (shared by host-start and matchmaking) — delegates to `_start_next_round()` which handles all 3 round types. AI scheduler hooks into each transition via `on_phase_change()`.

### Game logic is pure
`game_logic.py` contains pure functions (no I/O, no async). State transitions, vote tallying, game-over checks, assignment logic, client state sanitization. Routes call these under the lock.

### Voting: two systems
**Interrogation (REVIEW)**: Multi-vote — `min(3, alive_count - 1)` votes per player during VOTE sub-phase (26-55s window). Votes changeable until timer expires. No early-complete. DOUBLE VOTE doubles holder's weight in `resolve_votes()`.

**Task (MATCHUP)**: Left/Right binary vote per matchup sub-round. Only non-paired players vote. DOUBLE VOTE doubles holder's weight in `resolve_matchup_votes()`. Widest-margin loser eliminated; all-tie → random.

### Matchmaking
`MatchmakingService` (singleton in `deps.py`) maintains a rolling lobby queue. Players join via `POST /matchmaking/join`, connect to `GET /matchmaking/events` SSE for status. When `mm_min_humans` (default 2) are queued, a countdown fires. After `mm_countdown_seconds` (20s), `_fire_game()` pops the queue, creates a real game, adds AI (random count from `mm_min_total`–`mm_max_total`), and calls `initialize_and_start_game()`. All lobby clients receive `game_assigned` event and redirect. Solo player gets a `mm_solo_timeout_seconds` (45s) grace period before starting with AI companions. Frontend: `/queue` page.

### LLM-powered features
- **Question synthesis** (Interrogation): all submitted questions → LLM → one cohesive cross-examination paragraph. 5s timeout, fallback: numbered list.
- **Verdict summary** (Elimination): one-line dramatic summary after role reveal. `generate_verdict()` takes no `max_rounds` parameter. 3s timeout, fallback: no verdict.
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
- **Task matchup pairs**: `generate_matchup_pairs()` shuffles alive players into pairs. Odd count → one bye player stored in `round_state.bye_player_id` (excluded from voting). Each pair gets its own prompt from the task pool. `Matchup.votes` is `voter_id → 0/1` (LEFT/RIGHT), not a list. `resolve_matchup_votes()` computes per-player margins; widest-margin loser is eliminated.
- **MATCHUP sub-round loop**: `_start_matchup_loop` background task, same pattern as brain test loop. Each iteration broadcasts `MatchupChallengeEvent`, then calls `on_matchup_challenge()` to schedule AI votes. AI voters (non-pair players) vote randomly (no LLM call), 2-8s delay. Safety timer 120s covers all pairs.
- **Brain Test sub-rounds**: `_start_brain_test_loop` background task cycles through 5 challenges at 15s each. Safety timer 85s. AI answers via `on_brain_test_challenge()` → `_ai_brain_test_task()`. No elimination; `do_after_brain_test()` starts the next round directly.
- **Brain test scoring**: `score_brain_test()` in `game_logic.py`. Pure correctness: `selected_index == correct_index` awards 1 point. Responses store an int (selected option index), not a string. Winner picked by `determine_challenge_winner()`. Results not injected into AI prompts for subsequent rounds.
- **Abilities lifecycle**: Assigned in `do_brain_test_complete()` → stored in `state.active_ability` → announced via `AbilityAwardedEvent` and PhaseInterstitial → triggered at MATCHUP start (Task) or REVIEW start (Interrogation) by `_trigger_ability_on_review()` in `transitions.py` → cleared in `_start_next_round()`. Only one ability active at a time.
- **PARTIAL SCAN**: Triggered at REVIEW start (Interrogation) or MATCHUP start (Task). Sends `ScanResultEvent` only to the holder via `cm.send_to()` — not broadcast. Picks 2 random alive players (not holder): one true role, one random (50/50 correct). Results shuffled. Shown in `ScanResults` component at top of DISCUSS sub-phase.
- **DOUBLE VOTE**: Holder's votes count 2× in both `resolve_votes()` (Interrogation) and `resolve_matchup_votes()` (Task). Badge shown in `PlayerBar.tsx`.
- **Discussion sub-phases**: REVIEW has no new `GamePhase` values. `PhaseChangedEvent` carries `discuss_starts_at` and `vote_starts_at` ISO timestamps. `useSubPhase()` hook in `ReviewPhase.tsx` drives local transitions. `discussion_counts` on `RoundState` enforces 3-message rate limit per player (validated in the route). AI discussion scheduled in `_ai_discussion_task()`; AI chat context tracked in `_discussion_messages[game_id]` dict (keyed by player_id).
- **Comedy Cup**: Interrogation rounds only. During REVIEW VOTE sub-phase, players cast one comedy vote (`POST /{game_id}/comedy-vote`) alongside their deduction votes. `resolve_comedy_votes()` in `game_logic.py`. Winner broadcast via `ComedyWinnerEvent` at vote resolution. Shown in Elimination step 5 alongside verdict. Can vote for self. Not available in Task rounds (no REVIEW phase).
- **Narrator fires non-blocking**: `_fire_narration()` uses `asyncio.create_task()`. It acquires the lock only for the state read and write — LLM call is outside the lock. If the game ends before the narration resolves, it exits silently.
- **Elimination is 15s** (config.toml). 5-step reveal sequence in `Elimination.tsx` with a "beat" gap. Step 1 shows the vote map (who voted for whom) for Interrogation, or the matchup results grid for Task.
- **Matchmaking join window**: `MatchmakingService._join_window_open` event blocks new joins while a game is being fired. Clears after lobby SSE clients are disconnected.
- **Task prompts use separate pool**: `used_task_prompt_indices` + `last_task_prompt_category` tracked separately from regular prompts. `select_task_prompt()` in `prompts.py`.
- **Win conditions are individual, not team**: `check_game_over()` returns `("ai", [])` or `("survivors", [player_ids...])`. `state.winner` is `"ai"` or `"survivors"`; `state.winner_ids` holds the IDs of surviving players. `GameOverEvent` and `StateSyncEvent` carry `winner_ids`. `GameOver.tsx` shows "THE MACHINES WIN" (ai) or "YOU SURVIVE" / "{ALIAS} SURVIVES" / "SURVIVORS" with winners in warm color.
- **max_rounds is a safety cap only**: Default 10 (not 3). Game continues until ≤2 players remain; max_rounds prevents infinite games, not a design mechanic.
- **Round types selected dynamically**: `select_next_round_type(last_round_type, alive_count)` called at the start of each round (not pre-generated). `state.round_types` grows as rounds are played. `initialize_and_start_game` no longer branches on first round type.

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
