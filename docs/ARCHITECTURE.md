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
                                 vote, brain-test-answer)
POST /matchmaking/join|leave →  matchmaking queue
GET /matchmaking/events      →  matchmaking SSE (lobby_status, game_assigned)
GET /matchmaking/status      →  current lobby state
```

## Module Dependency Rules

```
schemas/ ← backend/services/ ← backend/api/routes/
schemas/ ← backend/llm/
schemas/ ← backend/minigames/
frontend/ is independent (communicates via REST + SSE)
```

`schemas/` is the shared contract. `game_logic.py` is pure (no I/O). `transitions.py` contains the async phase-transition sequences shared by routes and the AI scheduler, including `initialize_and_start_game` (used by both host-start and matchmaking). Routes handle HTTP + locking + broadcasting. `backend/minigames/` contains the handler plugin system — each round type is an isolated handler.

## Real-Time: SSE

Each connected client gets an `asyncio.Queue[GameEvent | None]`. The `ConnectionManager` maintains per-game dicts of queues and broadcasts events to all.

**Event flow**: Route validates action → acquires per-game `asyncio.Lock` → mutates `TellGameState` → creates `GameEvent` with monotonic `seq` → broadcasts to all queues → releases lock.

**Reconnection**: Every event logged to a per-game `deque(maxlen=200)`. On `EventSource` reconnect, client sends `last_seq` query param. Server replays missed events or falls back to full `state_sync` if too many missed.

**Keep-alive**: 30s timeout on queue reads, sends SSE comment `ping`. `sse-starlette` also pings at 15s intervals.

## Minigame Handler Pattern

`backend/minigames/` is the plugin package. Each round type implements `MinigameHandler`:

```python
class MinigameHandler:
    round_type: RoundType
    meta: MinigameMeta           # min_players, has_prompt, has_results,
                                 # active_interstitial, results_interstitial

    def setup_round(state, settings)          # mutates TellGameState in place
    def get_active_duration(settings) → int
    def get_results_duration(settings) → int
    def active_event_extras(state) → dict     # merged into PhaseChangedEvent
    async def on_active_start(game_id)        # start loops, schedule AI
    def build_results(state) → (payload, score_deltas)
    def build_state_sync_extras(state, player_id) → dict  # reconnection
```

`MINIGAME_REGISTRY` (dict in `backend/minigames/__init__.py`) maps `RoundType → MinigameHandler`. `get_handler(round_type)` is the single lookup point used by `transitions.py` and `game_logic.py`.

**To add a round type**: Create `backend/minigames/mytype.py`, subclass `MinigameHandler`, call `register(MyHandler())` in `__init__.py`. Add `MINIGAME_COMPONENTS[round_type]` entry in `FacilityScene.tsx`.

## State Machine

Two round types: **Task (Gallery Vote)** and **Quick Draw (Brain Test)**. Selected dynamically at the start of each round via `get_next_round_type(state)` — not pre-generated. `state.round_types` is a growing list (appended per round). Selection rule: no consecutive repeat.

**Task / Gallery Vote** (creative prompt, everyone votes for most-human-sounding answer):
```
PROMPT (45s + 5s interstitial) → ACTIVE (all see all answers, tap to vote)
  → RoundResultsEvent → RESULTS (vote counts, 15s) → next round
```
During ACTIVE, all players see all answers and vote for the player who sounds most human. Votes received = negative points (−1 per vote). `TaskHandler.on_active_start()` schedules AI vote tasks. Early-complete fires when all players have voted.

**Quick Draw / Brain Test** (multiple-choice speed quiz, scored by correctness):
```
ACTIVE (85s safety timer, 5 challenges × 15s each) → RoundResultsEvent
  → RESULTS (15s) → next round
```
`BrainTestHandler.on_active_start()` spawns `_brain_loop` as a background task. Each iteration broadcasts `SubRoundEvent(round_type="brain_test", sub_round_index=i, payload={question, options, ...})`, calls `on_brain_test_challenge()` to schedule AI, then sleeps for the sub-duration. After all challenges, cancels safety timer and calls `do_active_complete()`.

**After `total_rounds` (default 5)**:
```
FinalRevealEvent → GameOverEvent
```
`check_game_over()` returns winner info when `state.round_number >= state.total_rounds`. `_do_game_over()` broadcasts `FinalRevealEvent` (all roles + scores revealed) then `GameOverEvent`.

### Phase Transitions

All transitions funnel through `transitions.py` (minigame-agnostic — no `if round_type ==` checks):

| Function | Trigger | What it does |
|---|---|---|
| `start_phase_timer` | Every phase start | Creates `asyncio.Task` that sleeps then calls `handle_phase_expiry` |
| `handle_phase_expiry` | Timer fires | Acquires lock, checks phase unchanged, routes to `do_*_complete` |
| `do_prompt_complete` | All answers in (or timer) | Gets handler, transitions to ACTIVE, broadcasts event, calls `handler.on_active_start()` |
| `do_active_complete` | Sub-round loop done (or timer) | Calls `handler.build_results()`, applies score deltas, broadcasts `RoundResultsEvent`, then → RESULTS or next round |
| `do_results_complete` | RESULTS timer | Checks game-over; starts next round (only for `has_results=True` types) |
| `initialize_and_start_game` | Host start or matchmaking fire | Spawns AI, assigns personalities, delegates to `_start_next_round()` |

**Early completion**: When all players submit answers (PROMPT), timer is cancelled and `do_prompt_complete` fires immediately. For Task ACTIVE, when all players have voted, timer is cancelled and `do_active_complete` fires immediately. Brain test sub-rounds run on a fixed cadence — not early-completable per sub-round.

### Game-Over Conditions

Checked in `game_logic.check_game_over()` after each round completes. Returns `None` until game ends, then `("winners", [winner_ids...])`:
- `state.round_number >= state.total_rounds` → game ends; highest scorer wins; ties produce multiple `winner_ids`

`GameOverEvent` and `StateSyncEvent` both carry `winner_ids` and `scores`.

### Scoring

- `Player.score` (int) accumulates across rounds.
- Task: votes received = **−1 per vote** via `TaskHandler.build_results()`. `tally_gallery_votes()` in `game_logic.py`.
- Brain Test: `selected_index == correct_index` → +1 per challenge. `score_brain_test()` in `brain_test.py`.
- `scores` dict (player_id → score) carried on `RoundResultsEvent`, `StateSyncEvent`, `GameOverEvent`.

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

`on_phase_change()` in `ai_scheduler.py` **only handles PROMPT** — schedules AI answer tasks. ACTIVE phase AI scheduling is delegated to each minigame handler's `on_active_start()`:
- **Task**: `TaskHandler.on_active_start()` schedules `_ai_vote_task` for each AI player.
- **Brain Test**: `BrainTestHandler._brain_loop` calls `on_brain_test_challenge()` per challenge.

All tasks stored in `_ai_tasks[game_id]` and cancelled on phase change via `cancel_all()`. `register_task()` allows handlers to register external tasks for cleanup.

**Conversation history**: Each AI player has a `message_history` (PydanticAI `ModelMessage` list) stored in `_conversation_history`. History is threaded through `generate_answer` and `decide_vote` calls, giving AI players memory within a game.

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
| `decide_vote` | ACTIVE / task | Picks which player sounds most human; structured output `VoteResponse` |
| `generate_brain_test_answer` | ACTIVE / brain_test | Picks from 4 options. Uses stateless `brain_test_agent`. 3s timeout |
| `generate_narration` | Transition hooks | Uses `narrator_agent` + message history; dry literary narrator voice. 3s timeout (5s for game_over) |

5 personalities: anxious, chill, earnest, eccentric, sardonic. Each has `description`, `vote_strategy`, and `fallback_response`.

Model: `google-gla:gemini-3.1-flash-lite-preview` (configured in `config.toml`).

## Frontend Architecture

**State**: Single Zustand store (`useGameStore`) holds all game state. SSE events dispatch directly to store actions (`onStateSync`, `onPhaseChanged`, etc.). Generic round fields: `subRoundIndex`, `subRoundPayload`, `roundResults`, `roundScores` — no typed per-minigame fields.

**SSE connection**: `useGameEvents` hook connects `EventSource` on mount, routes events to store. Auto-reconnects natively.

**Session persistence**: Player ID stored in `sessionStorage` keyed by game ID. Survives page refresh within the same tab.

**Timer**: Server sends `phase_deadline` (ISO timestamp). Client counts down locally via `useTimer` hook (1s interval).

**Interstitial holds**: Each phase start has a built-in hold period driven by `MinigameMeta.active_interstitial` / `results_interstitial`. `PhaseChangedEvent` carries `action_starts_at` so the frontend knows when the actual action window begins. `TransitionOverlay` shows during the `reconfigure` state of the transition machine.

**Narrator**: `FacilityNarration` component receives `narrationText`/`narrationTrigger` from the store. Fades in, holds, then auto-dismisses after 6s. `game_over` trigger persists.

**Matchmaking**: `/queue` page uses `connectMatchmakingEvents()` (separate SSE client) to receive `lobby_status` and `game_assigned` events. On `game_assigned`, stores `{playerId, alias}` in `sessionStorage` keyed by game ID, then redirects to `/game/{id}`.

### Verification Facility UI

`frontend/src/facility/` is the diegetic game view. `game/[id]/page.tsx` renders `FacilityGameContent` after join.

**Layer stack** (bottom → top):
1. `FacilityBackground` — CSS atmospheric background (radial gradients, ambient glow; z-index 0)
2. `facility-vignette` — edge darkening overlay
3. Content layer (z-index 10) — panels, timer, narration, overlays

**Panel system**: `Panel` component reads zone geometry from `ZONES` in `zones.ts` and renders as `position: absolute` with frosted-glass (`facility-panel` CSS class: `backdrop-filter`, CRT scanline pseudo-element). 9 named zones:

| Zone | Layout purpose |
|---|---|
| `wall-display` | Large center-top — primary info, interstitials |
| `desk-terminal` | Center-bottom — player input |
| `main-screen` | Wide top — brain test challenge |
| `center-area` | Wide center — brain test options |
| `left-screen` / `right-screen` | Split — legacy two-panel layout |
| `full-screen` | Full-area — brain test results, game over |
| `readout` | Top-right — HUD readout |
| `ticker` | Bottom — narration PA strip |

**Transition machine** (`useTransitionMachine`): `idle → lockdown (300ms) → reconfigure → boot (400ms) → idle`. Total duration equals the server `action_starts_at` hold window. `FacilityScene` hides during `lockdown`/`reconfigure`; `TransitionOverlay` renders only during `reconfigure`. On reconnection (`state_sync` without phase change), `snapTo()` skips the animation.

**Phase layout** (`phaseLayouts.ts`): Two-tier lookup — `SHARED_LAYOUTS` for framework phases (lobby/prompt/game_over), `ROUND_LAYOUTS[roundType][phase]` for active/results. Returns `PhaseLayout { roomIndex, brightness, accentColor }` used by `FacilityBackground`.

**Phase interstitials** (`TransitionOverlay`): Shows in `wall-display` panel during `reconfigure`. 5 robot voice archetypes (clinical, bureaucratic, military, malfunctioning, friendly) cycle by round number.

**Cold open**: When phase transitions from `lobby` to first round, `FacilityGameContent` shows "N SUBJECTS DETECTED / some are not what they seem" for 5.5s before handing off to `FacilityScene`.

**Component registry** (`FacilityScene.tsx`): `MINIGAME_COMPONENTS` maps `round_type → {Active, Results}` component pairs. Phase routing dispatches to `minigame.Active` for `phase === "active"` and `minigame.Results` for `phase === "results"`.

**Facility phase components**:

| Component | Zones used | Notes |
|---|---|---|
| `FacilityLobby` | `wall-display` + `desk-terminal` | Title + player list; host start button |
| `FacilityPrompt` | `wall-display` + `desk-terminal` | Prompt display + answer textarea |
| `FacilityVote` | gallery layout | All answers visible; tap to cast gallery vote |
| `FacilityVoteResults` | results layout | Vote counts per player |
| `FacilityBrainTest` | `main-screen` + `center-area` (challenge) / `full-screen` (results) | Dual-mode based on phase |
| `FacilityGameOver` | `full-screen` | Headline, scoreboard, play again |

## Prompt Selection

**Task prompts**: 42 prompts across 7 categories (haiku, concise, humor, corporate, casual, style, emotional_task). `used_prompt_indices` + `last_prompt_category` tracked in `TellGameState`. No-repeat, no-same-category rules via `select_duel_prompt()` in `prompts.py`.

**Brain test challenges**: 21 multiple-choice challenges across 4 types (estimation, common_knowledge, trick, pattern) in `schemas/prompts.py`. Each has 4 `options` and a `correct_index`. `select_brain_test_challenges(n)` picks a balanced mix of `n` (default 5).
