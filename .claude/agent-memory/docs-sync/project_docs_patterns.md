---
name: project_docs_patterns
description: Documentation drift patterns, sync conventions, and common stale spots for the Tell game project docs
type: project
---

Round type history: Probe → Task/Interrogation/Word Chain (3-type) → Task/Word Chain/Brain Test/Interrogation (4-type, current). Always check `game_logic.py::select_round_types()` for the authoritative cycle order — docs lag the code.

**Why:** Each major feature push has changed the cycle. The order and count are load-bearing for timing tables in CLAUDE.md and GAME_DESIGN.md.

**How to apply:** When syncing docs, start with `select_round_types()` in `game_logic.py`. If the cycle doesn't match docs, update all timing tables and "round types" prose in CLAUDE.md, ARCHITECTURE.md, and GAME_DESIGN.md together.

Common drift sources:
- Phase durations: `config.toml` is authoritative. `config.py` default fallbacks may lag (e.g. `elimination_duration` was 8 in Python fallback, 12 in `config.toml`). When docs say a timer value, verify in `config.toml`.
- `schemas/constants.py` is minimal — just three constants. Not where durations or limits live.
- New round types always require: schema models (`game_state.py`), `game_logic.py` (phases, transitions), `transitions.py` (sub-round loop + do_* helpers), `ai_scheduler.py` (on_* handler), frontend component, SSE events, `config.py`/`config.toml` settings. All must be documented.
- AI scheduler conversation history feature: `_conversation_history` dict in `ai_scheduler.py`. Easy to miss.
- `initialize_and_start_game` is in `transitions.py` (not `actions.py`) — shared by host-start and matchmaking.
- Word Chain: `CHAIN` is the `GamePhase` value; `WORD_CHAIN` is the `RoundType`. Brain Test: `BRAIN_TEST` is both `GamePhase` and `RoundType`.
- Narrator fires in `transitions.py::_fire_narration()` as `asyncio.create_task()` — non-blocking, uses generate-then-lock pattern same as AI players.
- Comedy Cup adds a second vote track: `comedy_votes` on `RoundState`, `ComedyWinnerEvent` SSE, `castComedyVote()` action, winner shown at Elimination step 5.
- Brain Test results live on `RoundState.brain_challenges` (not a `TellGameState` field). They are not injected into AI prompts for subsequent rounds — only displayed to players via `BrainTestResultsEvent`.
- Brain Test now scores challenges: `trick`/`pattern` → fuzzy match; `estimation`/`common_knowledge` → uniqueness. Winner earns PARTIAL SCAN or DOUBLE VOTE stored in `state.active_ability`. Cleared in `_start_next_round()`.
- REVIEW has 3 server-driven sub-phases (REVEAL/DISCUSS/VOTE) — no new `GamePhase` values. Timestamps `discuss_starts_at` and `vote_starts_at` in `PhaseChangedEvent`. Frontend `useSubPhase()` drives local transitions.
- Discussion messages: `POST /{game_id}/discussion-message`, 3 msgs/player/round, 120 chars. Rate-limited via `discussion_counts` on `RoundState`. AI uses `_ai_discussion_task()` + `generate_discussion_message()`.
- PARTIAL SCAN triggered by `_trigger_ability_on_review()` in `transitions.py` at REVIEW start. DOUBLE VOTE applied in `resolve_votes()` in `game_logic.py`.
