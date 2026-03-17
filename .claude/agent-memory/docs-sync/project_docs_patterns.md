---
name: project_docs_patterns
description: Documentation drift patterns, sync conventions, and common stale spots for the Tell game project docs
type: project
---

Round type history: Probe was the original first round type (round-robin anonymous Q&A). It was replaced by Task/Interrogation/Word Chain cycling. Any reference to "Probe" as an active round type is stale — Probe is still defined in the enum but not in the rotation.

**Why:** Major architecture addition (matchmaking, Word Chain, Task rounds) in the commit after 47153f9. Probe dropped from `select_round_types()` cycle.

**How to apply:** When syncing docs, check `game_logic.py::select_round_types()` for the authoritative cycle order. Don't assume it matches what docs say.

Common drift sources:
- `schemas/constants.py` is minimal — just three constants. CLAUDE.md previously said "timer durations, player limits" which was wrong; those are in `config.toml`.
- `docs/GAME_DESIGN.md` "Explicitly Cut" section had "Matchmaking" listed — remove when matchmaking ships.
- AI scheduler conversation history feature: added silently, not mentioned in old docs. Check `_conversation_history` dict in `ai_scheduler.py`.
- `initialize_and_start_game` is in `transitions.py` (not `actions.py`) and is shared by both host-start and matchmaking flows.
- Word Chain uses `CHAIN` as the `GamePhase` value (not `WORD_CHAIN`). `WORD_CHAIN` is the `RoundType`.
