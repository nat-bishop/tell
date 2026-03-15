# Architecture

## System Overview

```
Human Client A  ── POST /games/{id}/answer ──►  FastAPI
                                                   │
                ◄── SSE: state_sync ───────────────┤  validates, acquires
Human Client B  ◄── SSE: answer_submitted ─────────┤  asyncio.Lock, mutates
                                                   │  state, broadcasts to
AI Player       ── internal asyncio task ──────────┘  all queues

GET /games/{id}/events  →  persistent EventSource per client
POST /games/{id}/*      →  actions (join, answer, chat, vote, start)
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

```
LOBBY → PROMPT (45s) → CHAT (75s) → VOTE (20s) → ELIMINATION (5s) → PROMPT → ... → GAME_OVER
```

### Phase Transitions

All transitions go through helper functions in `actions.py`:

| Function | Trigger | What it does |
|---|---|---|
| `_start_phase_timer` | Every phase start | Creates `asyncio.Task` that sleeps for duration, then calls `_handle_phase_expiry` |
| `_handle_phase_expiry` | Timer fires | Acquires lock, checks phase unchanged, transitions to next phase |
| `_do_vote_resolution` | Vote timer expires or all voted | Tallies votes, resolves ties (random), eliminates player |
| `_after_elimination` | Elimination timer expires | Checks game-over conditions, starts next round or ends game |

**Early completion**: When all players submit (answers or votes), the timer is cancelled and the transition happens immediately.

### Game-Over Conditions

Checked in `game_logic.check_game_over()` after each elimination:
- All humans eliminated → AI wins
- All AI eliminated → humans win
- ≤2 players remaining → humans win if any survive
- Max rounds reached (`max(3, humanCount + 1)`) → humans win

## AI Player Scheduling

`ai_scheduler.py` implements the **generate-then-lock** pattern:

```
1. Sleep random delay (3-15s for answers, 5-25s for chat, 2-10s for votes)
2. Build AIPlayerDeps snapshot (reads state WITHOUT lock — stale is fine)
3. Call LLM (PydanticAI agent) — may take 1-5 seconds
4. Acquire lock
5. Check phase hasn't changed (if it has, discard result)
6. Write result to state + broadcast event
7. Release lock
```

**Per phase**:
- **PROMPT**: Each AI schedules one answer with random delay
- **CHAT**: Each AI schedules 2-5 messages at random 5-25s intervals
- **VOTE**: Each AI schedules one vote with random delay

All tasks stored in `_ai_tasks[game_id]` and cancelled on phase change via `cancel_all()`.

**Fallback**: If LLM fails, personality's `fallback_response` is used (e.g., glitchy says "[signal lost]", chill says "meh").

## AI Agent Architecture

Single PydanticAI `Agent(output_type=str)` instantiated per call (not shared). System prompt composed from:
1. Personality template (answer/chat/vote-specific)
2. Game context (alive players, round number, answers so far, chat history)
3. Task-specific instruction

5 personalities: paranoid, chill, overachiever, glitchy, philosopher. Each has distinct answer style, chat behavior, vote strategy, and fallback response.

Model: `google-gla:gemini-3.1-flash-lite-preview` (fast, cheap). Configured in `config.toml`.

## Frontend Architecture

**State**: Single Zustand store (`useGameStore`) holds all game state. SSE events dispatch directly to store actions (`onStateSync`, `onPhaseChanged`, etc.).

**SSE connection**: `useGameEvents` hook connects `EventSource` on mount, routes events to store. Auto-reconnects natively.

**Phase routing**: `game/[id]/page.tsx` renders phase-appropriate component based on `store.phase`. Eliminated players get spectator views (read-only prompt/vote displays).

**Session persistence**: Player ID stored in `sessionStorage` keyed by game ID. Survives page refresh within the same tab.

**Timer**: Server sends `phase_deadline` (ISO timestamp). Client counts down locally via `useTimer` hook (1s interval). No server-side tick events needed.

## Prompt Selection

30 prompts across 5 categories (emotional, logical, creative, philosophical, social). Selection rules:
- No repeats within a game
- No same-category back-to-back
- Social prompts (reference other players) excluded from round 1
- Random within valid set after filtering
