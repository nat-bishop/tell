# Architecture

## System Overview

```
Human Client A  ── POST /games/{id}/answer ──►  FastAPI
                                                   │
                ◄── SSE: state_sync ───────────────┤  validates, acquires
Human Client B  ◄── SSE: phase_changed ────────────┤  asyncio.Lock, mutates
                                                   │  state, broadcasts to
AI Player       ── internal asyncio task ──────────┘  all queues

GET /games/{id}/events  →  persistent EventSource per client
POST /games/{id}/*      →  actions (join, start, answer, question, respond, nominate, vote)
```

## Module Dependency Rules

```
schemas/ ← backend/services/ ← backend/api/routes/
schemas/ ← backend/llm/
frontend/ is independent (communicates via REST + SSE)
```

`schemas/` is the shared contract. `game_logic.py` is pure (no I/O). Routes handle HTTP + locking + broadcasting.

## Real-Time: SSE

Each connected client gets an `asyncio.Queue[GameEvent | None]`. The `ConnectionManager` maintains per-game dicts of queues and broadcasts events to all.

**Event flow**: Route validates action → acquires per-game `asyncio.Lock` → mutates `TellGameState` → creates `GameEvent` with monotonic `seq` → broadcasts to all queues → releases lock.

**Reconnection**: Every event logged to a per-game `deque(maxlen=200)`. On `EventSource` reconnect, client sends `last_seq` query param. Server replays missed events or falls back to full `state_sync` if too many missed.

**Keep-alive**: 30s timeout on queue reads, sends SSE comment `ping`. `sse-starlette` also pings at 15s intervals.

## State Machine

Two round types alternate throughout the game. Round 1 is always Probe.

**Probe** (round-robin anonymous questions):
```
LOBBY → PROMPT → QUESTION → RESPOND → REVIEW → ELIMINATION → PROMPT → ... → GAME_OVER
```

**Interrogation** (hot seat with LLM question synthesis):
```
LOBBY → PROMPT → NOMINATE → QUESTION → RESPOND → REVIEW → ELIMINATION → ...
```

Round types are pre-generated at game start (`select_round_types()`) into `state.round_types`: odd rounds = probe, even rounds = interrogation.

### Phase Transitions

All transitions funnel through helper functions in `actions.py`:

| Function | Trigger | What it does |
|---|---|---|
| `_start_phase_timer` | Every phase start | Creates `asyncio.Task` that sleeps then calls `_handle_phase_expiry` |
| `_handle_phase_expiry` | Timer fires | Acquires lock, checks phase unchanged, routes to next phase |
| `_synthesize_and_transition` | All questions in (Interrogation) | Calls LLM synthesis outside lock, transitions to RESPOND |
| `_do_vote_resolution` | REVIEW timer expires | Tallies multi-votes, generates LLM verdict, eliminates player |
| `_after_elimination` | ELIMINATION timer expires | Checks game-over, starts next round or ends game |

**Early completion**: When all players submit (answers, nominations, questions, responses), the timer is cancelled and the transition happens immediately. Exception: **REVIEW never early-completes** — votes are changeable until the timer expires.

**Probe QUESTION assignment**: `assign_question_targets()` in `game_logic.py` creates a round-robin chain — player `i` questions player `(i+1) % len(alive)`.

**Interrogation NOMINATE resolution**: plurality vote among all nominations; ties broken randomly.

**Interrogation QUESTION → synthesis**: when all non-nominated players submit questions, `synthesize_questions()` (LLM, 5s timeout) weaves them into one cross-examination paragraph. Fallback: numbered list.

### Game-Over Conditions

Checked in `game_logic.check_game_over()` after each elimination:
- All humans eliminated → AI wins
- All AI eliminated → humans win
- ≤2 players remaining → humans win if any survive
- Max rounds reached (`max(3, humanCount + 1)`) → humans win

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

All tasks stored in `_ai_tasks[game_id]` and cancelled on phase change via `cancel_all()`.

**Fallback**: If LLM fails, personality's `fallback_response` is used.

## AI Agent Architecture

Single PydanticAI `Agent(output_type=str)` instantiated per call. System prompt composed from:
1. Personality template (action-specific)
2. Game context (alive players, round number, answers, questions/responses)
3. Task-specific instruction

**Agent functions in `agents.py`**:

| Function | Phase | Notes |
|---|---|---|
| `generate_answer` | PROMPT | Responds to prompt in character |
| `generate_question` | QUESTION | Anonymous follow-up targeting assigned/nominated player |
| `generate_question_response` | RESPOND | Responds to received question or synthesis |
| `generate_nomination` | NOMINATE | Picks player to put on hot seat |
| `decide_vote` | REVIEW | Returns up to `max_votes_for_player(alive_count)` aliases |
| `synthesize_questions` | QUESTION→RESPOND | System-level call; weaves N questions into one paragraph |
| `generate_verdict` | Elimination | System-level call; one-line dramatic sentence about the elimination |

`synthesize_questions` and `generate_verdict` are system-level calls (no personality context), with short timeouts (5s and 3s respectively).

5 personalities: paranoid, chill, overachiever, glitchy, philosopher. Each has `answer_system_prompt`, `vote_strategy`, `question_style`, and `fallback_response`.

Model: `google-gla:gemini-3.1-flash-lite-preview` (configured in `config.toml`).

## Frontend Architecture

**State**: Single Zustand store (`useGameStore`) holds all game state. SSE events dispatch directly to store actions (`onStateSync`, `onPhaseChanged`, etc.).

**SSE connection**: `useGameEvents` hook connects `EventSource` on mount, routes events to store. Auto-reconnects natively.

**Phase routing**: `game/[id]/page.tsx` renders phase-appropriate component based on `store.phase`. Eliminated players receive a `spectator` prop — components render read-only views.

**Session persistence**: Player ID stored in `sessionStorage` keyed by game ID. Survives page refresh within the same tab.

**Timer**: Server sends `phase_deadline` (ISO timestamp). Client counts down locally via `useTimer` hook (1s interval).

**View components**:

| Component | Phase | Role |
|---|---|---|
| `PlayerBar` | All gameplay phases | Persistent strip showing alive players and connection status |
| `Gallery` | REVIEW | Grid of player cards for voting context |
| `Spotlight` | REVIEW | Auto-cycling featured player |
| `VoteOverlay` | REVIEW | Multi-select vote UI (up to 3, changeable) |
| `QuestionPhase` | QUESTION | Write anonymous follow-up question to assigned target |
| `RespondPhase` | RESPOND | Answer received question (or synthesis in Interrogation) |
| `NominatePhase` | NOMINATE | Pick player for hot seat |
| `ReviewPhase` | REVIEW | Combines Spotlight + Gallery + VoteOverlay |

## Prompt Selection

30 prompts across 5 categories (emotional, logical, creative, philosophical, social). Selection rules:
- No repeats within a game
- No same-category back-to-back
- Social prompts (reference other players) excluded from round 1
- Random within valid set after filtering
