---
name: project_docs_patterns
description: Documentation drift patterns, sync conventions, and common stale spots for the Tell game project docs
type: project
---

Round type history: Probe → Task/Interrogation/Word Chain → Task/Brain Test/Interrogation → Task + Brain Test (v3) → **Task (Gallery Vote) + Brain Test (Quick Draw) + Wager + Signal (v4, current)**. Always check `MINIGAME_REGISTRY` in `backend/minigames/__init__.py` for the authoritative list.

**Why:** Each major push changes the round type cycle. The names and mechanics are load-bearing throughout CLAUDE.md, ARCHITECTURE.md, and GAME_DESIGN.md.

**How to apply:** When syncing docs, start with `backend/minigames/`. Check handler `meta` fields for `has_prompt`/`has_results` — these determine phase flow. Check `FacilityScene.tsx::MINIGAME_COMPONENTS` for frontend handler count.

## v4 Key Additions (Wager + Signal)

Added alongside existing Task + BrainTest handlers:

- **WagerHandler** (`backend/minigames/wager.py`): `_wager_loop` drives 3 questions × [GUESS 15s + BET 15s]. Routes: `POST /wager-guess`, `POST /wager-bet`. Scoring: `score_wager()`. No early completion — loop controls timing.
- **SignalHandler** (`backend/minigames/signal.py`): `has_prompt=True`, custom `get_prompt_duration()` (20s). `_signal_loop` iterates player order. Routes: `GET /signal-phrase`, `POST /signal-guess`. LLM judging via `judge_signal_guesses()` (parallelized, fuzzy fallback). Custom frontend prompt: `FacilitySignalPrompt`.
- **MINIGAME_COMPONENTS** in `FacilityScene.tsx` now has 4 entries. Signal entry has `Prompt` key (custom).
- **Task prompt categories changed from earlier docs**: Now `style_transfer`/`translation`/`pattern`/`grammar`/`format_conversion`/`summary`/`rewrite`. 36 prompts total.
- **No solo timeout in matchmaking**: Always fires on countdown. Always fills to 8 total with AI.
- **Config**: `TELL_VOTE_DURATION`/`TELL_VOTE_RESULTS_DURATION` for task active/results (25s/8s). Brain test challenge duration is 12s, safety is 75s.
- **Signal state on `TellGameState`**: `used_signal_phrase_indices`, `used_signal_constraint_indices`.
- **Signal state on `RoundState`**: `signal_constraint`, `signal_player_order`, `signal_phrases`, `signal_guesses`, `signal_judgments`.

## Facility UI (current frontend)

`frontend/src/facility/` is the diegetic game view. Key things to keep in sync:

- **Zone table**: `zones.ts` is authoritative for panel positions. 9 zones.
- **Transition machine states**: `idle → lockdown → reconfigure → boot → idle`. `FacilityScene` hidden during lockdown/reconfigure; `TransitionOverlay` renders only in reconfigure.
- **No Rive**: Background is pure CSS via `FacilityBackground.tsx`.
- **Component registry**: `MINIGAME_COMPONENTS` in `FacilityScene.tsx` maps `round_type → {Active, Results, Prompt?}`. Signal has a `Prompt` entry.

## v5 Key Changes (AI consolidation, scoring ×100, Signal redesign)

- **AI agent consolidation**: `brain_test_agent` removed. Single `ai_agent` handles all player actions. `judge_agent` for signal judging only. All actions go through `_run_ai_agent()`.
- **Structured output + auto-retry**: `AICallContext` dataclass carries `valid: list | None`. `ai_agent` constructed with `validation_context=lambda ctx: ctx.deps.valid`. `field_validator` in output models (BrainTestResponse, PlayerPickResponse, SignalGuessResponse) raises if value not in `valid` — triggers PydanticAI retry (up to 2).
- **Stable instructions / volatile user message**: `get_personality_instructions(name)` computes once per personality. Passed as `instructions=` kwarg to `ai_agent.run()`. Game context in user message.
- **All scores ×100**: Task −100/vote; Brain Test +100/challenge; Wager +100 closest, +100 bet; Signal guesser score*50 (0/50/100), transmitter = avg of guesser points (int division).
- **Signal redesign**: 3 random transmitters (not all players). `used_signal_transmitter_ids` tracks across rounds. Non-transmitters cannot submit answers; transmitters cannot guess. LLM judging is graded 0/1/2 (not bool). `judge_agent` output model: `SignalJudgment` with list of `JudgmentEntry(score: 0|1|2)`. Fuzzy fallback now binary 0/2.
- **Conversation history now universal**: All player actions thread history — including brain test and signal guess (previously stateless). `_conversation_history[game_id][player_id]` populated by every `_run_ai_agent` call.

## Common drift sources (v5)

- **Task scoring is negative and ×100**: Votes received = −100 each. Check `task.py::build_results()`.
- **Signal transmitters vs. all players**: Only 3 transmitters per round. `signal_player_order` = transmitter list, not all players. `used_signal_transmitter_ids` on `TellGameState` tracks repeats.
- **Signal judging is graded 0/1/2**, not boolean. Guesser points = `score * 50`. Transmitter = integer avg of guesser points.
- **`AICallContext` is the deps type**, not `AIPlayerDeps` (old name, removed). `validation_context` is a constructor param on `ai_agent`, not a `run()` param.
- **Round types**: All four registered: TASK, BRAIN_TEST, WAGER, SIGNAL. Selection rule: no consecutive repeat only.
- **`MinigameMeta` location**: `backend/minigames/base.py`, not `game_logic.py`.
- **`score_brain_test()` location**: `backend/minigames/brain_test.py`, not `game_logic.py`.
- **`tally_gallery_votes()` in game_logic.py**: Pure helper used by narrator context builder and task handler.
- **`StateSyncEvent` carries `scores` dict** plus generic reconnection fields: `sub_round_index`, `sub_round_payload`, `round_results_payload`, `round_scores`.
- **FinalReveal before GameOver**: `_do_game_over()` broadcasts `FinalRevealEvent` then `GameOverEvent`.
- **`total_rounds = 5`** is game length (not a safety cap).
- **`initialize_and_start_game`** in `transitions.py` — shared by host-start and matchmaking.
- **Narrator fires in** `transitions.py::_fire_narration()` as `asyncio.create_task()` — non-blocking.
- **Circular import pattern**: `ai_scheduler ↔ transitions`, `BrainTestHandler._brain_loop → do_active_complete`, `WagerHandler._wager_loop → do_active_complete`, `SignalHandler._signal_loop → do_active_complete`. All resolved via runtime imports inside async functions.
- **Signal `_judge_all_guesses` runs outside lock**: LLM calls parallelized per featured player, then result stored under lock.
- **Signal guesses keyed by featured_player_id → guesser_id**: Nested dict. `rs.signal_guesses[featured_pid][guesser_pid] = guess_text`.
