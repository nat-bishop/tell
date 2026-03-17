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
POST /games/{id}/*         →  actions (join, start, answer, question, respond, nominate, vote, chain-word)
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

Three round types cycle: **Task → Interrogation → Word Chain → Task → ...**. Pre-generated at game start via `select_round_types()` into `state.round_types`.

**Task** (constrained creative prompt, no Q&A):
```
PROMPT (25s) → REVIEW (40s) → ELIMINATION (8s) → next round
```

**Interrogation** (hot seat with LLM question synthesis):
```
PROMPT (45s) → NOMINATE (15s) → QUESTION (25s) → RESPOND (30s) → REVIEW (40s) → ELIMINATION (8s) → next round
```

**Word Chain** (word association, no written prompt):
```
CHAIN (64s safety timer) → REVIEW (40s) → ELIMINATION (8s) → next round
```
CHAIN is subdivided into 8 sub-rounds of 8s each, driven by `_start_chain_loop` background task.

### Phase Transitions

All transitions funnel through helper functions in `transitions.py` (shared by `actions.py` routes and `ai_scheduler.py`):

| Function | Trigger | What it does |
|---|---|---|
| `start_phase_timer` | Every phase start | Creates `asyncio.Task` that sleeps then calls `handle_phase_expiry` |
| `handle_phase_expiry` | Timer fires | Acquires lock, checks phase unchanged, routes to `do_*_complete` |
| `do_prompt_complete` | All answers in | TASK → REVIEW; INTERROGATION → NOMINATE; PROBE → QUESTION |
| `do_question_complete` | All questions in | Interrogation: calls LLM synthesis, broadcasts `synthesis_ready`, → RESPOND |
| `do_vote_resolution` | REVIEW timer expires | Tallies multi-votes, generates LLM verdict, → ELIMINATION |
| `do_after_elimination` | ELIMINATION timer | Checks game-over; branches on next round type |
| `do_chain_complete` | CHAIN safety timer or sub-rounds done | → REVIEW |
| `initialize_and_start_game` | Host start or matchmaking fire | Spawns AI, assigns personalities, transitions to first round |

**Early completion**: When all players submit (answers, nominations, questions, responses), the timer is cancelled and the transition happens immediately. Exceptions: **REVIEW never early-completes**; **CHAIN** uses its own sub-round loop, not early-complete.

**Interrogation NOMINATE resolution**: plurality vote among all nominations; ties broken randomly.

**Interrogation QUESTION → synthesis**: when all non-nominated players submit questions, `synthesize_questions()` (LLM, 5s timeout) weaves them into one cross-examination paragraph. Fallback: numbered list.

**Word Chain sub-round loop**: `_start_chain_loop` runs as a background `asyncio.Task`. Each iteration sleeps `chain_sub_round_duration` (8s), picks the next seed via `select_chain_next_word()` (prefers unique/single-submitter words), broadcasts `ChainSeedEvent`, then calls `on_chain_sub_round()` to schedule AI associations. After all sub-rounds, cancels safety timer and calls `do_chain_complete`.

### Game-Over Conditions

Checked in `game_logic.check_game_over()` after each elimination:
- All humans eliminated → AI wins
- All AI eliminated → humans win
- ≤2 players remaining → humans win if any survive
- Max rounds reached (`max(3, humanCount + 1)`) → humans win

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
| REVIEW | Each AI casts votes | 5-15s |
| CHAIN (each sub-round) | Each AI submits a word association | 1-4s |

CHAIN sub-rounds are scheduled via `on_chain_sub_round(game_id, sub_round)` called by `_start_chain_loop` at the start of each sub-round. AI chain tasks use the same generate-then-lock pattern but are registered via `register_task()` rather than replacing the task list (so they don't cancel phase tasks).

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
| `generate_association` | CHAIN sub-round | System-level call; single word, personality-aware style hints. 3s timeout |

`synthesize_questions`, `generate_verdict`, and `generate_association` use `_run_system_agent()` — a separate ephemeral `Agent` with no personality context and short timeouts.

5 personalities: paranoid, chill, overachiever, glitchy, philosopher. Each has `answer_system_prompt`, `vote_strategy`, `question_style`, and `fallback_response`.

Model: `google-gla:gemini-3.1-flash-lite-preview` (configured in `config.toml`).

## Frontend Architecture

**State**: Single Zustand store (`useGameStore`) holds all game state. SSE events dispatch directly to store actions (`onStateSync`, `onPhaseChanged`, etc.).

**SSE connection**: `useGameEvents` hook connects `EventSource` on mount, routes events to store. Auto-reconnects natively.

**Phase routing**: `game/[id]/page.tsx` renders phase-appropriate component based on `store.phase`. Eliminated players receive a `spectator` prop — components render read-only views.

**Session persistence**: Player ID stored in `sessionStorage` keyed by game ID. Survives page refresh within the same tab.

**Timer**: Server sends `phase_deadline` (ISO timestamp). Client counts down locally via `useTimer` hook (1s interval).

**Phase interstitials**: `PhaseInterstitial` component briefly displays the incoming phase name and round type label between transitions, with CSS `animate-interstitial-in/out` animations.

**Matchmaking**: `/queue` page uses `connectMatchmakingEvents()` (separate SSE client from game events) to receive `lobby_status` and `game_assigned` events. On `game_assigned`, stores `{playerId, alias}` in `sessionStorage` keyed by game ID, then redirects to `/game/{id}`.

**View components**:

| Component | Phase | Role |
|---|---|---|
| `AnswerCard` | Shared | Answer-first card; alias + role label pinned to bottom; renders as `button` or `div` |
| `PlayerBar` | All gameplay phases | Persistent strip showing alive players and connection status |
| `VoteOverlay` | REVIEW | Multi-select vote UI (up to 3, changeable) |
| `PhaseInterstitial` | Phase transitions | Overlay showing phase name + round type, fades in/out |
| `WordChainPhase` | CHAIN | Seed word display, growing chain thread, single-word input per sub-round |
| `QuestionPhase` | QUESTION | Shows target's answer, write anonymous follow-up question |
| `RespondPhase` | RESPOND | Answer received question (or synthesis in Interrogation) |
| `NominatePhase` | NOMINATE | Pick player for hot seat |
| `ReviewPhase` | REVIEW | `AnswerCard` grid with inline Q&A + voting |

## Prompt Selection

**Regular prompts**: 30 prompts across 5 categories (emotional, logical, creative, philosophical, social). Used in Interrogation/Probe rounds. Selection rules: no repeats, no same-category back-to-back, social prompts excluded from round 1.

**Task prompts**: 42 prompts across 7 categories (haiku, concise, humor, corporate, casual, style, emotional_task). Used in Task rounds. Separate `used_task_prompt_indices` + `last_task_prompt_category` tracked in `TellGameState`. Same no-repeat, no-same-category rules via `select_task_prompt()`.

**Word Chain seeds**: 100+ seed words in `schemas/word_chain.py`. `select_seed_word()` avoids recently used seeds.
