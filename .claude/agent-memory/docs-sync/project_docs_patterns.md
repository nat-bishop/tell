---
name: project_docs_patterns
description: Documentation drift patterns, sync conventions, and common stale spots for the Tell game project docs
type: project
---

Round type history: Probe → Task/Interrogation/Word Chain (3-type) → Task/Brain Test/Interrogation (3-type) → **Task (Matchup) + Brain Test (Quick Draw) only (v2, current)**. Always check `game_logic.py::select_next_round_type()` and `MINIGAMES` registry for the authoritative list — docs lag the code.

**Why:** Each major feature push has changed the cycle. The count and names are load-bearing for timing tables in CLAUDE.md and GAME_DESIGN.md.

**How to apply:** When syncing docs, start with `MINIGAMES` in `game_logic.py`. If the round types don't match docs, update all timing tables and "round types" prose in CLAUDE.md, ARCHITECTURE.md, and GAME_DESIGN.md together.

## v2 Key Changes (score-based, no elimination)

The game was completely redesigned from elimination-based to score-based in 2026:
- Frame flip: "Be yourself, find the AI" — humans play as themselves, AI tries to pass as human
- No elimination. No spectator mode. Fixed 5 rounds. Big reveal at end.
- Removed: Interrogation, Discussion chat, Comedy Cup, Abilities (PARTIAL SCAN + DOUBLE VOTE), multi-vote, ELIMINATION phase
- Added: Matchup sub-round loop (1v1 head-to-head), FinalRevealEvent, scoring on Player model

## Facility UI (current frontend, branch: verification-chamber-ui)

`frontend/src/facility/` is a parallel diegetic rewrite — old `components/` untouched, used by join/queue screens only. `FacilityGameContent` replaces old `GameContent` in `game/[id]/page.tsx`. Key things to keep in sync:

- **Zone table**: `zones.ts` is authoritative for panel positions. 9 zones. Changes there should update the zone table in ARCHITECTURE.md.
- **Transition machine states**: `idle → lockdown → reconfigure → boot → idle`. `FacilityScene` hidden during lockdown/reconfigure; `TransitionOverlay` renders only in reconfigure.
- **Rive inputs**: state machine name `"facility_sm"`, 6 character slots × 3 inputs (`char_{i}_x`, `char_{i}_state`, `char_{i}_visible`), plus 3 room inputs. `phaseLayouts.ts` is authoritative for what gets set per phase.
- **Legacy components are NOT removed**: They're still used. Don't document them as removed.

## Generic Minigame Architecture (v3, current)

`GamePhase` is now 5 fixed values: `LOBBY, PROMPT, ACTIVE, RESULTS, GAME_OVER`. `ACTIVE` and `RESULTS` dispatch by `round_type` — phases never grow with new minigames.

Key event renames:
- `BrainTestChallengeEvent` + `MatchupChallengeEvent` → `SubRoundEvent(round_type, sub_round_index, payload)`
- `BrainTestResultsEvent` + `MatchupResultsEvent` → `RoundResultsEvent(round_type, results, scores, payload)`
- `PhaseChangedEvent` now carries `round_payload`, `round_results`, `round_scores` (not `matchups`)

Key function renames in `transitions.py`:
- `do_matchup_complete` + `do_brain_test_complete` → `do_active_complete` (dispatches by round_type)
- `do_after_brain_test` → `do_results_complete`
- New: `_initialize_round()`, `_start_sub_round_loop()` dispatchers

`MinigameMeta` now has: `min_players`, `has_prompt`, `has_results`, `active_interstitial`, `results_interstitial`.

Frontend store: ~20 minigame-specific fields replaced with 5 generic fields: `subRoundIndex`, `subRoundPayload`, `roundPayload`, `roundResults`, `roundScores`.

`FacilityScene.tsx` routes `active`/`results` by `roundType` (not phase-specific components).
`phaseLayouts.ts`: `PHASE_LAYOUTS` record → `getPhaseLayout(phase, roundType)` two-tier lookup.

`RoundState.current_matchup` removed — redundant with `current_sub_round`.
`resolve_matchup_votes()` returns `(state, matchup_results_list, scores_dict)`.

## Common drift sources (v3)

- **Round types**: Only `TASK` and `BRAIN_TEST` in `MINIGAMES`. Selection rule: no consecutive repeat only.
- **Phase durations**: `config.toml` is authoritative. `config.py` default fallbacks may lag.
- **schemas/constants.py** is minimal — just three constants. Not where durations or limits live.
- **Sub-round events**: Both loops now emit `SubRoundEvent`. Check `round_type` field to distinguish matchup vs brain test.
- **FinalReveal before GameOver**: `_do_game_over()` broadcasts `FinalRevealEvent` then `GameOverEvent`. Frontend handles reveal-first, score-second sequence.
- **`total_rounds = 5`** is the game length (not a safety cap). `check_game_over()` returns winner when `round_number >= total_rounds`.
- **`initialize_and_start_game`** is in `transitions.py` (not `actions.py`) — shared by host-start and matchmaking.
- **Narrator fires in** `transitions.py::_fire_narration()` as `asyncio.create_task()` — non-blocking, generate-then-lock pattern.
- **AI conversation history**: `_conversation_history` dict in `ai_scheduler.py`. Easy to miss in architecture docs.
- **`StateSyncEvent` carries `scores` dict** — player_id → score. Also on `RoundResultsEvent` and `GameOverEvent`.
- **Bye player**: Odd player out in matchup rounds stored as `bye_player_id` on `RoundState`. They don't appear in a head-to-head but still accumulate score from other rounds.
