# Architecture

## System Overview

```
Human Client A  ── POST /games/{id}/answer ──►  FastAPI
                                                   │
                ◄── SSE: state_sync ───────────────┤  validates, acquires
Human Client B  ◄── SSE: phase_changed ────────────┤  asyncio.Lock, mutates
                                                   │  state, broadcasts to
AI Player       ── internal asyncio task ──────────┘  all queues

GET /games/{id}/events     →  persistent EventSource per client
POST /games/{id}/*         →  actions (join, start, answer, question, respond,
                               nominate, vote, comedy-vote,
                               brain-test-answer, discussion-message)
POST /matchmaking/join|leave  →  matchmaking queue
GET /matchmaking/events    →  matchmaking SSE (lobby_status, game_assigned)
GET /matchmaking/status    →  current lobby state
```

## Module Dependency Rules

```
schemas/ ← backend/services/ ← backend/api/routes/
schemas/ ← backend/llm/
frontend/ is independent (communicates via REST + SSE)
```

`schemas/` is the shared contract. `game_logic.py` is pure (no I/O). `transitions.py` contains the async phase-transition sequences shared by routes and the AI scheduler, including `initialize_and_start_game` (used by both host-start and matchmaking). Routes handle HTTP + locking + broadcasting.

## Real-Time: SSE

Each connected client gets an `asyncio.Queue[GameEvent | None]`. The `ConnectionManager` maintains per-game dicts of queues and broadcasts events to all.

**Event flow**: Route validates action → acquires per-game `asyncio.Lock` → mutates `TellGameState` → creates `GameEvent` with monotonic `seq` → broadcasts to all queues → releases lock.

**Reconnection**: Every event logged to a per-game `deque(maxlen=200)`. On `EventSource` reconnect, client sends `last_seq` query param. Server replays missed events or falls back to full `state_sync` if too many missed.

**Keep-alive**: 30s timeout on queue reads, sends SSE comment `ping`. `sse-starlette` also pings at 15s intervals.

## State Machine

Three round types: **Task, Quick Draw (Brain Test), Interrogation**. Selected dynamically at the start of each round via `select_next_round_type(last_round_type, alive_count)` — not pre-generated. `state.round_types` is a growing list (appended per round). `MinigameMeta` / `MINIGAMES` in `game_logic.py` stores `min_players` and `has_elimination` per type. Selection rules: no consecutive repeat, Interrogation requires ≥4 alive, no consecutive non-eliminating rounds.

**Task** (constrained creative prompt, no Q&A):
```
PROMPT (25s) → REVIEW (40s) → ELIMINATION (12s) → next round
```

**Quick Draw / Brain Test** (multiple-choice speed quiz, no voting or elimination):
```
BRAIN_TEST (85s safety timer) → BRAIN_TEST_RESULTS (15s) → next round
```
BRAIN_TEST runs 5 challenges at 15s each via `_start_brain_test_loop`. Each challenge shows 4 options; players tap one. Scored by pure correctness (`selected_index == correct_index` → 1 point). Winner receives PARTIAL SCAN or DOUBLE VOTE ability stored in `state.active_ability`. `do_after_brain_test()` starts the next round directly — no ELIMINATION.

**Interrogation** (hot seat with LLM question synthesis):
```
PROMPT (45s) → NOMINATE (15s) → QUESTION (25s) → RESPOND (30s) → REVIEW (40s) → ELIMINATION (12s) → next round
```

**REVIEW sub-phases** (all round types with REVIEW): No new `GamePhase` enum values. `PhaseChangedEvent` carries `discuss_starts_at` and `vote_starts_at` ISO timestamps. Frontend `useSubPhase()` hook in `ReviewPhase.tsx` transitions locally:
```
REVEAL (0-8s) → DISCUSS (8-26s) → VOTE (26-40s)
```
PARTIAL SCAN ability (if active) triggers in `_trigger_ability_on_review()` at REVIEW start — picks 2 random alive players (not holder), one with true role, one randomized (50/50). Results broadcast via `ScanResultEvent`, shown in `ScanResults` component during DISCUSS. During DISCUSS, players send up to 3 messages (`POST /{game_id}/discussion-message`, 120 char max) broadcast as `DiscussionMessageEvent`. Rate-limited via `discussion_counts` on `RoundState`.

### Phase Transitions

The canonical valid phase sequences are defined in `PHASE_SEQUENCES` (a dict keyed by `RoundType`) in `game_logic.py`. `next_phase()` consults this table; `transitions.py` helper functions drive the actual async work.

All transitions funnel through helper functions in `transitions.py` (shared by `actions.py` routes and `ai_scheduler.py`):

| Function | Trigger | What it does |
|---|---|---|
| `start_phase_timer` | Every phase start | Creates `asyncio.Task` that sleeps then calls `handle_phase_expiry` |
| `handle_phase_expiry` | Timer fires | Acquires lock, checks phase unchanged, routes to `do_*_complete` |
| `do_prompt_complete` | All answers in | TASK → REVIEW; INTERROGATION → NOMINATE |
| `do_question_complete` | All questions in | Interrogation: calls LLM synthesis, broadcasts `synthesis_ready`, → RESPOND |
| `do_vote_resolution` | REVIEW timer expires | Tallies multi-votes + comedy votes, generates LLM verdict, → ELIMINATION |
| `do_after_elimination` | ELIMINATION timer | Checks game-over; branches on next round type |
| `do_brain_test_complete` | BRAIN_TEST safety timer or challenges done | Scores challenges, assigns ability, → BRAIN_TEST_RESULTS |
| `do_after_brain_test` | BRAIN_TEST_RESULTS timer | No elimination — starts next round directly |
| `_trigger_ability_on_review` | REVIEW phase start | Executes PARTIAL SCAN if active; clears DOUBLE VOTE on round end |
| `initialize_and_start_game` | Host start or matchmaking fire | Spawns AI, assigns personalities, delegates to `_start_next_round()` |

**Early completion**: When all players submit (answers, nominations, questions, responses), the timer is cancelled and the transition happens immediately. Exception: **REVIEW never early-completes**.

**Interrogation NOMINATE resolution**: plurality vote among all nominations; ties broken randomly.

**Interrogation QUESTION → synthesis**: when all non-nominated players submit questions, `synthesize_questions()` (LLM, 5s timeout) weaves them into one cross-examination paragraph. Fallback: numbered list.

**Brain Test sub-round loop**: `_start_brain_test_loop` runs as a background `asyncio.Task`. Each iteration broadcasts `BrainTestChallengeEvent` (including `options` array) with the current challenge, then calls `on_brain_test_challenge()` to schedule AI option selection (via `_ai_brain_test_task()`, generate-then-lock pattern). After all challenges, cancels safety timer and calls `do_brain_test_complete`.

### Game-Over Conditions

Checked in `game_logic.check_game_over()` after each elimination. Returns `("ai", [])` or `("survivors", [player_ids...])`:
- All humans eliminated → AI wins (`state.winner = "ai"`, `state.winner_ids = []`)
- All AI eliminated or ≤2 players remaining → survivors win (`state.winner = "survivors"`, `state.winner_ids = [...]`)
- Max rounds reached (safety cap, default 10) → same survivor logic

`GameOverEvent` and `StateSyncEvent` both carry `winner_ids`.

## Matchmaking

`MatchmakingService` (singleton, `backend/services/matchmaking.py`) implements a rolling lobby:

1. Players `POST /matchmaking/join` → get `player_id` + `alias` + connect to `GET /matchmaking/events` SSE.
2. Each join/leave triggers `_on_player_change()`: if `human_count >= mm_min_humans`, start countdown; if count drops below, cancel it.
3. Solo player gets a separate `mm_solo_timeout_seconds` (45s) grace period, then fires a game with AI companions.
4. `_fire_game()`: snapshot + clear queue, close join window (`_join_window_open.clear()`), create `TellGameState`, add human players, call `initialize_and_start_game(game_id, ai_count)`, broadcast `game_assigned` SSE event to all lobby clients, then reopen window.
5. Total player count is randomized: `target_total = random.randint(mm_min_total, mm_max_total)`, `ai_count = max(1, target_total - human_count)`.

The `MATCHMAKING_LOBBY_ID = "_matchmaking"` constant is used as a synthetic game ID within `ConnectionManager` so the same SSE infrastructure serves both game and lobby streams.

## AI Player Scheduling

`ai_scheduler.py` implements the **generate-then-lock** pattern:

```
1. Sleep random delay (varies by phase)
2. Build AIPlayerDeps snapshot (reads state WITHOUT lock — stale is fine)
3. Call LLM (PydanticAI agent) — may take 1-5 seconds
4. Acquire lock
5. Check phase hasn't changed (if it has, discard result)
6. Write result to state + broadcast event
7. Release lock
```

**Per phase**:

| Phase | Action | Delay |
|---|---|---|
| PROMPT | Each AI answers | 3-15s |
| NOMINATE | Each AI nominates (Interrogation only) | 2-8s |
| QUESTION | Each AI submits a question (except hot-seated) | 3-12s |
| RESPOND | AI targets respond to their question | 2-8s |
| REVIEW (DISCUSS) | Each AI sends 1-2 discussion messages | 10-22s |
| REVIEW (VOTE) | Each AI casts votes | 28-37s |
| BRAIN_TEST (each challenge) | Each AI selects an option | 2-8s |

Brain test challenges scheduled via `on_brain_test_challenge()` called by `_start_brain_test_loop`. Uses the same generate-then-lock pattern and registers via `register_task()`.

All tasks stored in `_ai_tasks[game_id]` and cancelled on phase change via `cancel_all()`.

**Conversation history**: Each AI player has a `message_history` (PydanticAI `ModelMessage` list) stored in `_conversation_history`. History is threaded through all `generate_*` calls and updated after each action, giving AI players memory within a game.

**Fallback**: If LLM fails, personality's `fallback_response` is used.

## AI Agent Architecture

Single module-level `ai_agent: Agent[AIPlayerDeps, str]` in `agents.py`. System prompt built dynamically from `@ai_agent.instructions` — personality template + game context (alive players, round, answers, Q&A, synthesis). Model passed per-call via `model=settings.ai_model`.

**Agent functions in `agents.py`**:

| Function | Phase | Notes |
|---|---|---|
| `generate_answer` | PROMPT | Responds to prompt in character |
| `generate_question` | QUESTION | Anonymous follow-up targeting assigned/nominated player |
| `generate_question_response` | RESPOND | Responds to received question or synthesis |
| `generate_nomination` | NOMINATE | Picks player to put on hot seat; structured output `NominationResponse` |
| `decide_vote` | REVIEW | Returns up to `max_votes_for_player(alive_count)` aliases; structured output `VoteResponse` |
| `synthesize_questions` | QUESTION→RESPOND | System-level call; weaves N questions into one paragraph. 5s timeout |
| `generate_verdict` | Elimination | System-level call; one-line dramatic sentence. 3s timeout |
| `generate_brain_test_answer` | BRAIN_TEST | System-level call; picks from 4 options. 3s timeout |
| `generate_discussion_message` | REVIEW DISCUSS | Reuses `ai_agent` + conversation history; personality-aware chat message |
| `generate_narration` | Transition hooks | System-level call; dry literary narrator voice. 3s timeout (5s for game_over) |

`synthesize_questions`, `generate_verdict`, `generate_brain_test_answer`, and `generate_narration` use `_run_system_call()` — a separate ephemeral `Agent` with no personality context and short timeouts.

5 personalities: paranoid, chill, overachiever, glitchy, philosopher. Each has `answer_system_prompt`, `vote_strategy`, `question_style`, and `fallback_response`.

Model: `google-gla:gemini-3.1-flash-lite-preview` (configured in `config.toml`).

## Frontend Architecture

**State**: Single Zustand store (`useGameStore`) holds all game state. SSE events dispatch directly to store actions (`onStateSync`, `onPhaseChanged`, etc.).

**SSE connection**: `useGameEvents` hook connects `EventSource` on mount, routes events to store. Auto-reconnects natively.

**Phase routing**: `game/[id]/page.tsx` renders phase-appropriate component based on `store.phase`. Eliminated players receive a `spectator` prop — components render read-only views.

**Session persistence**: Player ID stored in `sessionStorage` keyed by game ID. Survives page refresh within the same tab.

**Timer**: Server sends `phase_deadline` (ISO timestamp). Client counts down locally via `useTimer` hook (1s interval).

**Phase interstitials**: `PhaseInterstitial` has 5 rotating robot voice archetypes (clinical, bureaucratic, military, malfunctioning, friendly) that cycle per round. Each phase gets directive subtitle text. Spectator-specific variants and situation lines ("N units remain") derived from cumulative context fields in the store (`totalRounds`, `lastEliminationWasHuman`, `humansEliminated`, `aisEliminated`). On first game start, `game/[id]/page.tsx` shows a cold open sequence ("N UNITS ASSEMBLED / some are not what they seem") before round 1.

**Narrator**: `Narration` component receives `narrationText`/`narrationTrigger` from the store. Fades in, holds, then auto-dismisses after 6s. `game_over` trigger persists. `NarrationInline` used on the game over screen.

**Matchmaking**: `/queue` page uses `connectMatchmakingEvents()` (separate SSE client from game events) to receive `lobby_status` and `game_assigned` events. On `game_assigned`, stores `{playerId, alias}` in `sessionStorage` keyed by game ID, then redirects to `/game/{id}`.

**View components**:

| Component | Phase | Role |
|---|---|---|
| `AnswerCard` | Shared | Answer-first card; alias + role label pinned to bottom; renders as `button` or `div` |
| `PlayerBar` | All gameplay phases | Persistent strip showing alive players and connection status |
| `VoteOverlay` | REVIEW | Multi-select vote UI (up to 3, changeable) |
| `PhaseInterstitial` | Phase transitions | Robot voice archetype overlay with directive subtitles and situation lines |
| `Narration` | Async narrator events | Floating overlay, auto-dismiss 6s; `NarrationInline` for game over |
| `BrainTestPhase` | BRAIN_TEST / BRAIN_TEST_RESULTS | 4-option buttons + scored results grid with winner + ability awarded |
| `QuestionPhase` | QUESTION | Shows target's answer, write anonymous follow-up question |
| `RespondPhase` | RESPOND | Answer received question (or synthesis in Interrogation) |
| `NominatePhase` | NOMINATE | Pick player for hot seat |
| `ReviewPhase` | REVIEW | 3 sub-phases via `useSubPhase()`: REVEAL (AnswerCard grid + Q&A), DISCUSS (DiscussionChat + ScanResults), VOTE (voting + comedy) |

## Prompt Selection

**Regular prompts**: 30 prompts across 5 categories (emotional, logical, creative, philosophical, social). Used in Interrogation rounds. Selection rules: no repeats, no same-category back-to-back, social prompts excluded from round 1.

**Task prompts**: 42 prompts across 7 categories (haiku, concise, humor, corporate, casual, style, emotional_task). Used in Task rounds. Separate `used_task_prompt_indices` + `last_task_prompt_category` tracked in `TellGameState`. Same no-repeat, no-same-category rules via `select_task_prompt()`.

**Brain test challenges**: 21 multiple-choice challenges across 4 types (estimation, common_knowledge, trick, pattern) in `schemas/prompts.py`. Each has 4 `options` and a `correct_index`. `select_brain_test_challenges(n)` picks a balanced mix of `n` (default 5).
