---
name: project_docs_patterns
description: Documentation drift patterns, sync conventions, and common stale spots for the Tell game project docs
type: project
---

Round type history: Probe → Task/Interrogation/Word Chain → Task/Brain Test/Interrogation → **Task (Gallery Vote) + Brain Test (Quick Draw) only (v3, current)**. Always check `MINIGAME_REGISTRY` in `backend/minigames/__init__.py` for the authoritative list.

**Why:** Each major push changes the round type cycle. The names and mechanics are load-bearing throughout CLAUDE.md, ARCHITECTURE.md, and GAME_DESIGN.md.

**How to apply:** When syncing docs, start with `backend/minigames/`. Check handler `meta` fields for `has_prompt`/`has_results` — these determine phase flow.

## v3 Key Changes (plugin pattern + gallery vote)

Major refactor post-v2:

- **GamePhase collapsed**: 7 → 5 phases. Now: LOBBY, PROMPT, ACTIVE, RESULTS, GAME_OVER only.
- **Task round changed**: Was 1v1 matchup (sub-round loop). Now **gallery vote** — all answers shown at once, all players vote for one player who sounds most human. Votes received = −1 point each. Positive score = fewer suspicion votes.
- **Minigame handler plugin system**: `backend/minigames/` package with `MinigameHandler` interface, `MinigameMeta` dataclass, `MINIGAME_REGISTRY` dict. Handlers: `TaskHandler`, `BrainTestHandler`.
- **transitions.py is minigame-agnostic**: No `if round_type ==` checks. Everything dispatches via `get_handler()`.
- **AI scheduling delegated to handlers**: `on_phase_change()` in `ai_scheduler.py` handles PROMPT only. ACTIVE scheduling in `TaskHandler.on_active_start()` and `BrainTestHandler._brain_loop`.
- **SSE event names changed**: `SubRoundEvent` (was `BrainTestChallengeEvent`), `RoundResultsEvent` (was `BrainTestResultsEvent`/`VoteResultsEvent`). Old names gone.
- **Route changed**: `/vote` (was `/matchup-vote`).
- **score_brain_test()** moved to `backend/minigames/brain_test.py` (was `game_logic.py`).
- **MinigameMeta/MINIGAMES** moved to `backend/minigames/base.py` and `__init__.py` (was `game_logic.py`).
- **Rive removed**: `RiveScene.tsx`, `useFacilityCharacters.ts`, `facility.riv`, `@rive-app/react-canvas` all deleted. Background is now CSS (`FacilityBackground.tsx`).
- **FacilityViewport deleted**: Inlined into `FacilityGameContent.tsx`.
- **Frontend phases renamed**: `FacilityMatchup` → `FacilityVote`; `FacilityVoteResults` added.
- **FacilityScene uses component registry**: `MINIGAME_COMPONENTS` record mapping round_type → {Active, Results}.
- **phaseLayouts.ts two-tier**: `SHARED_LAYOUTS` for framework phases, `ROUND_LAYOUTS[roundType][phase]` for active/results.
- **`used_task_prompt_indices`/`last_task_prompt_category` renamed** to `used_prompt_indices`/`last_prompt_category` on `TellGameState`.

## Facility UI (current frontend)

`frontend/src/facility/` is the diegetic game view. Key things to keep in sync:

- **Zone table**: `zones.ts` is authoritative for panel positions. 9 zones.
- **Transition machine states**: `idle → lockdown → reconfigure → boot → idle`. `FacilityScene` hidden during lockdown/reconfigure; `TransitionOverlay` renders only in reconfigure.
- **No Rive**: Background is pure CSS via `FacilityBackground.tsx`.
- **Component registry**: `MINIGAME_COMPONENTS` in `FacilityScene.tsx` maps round_type → components. Adding a minigame requires entry here.

## Common drift sources (v3)

- **Task scoring is negative**: Votes received = −1 each. Easy to describe as "+1 per win" (old mechanic). Check `task.py::build_results()`.
- **Round types**: Only `TASK` and `BRAIN_TEST` registered. Selection rule: no consecutive repeat only.
- **`MinigameMeta` location**: `backend/minigames/base.py`, not `game_logic.py`.
- **`score_brain_test()` location**: `backend/minigames/brain_test.py`, not `game_logic.py`.
- **`tally_gallery_votes()` in game_logic.py**: Pure helper used by narrator context builder and task handler.
- **`StateSyncEvent` carries `scores` dict** plus generic reconnection fields: `sub_round_index`, `sub_round_payload`, `round_results_payload`, `round_scores`.
- **FinalReveal before GameOver**: `_do_game_over()` broadcasts `FinalRevealEvent` then `GameOverEvent`.
- **`total_rounds = 5`** is game length (not a safety cap).
- **`initialize_and_start_game`** in `transitions.py` — shared by host-start and matchmaking.
- **Narrator fires in** `transitions.py::_fire_narration()` as `asyncio.create_task()` — non-blocking.
- **AI conversation history**: `_conversation_history` dict in `ai_scheduler.py`.
- **Circular import pattern**: `ai_scheduler ↔ transitions`, and `BrainTestHandler._brain_loop → do_active_complete`. All resolved via runtime imports inside async functions.
