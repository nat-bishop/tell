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

## Common drift sources (v2)

- **Round types**: Only `TASK` and `BRAIN_TEST` in `MINIGAMES`. Selection rule: no consecutive repeat only (no player count restrictions).
- **Phase durations**: `config.toml` is authoritative. `config.py` default fallbacks may lag.
- **schemas/constants.py** is minimal — just three constants. Not where durations or limits live.
- **Matchup sub-round loop**: `_start_matchup_loop` in `transitions.py`, analogous to `_start_brain_test_loop`. Uses `MatchupChallengeEvent` SSE. AI votes via generate-then-lock pattern.
- **FinalReveal before GameOver**: `_do_game_over()` broadcasts `FinalRevealEvent` then `GameOverEvent`. Frontend handles reveal-first, score-second sequence.
- **`total_rounds = 5`** is the game length (not a safety cap). `check_game_over()` returns winner when `round_number >= total_rounds`.
- **`initialize_and_start_game`** is in `transitions.py` (not `actions.py`) — shared by host-start and matchmaking.
- **Narrator fires in** `transitions.py::_fire_narration()` as `asyncio.create_task()` — non-blocking, generate-then-lock pattern.
- **AI conversation history**: `_conversation_history` dict in `ai_scheduler.py`. Easy to miss in architecture docs.
- **`StateSyncEvent` carries `scores` dict** — player_id → score. Also on `MatchupResultsEvent`, `BrainTestResultsEvent`, `GameOverEvent`.
- **Bye player**: Odd player out in matchup rounds stored as `bye_player_id` on `RoundState`. They don't appear in a head-to-head but still accumulate score from other rounds.
