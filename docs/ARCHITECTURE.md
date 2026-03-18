# Architecture

## System Overview

```
Human Client A  ── POST /games/{id}/answer ──────►  FastAPI
                                                       │
                ◄── SSE: state_sync ───────────────────┤  validates, acquires
Human Client B  ◄── SSE: phase_changed ────────────────┤  asyncio.Lock, mutates
                                                       │  state, broadcasts to
AI Player       ── internal asyncio task ──────────────┘  all queues

GET /games/{id}/events       →  persistent EventSource per client
POST /games/{id}/*           →  actions (join, start, answer,
                                 matchup-vote, brain-test-answer)
POST /matchmaking/join|leave →  matchmaking queue
GET /matchmaking/events      →  matchmaking SSE (lobby_status, game_assigned)
GET /matchmaking/status      →  current lobby state
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

Two round types: **Task (Matchup)** and **Quick Draw (Brain Test)**. Selected dynamically at the start of each round via `select_next_round_type(last_round_type)` — not pre-generated. `state.round_types` is a growing list (appended per round). `MinigameMeta` / `MINIGAMES` in `game_logic.py` stores `min_players` per type. Selection rule: no consecutive repeat.

**Task / Matchup** (constrained creative prompt, 1v1 voting):
```
PROMPT (25s) → MATCHUP (sub-round loop, 12s each) → MatchupResultsEvent → next round
```
After PROMPT, players are paired for head-to-head voting. `_start_matchup_loop` runs as a background task cycling through pairs. Each iteration broadcasts `MatchupChallengeEvent` with both answers and no labels; all players vote which sounds more human (0=left, 1=right). Winning player gets +1 score via `resolve_matchup_votes()`.

**Quick Draw / Brain Test** (multiple-choice speed quiz, scored by correctness):
```
BRAIN_TEST (75s safety timer, 5 challenges × 12s each) → BRAIN_TEST_RESULTS (15s) → next round
```
`_start_brain_test_loop` cycles through challenges. Each challenge shows 4 options; players tap one. Scored by pure correctness (`selected_index == correct_index` → 1 point). `do_after_brain_test()` starts the next round directly.

**After `total_rounds` (default 5)**:
```
FinalRevealEvent → GameOverEvent
```
`check_game_over()` returns winner info when `state.round_number >= state.total_rounds`. `_do_game_over()` broadcasts `FinalRevealEvent` (all roles + scores revealed) then `GameOverEvent`.

### Phase Transitions

All transitions funnel through helper functions in `transitions.py` (shared by `actions.py` routes and `ai_scheduler.py`):

| Function | Trigger | What it does |
|---|---|---|
| `start_phase_timer` | Every phase start | Creates `asyncio.Task` that sleeps then calls `handle_phase_expiry` |
| `handle_phase_expiry` | Timer fires | Acquires lock, checks phase unchanged, routes to `do_*_complete` |
| `do_prompt_complete` | All answers in (or timer) | TASK → MATCHUP; starts `_start_matchup_loop` |
| `do_matchup_complete` | All matchup sub-rounds done | Resolves votes, updates scores, checks game-over or next round |
| `do_brain_test_complete` | BRAIN_TEST safety timer or challenges done | Scores challenges, → BRAIN_TEST_RESULTS |
| `do_after_brain_test` | BRAIN_TEST_RESULTS timer | Checks game-over; starts next round directly |
| `initialize_and_start_game` | Host start or matchmaking fire | Spawns AI, assigns personalities, delegates to `_start_next_round()` |

**Early completion**: When all players submit answers, the timer is cancelled and `do_prompt_complete` fires immediately. MATCHUP sub-rounds run on a fixed 12s cadence — not early-completable.

**Matchup pairings**: Players paired in insertion order. Odd player out stored as `bye_player_id` on `RoundState`. `transition_to_matchup()` builds the `matchups` list in `game_logic.py`.

**Brain Test sub-round loop**: `_start_brain_test_loop` runs as a background `asyncio.Task`. Each iteration broadcasts `BrainTestChallengeEvent` (including `options` array) with the current challenge, then calls `on_brain_test_challenge()` to schedule AI option selection (via `_ai_brain_test_task()`, generate-then-lock pattern). After all challenges, cancels safety timer and calls `do_brain_test_complete`.

### Game-Over Conditions

Checked in `game_logic.check_game_over()` after each round completes. Returns `None` until game ends, then `("highest_scorer", [winner_ids...])`:
- `state.round_number >= state.total_rounds` → game ends; highest scorer wins; ties produce multiple `winner_ids`
- `state.winner = "highest_scorer"`; `state.winner_ids` holds IDs of top-scoring players

`GameOverEvent` and `StateSyncEvent` both carry `winner_ids` and `scores`.

### Scoring

- `Player.score` (int) accumulates across rounds.
- Matchup: winning side gets +1 per matchup via `resolve_matchup_votes()`. Ties: no point.
- Brain Test: `selected_index == correct_index` → +1 per challenge via `score_brain_test()`.
- `scores` dict (player_id → score) carried on `MatchupResultsEvent`, `BrainTestResultsEvent`, `StateSyncEvent`, `GameOverEvent`.

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
| MATCHUP (each sub-round) | Each AI votes | 1-8s |
| BRAIN_TEST (each challenge) | Each AI selects an option | 2-8s |

Brain test and matchup challenges scheduled via `on_brain_test_challenge()` and `on_matchup_challenge()` called by their respective background loops.

All tasks stored in `_ai_tasks[game_id]` and cancelled on phase change via `cancel_all()`.

**Conversation history**: Each AI player has a `message_history` (PydanticAI `ModelMessage` list) stored in `_conversation_history`. History is threaded through `generate_answer` and `generate_vote` calls, giving AI players memory within a game.

**Fallback**: If LLM fails, personality's `fallback_response` is used.

## AI Agent Architecture

Single module-level `ai_agent: Agent[AIPlayerDeps, str]` in `agents.py`. System prompt built dynamically from `@ai_agent.instructions` — personality template + game context (all players, round, answers). Model passed per-call via `model=settings.ai_model`.

Two agent tiers:
- **Character agents** (`ai_agent`, `narrator_agent`) — personality-driven, maintain message history.
- **Utility agents** (`brain_test_agent`) — stateless one-shot calls with fixed purpose.

**Agent functions in `agents.py`**:

| Function | Phase | Notes |
|---|---|---|
| `generate_answer` | PROMPT | Responds to prompt trying to pass as human |
| `generate_vote` | MATCHUP | Picks which answer sounds more human; structured output `VoteResponse` |
| `generate_brain_test_answer` | BRAIN_TEST | Picks from 4 options. Uses stateless `brain_test_agent`. 3s timeout |
| `generate_narration` | Transition hooks | Uses `narrator_agent` + message history; dry literary narrator voice. 3s timeout (5s for game_over) |

`generate_brain_test_answer` uses `_run_system_call()` — a stateless utility agent with no personality context.

5 personalities: paranoid, chill, overachiever, glitchy, philosopher. Each has `answer_system_prompt`, `vote_strategy`, and `fallback_response`.

Model: `google-gla:gemini-3.1-flash-lite-preview` (configured in `config.toml`).

## Frontend Architecture

**State**: Single Zustand store (`useGameStore`) holds all game state. SSE events dispatch directly to store actions (`onStateSync`, `onPhaseChanged`, etc.).

**SSE connection**: `useGameEvents` hook connects `EventSource` on mount, routes events to store. Auto-reconnects natively.

**Phase routing**: `game/[id]/page.tsx` renders phase-appropriate component based on `store.phase`.

**Session persistence**: Player ID stored in `sessionStorage` keyed by game ID. Survives page refresh within the same tab.

**Timer**: Server sends `phase_deadline` (ISO timestamp). Client counts down locally via `useTimer` hook (1s interval).

**Interstitial holds**: Each phase start has a built-in hold period (`_INTERSTITIAL_HOLD` dict in `game_logic.py`). `PhaseChangedEvent` carries `action_starts_at` so the frontend knows when the actual action window begins. `PhaseInterstitial` component shows during the hold.

**Phase interstitials**: `PhaseInterstitial` has 5 rotating robot voice archetypes (clinical, bureaucratic, military, malfunctioning, friendly) that cycle per round. Each phase gets directive subtitle text. Situation lines ("round N of 5") derived from `totalRounds` in the store. On first game start, `game/[id]/page.tsx` shows a cold open sequence ("N UNITS ASSEMBLED / some are not what they seem") before round 1.

**Narrator**: `Narration` component receives `narrationText`/`narrationTrigger` from the store. Fades in, holds, then auto-dismisses after 6s. `game_over` trigger persists. `NarrationInline` used on the game over screen.

**Matchmaking**: `/queue` page uses `connectMatchmakingEvents()` (separate SSE client from game events) to receive `lobby_status` and `game_assigned` events. On `game_assigned`, stores `{playerId, alias}` in `sessionStorage` keyed by game ID, then redirects to `/game/{id}`.

**View components**:

| Component | Phase | Role |
|---|---|---|
| `AnswerCard` | Shared | Answer-first card; alias + role label pinned to bottom; renders as `button` or `div` |
| `PlayerBar` | All gameplay phases | Persistent strip showing players, connection status, and running scores |
| `PhaseInterstitial` | Phase transitions | Robot voice archetype overlay with directive subtitles and situation lines |
| `Narration` | Async narrator events | Floating overlay, auto-dismiss 6s; `NarrationInline` for game over |
| `BrainTestPhase` | BRAIN_TEST / BRAIN_TEST_RESULTS | 4-option buttons + scored results grid |
| `MatchupPhase` | MATCHUP | 1v1 answer pair with vote buttons; sub-round loop |

## Prompt Selection

**Task prompts**: 42 prompts across 7 categories (haiku, concise, humor, corporate, casual, style, emotional_task). Used in Task/Matchup rounds. `used_task_prompt_indices` + `last_task_prompt_category` tracked in `TellGameState`. No-repeat, no-same-category rules via `select_task_prompt()`.

**Brain test challenges**: 21 multiple-choice challenges across 4 types (estimation, common_knowledge, trick, pattern) in `schemas/prompts.py`. Each has 4 `options` and a `correct_index`. `select_brain_test_challenges(n)` picks a balanced mix of `n` (default 5).
