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
POST /games/{id}/*           →  actions (join, start, answer, vote,
                                 brain-test-answer, wager-guess, wager-bet, signal-guess)
GET  /games/{id}/signal-phrase →  player's secret phrase + constraint (signal rounds only)
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
    def get_prompt_duration(settings) → int  # default: settings.prompt_duration; override for custom timing
    def get_active_duration(settings) → int
    def get_results_duration(settings) → int
    def active_event_extras(state) → dict     # merged into PhaseChangedEvent
    async def on_active_start(game_id)        # start loops, schedule AI
    def build_results(state) → (payload, score_deltas)
    def build_state_sync_extras(state, player_id) → dict  # reconnection
```

`MINIGAME_REGISTRY` (dict in `backend/minigames/__init__.py`) maps `RoundType → MinigameHandler`. `get_handler(round_type)` is the single lookup point used by `transitions.py` and `game_logic.py`.

**To add a round type**: Create `backend/minigames/mytype.py`, subclass `MinigameHandler`, call `register(MyHandler())` in `__init__.py`. Add `MINIGAME_COMPONENTS[round_type]` entry in `FacilityScene.tsx`. If the round needs a custom prompt screen, add a `Prompt` key to the registry entry.

## State Machine

Four round types selected dynamically at the start of each round via `get_next_round_type(state)` — not pre-generated. `state.round_types` is a growing list (appended per round). Selection rule: no consecutive repeat.

**Task / Gallery Vote** (linguistic task prompt, everyone votes for most-human-sounding answer):
```
PROMPT (45s + 5s interstitial) → ACTIVE (all see all answers, tap to vote)
  → RoundResultsEvent → RESULTS (vote counts, 8s) → next round
```
During ACTIVE, all players see all answers and vote for the player who sounds most human. Votes received = negative points (−100 per vote). `TaskHandler.on_active_start()` schedules AI vote tasks. Early-complete fires when all players have voted.

**Quick Draw / Brain Test** (multiple-choice speed quiz, scored by correctness):
```
ACTIVE (75s safety timer, 5 challenges × 12s each) → RoundResultsEvent
  → RESULTS (15s) → next round
```
`BrainTestHandler.on_active_start()` spawns `_brain_loop` as a background task. Each iteration broadcasts `SubRoundEvent(round_type="brain_test", sub_round_index=i, payload={question, options, ...})`, calls `on_brain_test_challenge()` to schedule AI, then sleeps for the sub-duration. After all challenges, cancels safety timer and calls `do_active_complete()`.

**Wager** (numerical estimation + social betting):
```
ACTIVE (100s safety, 3 questions × [GUESS 15s + BET 15s]) → RoundResultsEvent
  → RESULTS (15s) → next round
```
`WagerHandler._wager_loop` iterates each question in two sub-rounds: GUESS (place marker on number line) then BET (pick whose guess is closest). Each sub-round broadcasts `SubRoundEvent(round_type="wager", ...)`. Scoring: +100 for closest guess, +100 for betting on a closest guesser; self-bet allowed. `score_wager()` in `wager.py`.

**Signal** (Drawful-style phrase transformation + guessing):
```
PROMPT (20s — 3 random transmitters each get a secret phrase + shared constraint, submit transformation)
→ ACTIVE (120s safety, 3 sub-rounds × 12s each — one per transmitter, all non-transmitters guess simultaneously)
→ LLM batch-judges all guesses → RoundResultsEvent → RESULTS (15s) → next round
```
`SignalHandler.setup_round` selects 3 random transmitters (tracked in `used_signal_transmitter_ids` to avoid repeats across rounds); only they get phrases and answer during PROMPT. `_signal_loop` iterates `signal_player_order` (transmitters only), broadcasting `SubRoundEvent(round_type="signal", ...)` per transmitter. All non-transmitters submit guesses via `POST /signal-guess`; transmitters cannot guess their own phrase. After all sub-rounds, `_judge_all_guesses` parallelizes LLM judging via `asyncio.gather`. LLM scoring is graded 0/1/2 per guess. Signal uses a custom PROMPT component (`FacilitySignalPrompt`) that fetches per-player phrases via `GET /signal-phrase`.

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

All scores are in units of 100 for granularity. `Player.score` (int) accumulates across rounds.

- **Task**: votes received = **−100 per vote** via `TaskHandler.build_results()`. `tally_gallery_votes()` in `game_logic.py`.
- **Brain Test**: `selected_index == correct_index` → +100 per challenge. `score_brain_test()` in `brain_test.py`.
- **Wager**: +100 for closest guess, +100 for betting on a closest guesser. Max 200 per question, 600 across 3 questions. `score_wager()` in `wager.py`.
- **Signal**: LLM judges each guess 0/1/2. Guesser earns `score * 50` (0/50/100). Transmitter earns the integer average of all their guessers' points. LLM `judge_agent` with fuzzy match fallback. `SignalHandler.build_results()`.
- `scores` dict (player_id → score) carried on `RoundResultsEvent`, `StateSyncEvent`, `GameOverEvent`.

## Matchmaking

`MatchmakingService` (singleton, `backend/services/matchmaking.py`) implements a rolling lobby:

1. Players `POST /matchmaking/join` → get `player_id` + `alias` + connect to `GET /matchmaking/events` SSE.
2. Each join/leave triggers `_on_player_change()`: if `human_count >= mm_min_humans`, start countdown; if count drops below, cancel it.
3. `_fire_game()`: snapshot + clear queue (capped at `mm_max_humans`), close join window (`_join_window_open.clear()`), create `TellGameState`, add human players, fill to 8 total with AI, call `initialize_and_start_game(game_id, ai_count)`, broadcast `game_assigned` SSE event to all lobby clients, then reopen window.

The `MATCHMAKING_LOBBY_ID = "_matchmaking"` constant is used as a synthetic game ID within `ConnectionManager` so the same SSE infrastructure serves both game and lobby streams.

## AI Player Scheduling

`ai_scheduler.py` implements the **generate-then-lock** pattern:

```
1. Sleep random delay (varies by phase)
2. Read state snapshot outside lock (stale is fine)
3. Call LLM (PydanticAI agent) — may take 1-5 seconds
4. Acquire lock
5. Check phase hasn't changed (if it has, discard result)
6. Write result to state + broadcast event
7. Release lock
```

`on_phase_change()` in `ai_scheduler.py` **only handles PROMPT** — schedules AI answer tasks (for Task and Signal rounds). ACTIVE phase AI scheduling is delegated to each minigame handler's `on_active_start()`:
- **Task**: `TaskHandler.on_active_start()` schedules `_ai_vote_task` for each AI player.
- **Brain Test**: `BrainTestHandler._brain_loop` calls `on_brain_test_challenge()` per challenge.
- **Wager**: `WagerHandler._wager_loop` calls `on_wager_guess()`/`on_wager_bet()` per sub-round.
- **Signal (PROMPT)**: `_ai_answer_task` detects `round_type == SIGNAL` and only schedules AI transmitters; uses `build_signal_transform_prompt`.
- **Signal (ACTIVE)**: `SignalHandler._signal_loop` calls `on_signal_sub_round()` each sub-round, scheduling `_ai_signal_guess_task` for each non-transmitter AI player.

All tasks stored in `_ai_tasks[game_id]` and cancelled on phase change via `cancel_all()`. `register_task()` allows handlers to register external tasks for cleanup.

**Conversation history**: Each AI player has a `message_history` (PydanticAI `ModelMessage` list) stored in `_conversation_history`. History is threaded through every `_run_ai_agent` call — answers, votes, brain test answers, wager guesses, wager bets, and signal guesses — giving AI players memory across all rounds of the game.

**Fallback**: If LLM fails, personality's `fallback_response` is used.

## AI Agent Architecture

Three agents in `agents.py`:
- **`ai_agent`** — all player actions (answers, votes, guesses, bets). `deps_type=AICallContext`.
- **`narrator_agent`** — show host narration, maintains per-game history.
- **`judge_agent`** — signal judging only; not a player action.

**Stable system prompt / volatile user message**: `get_personality_instructions(name)` returns a cacheable per-personality string passed as `instructions=` to each `ai_agent.run()` call. Volatile context (round, answers, other players) goes in the user message built by `build_*_prompt()` functions.

**Structured output with auto-retry**: Each action type has a Pydantic output model with `field_validator`. `validation_context` on `ai_agent` is a lambda that reads from `deps.valid` at call time — PydanticAI re-runs validation on retry, so invalid choices (wrong index, unknown alias) auto-retry up to 2 times.

```python
@dataclass
class AICallContext:
    valid: list | None = None   # valid indices or aliases; checked by field_validator

ai_agent = Agent(
    output_type=str,
    deps_type=AICallContext,
    retries=2,
    validation_context=lambda ctx: ctx.deps.valid,
)
```

**Conversation history**: All player actions (answers, votes, brain test, wager, signal guess) thread `message_history` through `_run_ai_agent` and store updated history in `_conversation_history[game_id][player_id]`. Gives AI players in-game memory across rounds.

**Agent functions in `agents.py`** (all through `_run_ai_agent`):

| Function | Output model | Phase | Notes |
|---|---|---|---|
| `generate_answer` | `str` | PROMPT | Signal uses `build_signal_transform_prompt`; task uses `build_answer_prompt` |
| `decide_gallery_vote` | `PlayerPickResponse` | ACTIVE / task | `valid=` list of aliases; auto-retries on invalid alias. Fallback: random |
| `generate_brain_test_answer` | `BrainTestResponse` | ACTIVE / brain_test | `valid=` list of valid indices; auto-retries on out-of-range. Fallback: random |
| `generate_wager_guess` | `WagerGuessResponse` | ACTIVE / wager | No `valid=`; personality-driven with history |
| `generate_wager_bet` | `PlayerPickResponse` | ACTIVE / wager | `valid=` list of aliases; auto-retries on invalid alias |
| `generate_signal_guess` | `SignalGuessResponse` | ACTIVE / signal | Non-transmitters only. Fallback: `None` (no guess) |
| `judge_signal_guesses` | `SignalJudgment` | post-ACTIVE / signal | Uses `judge_agent`. Graded 0/1/2 per guess. 5s timeout. Fuzzy match fallback |
| `generate_narration` | `str` | Transition hooks | Uses `narrator_agent` + message history. 3s timeout (5s for game_over) |

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

**Component registry** (`FacilityScene.tsx`): `MINIGAME_COMPONENTS` maps `round_type → {Active, Results, Prompt?}` component pairs. Signal includes a `Prompt` entry (`FacilitySignalPrompt`); others fall back to `FacilityPrompt`. Phase routing dispatches to the appropriate component per phase.

**Facility phase components**:

| Component | Zones used | Notes |
|---|---|---|
| `FacilityLobby` | `wall-display` + `desk-terminal` | Title + player list; host start button |
| `FacilityPrompt` | `wall-display` + `desk-terminal` | Default prompt phase; unused when round has custom Prompt |
| `FacilityVote` | gallery layout | All answers visible; tap to cast gallery vote (task active) |
| `FacilityVoteResults` | results layout | Vote counts per player (task results) |
| `FacilityBrainTest` | `main-screen` + `center-area` (challenge) / `full-screen` (results) | Dual-mode; handles both active and results phases |
| `FacilityWager` | layout varies | Handles both active (number line + betting) and results phases |
| `FacilitySignalPrompt` | `wall-display` + `desk-terminal` | Custom prompt for signal: fetches per-player phrase via `GET /signal-phrase` |
| `FacilitySignalActive` | layout varies | Shows current transformation; guess input |
| `FacilitySignalResults` | layout varies | Phrase/guess/judgment cards per player |
| `FacilityGameOver` | `full-screen` | Headline, scoreboard, play again |

## Prompt Selection

**Task prompts**: 36 prompts across 7 linguistic-task categories (`style_transfer`, `translation`, `pattern`, `grammar`, `format_conversion`, `summary`, `rewrite`). `used_prompt_indices` + `last_prompt_category` tracked in `TellGameState`. No-repeat, no-same-category rules via `select_duel_prompt()` in `prompts.py`.

**Brain test challenges**: 21 multiple-choice challenges across 4 types (`estimation`, `common_knowledge`, `trick`, `pattern`) in `schemas/prompts.py`. Each has 4 `options` and a `correct_index`. `select_brain_test_challenges(n)` picks a balanced mix of `n` (default 5).

**Wager questions**: 26 numerical estimation questions across 6 categories (`geography`, `science`, `history`, `pop_culture`, `economics`, `nature`). Each has `correct_answer`, `range_min`/`range_max`, and `unit`. `select_wager_questions(n)` picks a category-diverse mix of `n` (default 3).

**Signal content**: 15 constraint strings (instruction text like "Describe the phrase as a breaking news headline.") and 40 phrases (concrete everyday scenarios). Each round: one shared constraint selected via `select_signal_constraint()`, one unique phrase per player via `select_signal_phrases()`. Both track `used_indices` on `TellGameState` to avoid repeats.
