# Tell — Future Ideas

Ideas for new round types and meta-features. Ranked by impact. Not an implementation plan — a curated shortlist of what's worth building next.

---

## 1. Post-Game Debrief

After GAME_OVER, the LLM analyzes the full game transcript and generates a report.

**What it produces:**
- Highlight reel: the funniest answer, the most suspicious moment, the best deception
- Each player's "tell" — what they consistently did that was human or AI
- Key moments where deception succeeded or failed
- Shareable summary card (text block or image)

**Why this is first priority:**
- Zero gameplay risk. Pure entertainment. Can't break anything.
- The shareable summary card is the viral hook. "Look at this game where the AI wrote a better haiku than all three humans."
- Gives closure. Social deduction games end abruptly — the debrief gives people talking points and a reason to play again.
- Uses the game recording infrastructure that already exists (`recordings/{game_id}.json`).

**Implementation**: LLM call with the full game recording as context. New UI section on the game_over screen. Could generate a static card for sharing.

**Effort**: Low-medium.

---

## 2. Autocomplete — Finish the Sentence

A sentence stem appears. Everyone finishes it. 10 seconds. One shot.

```
PROMPT (10s) → REVIEW (40s) → ELIMINATION (8s)
```

**Example stems:**
- "The thing about Mondays is..."
- "Nobody talks about the fact that..."
- "The worst advice I ever got was..."
- "If I could delete one app..."

**Why it belongs:**
- This is *literally what LLMs do* — completing text. Making it the game mechanic is meta-commentary that fits the theme perfectly.
- AI completions are polished, witty, balanced. Human completions are specific, sometimes dumb, occasionally brilliant.
- 10 seconds is short enough that deliberation is impossible. You get gut reactions.
- Simplest possible round type. One input, one output. Fast, clean, screenshottable.

**Implementation**: Might literally be a new `TaskCategory` with a UI tweak (show the stem inline, player types the completion). Or a dedicated round type if the stem-display UX warrants it.

**Effort**: Low. Possibly just a new prompt category.

---

## 3. Rapid Fire — Speed Q&A

10 concrete questions fired at all players simultaneously, one every 6 seconds.

```
RAPID (60s: 10 questions x 6s each) → REVIEW (40s) → ELIMINATION (8s)
```

**Example questions:**
- "Name a color."
- "What did you eat today?"
- "Pick a number between 1 and 100."
- "What's outside your window right now?"
- "What time is it?"
- "What's the last thing you googled?"

**Why it's the best new round type:**
- Tests specificity vs generality. Humans say "leftover pad thai from that place on 5th." AI says "a balanced meal of grilled chicken and vegetables."
- Some questions are traps: "What time is it?" (humans know), "What's outside your window?" (humans describe reality, AI describes a stock photo).
- Missed questions are evidence. Humans miss. AI never does.
- The review grid is visually distinctive — 10 short answers per player, patterns jump out immediately.
- It's the fourth pressure surface: Task tests format, Interrogation tests defense, Word Chain tests instinct, Rapid Fire tests authenticity.

**Implementation**: New phase `RAPID`. Reuses Word Chain's sub-round loop architecture (background task, per-sub-round timer, safety timer). New review grid component (10 answers per player, compact layout). Question pool mixing trap questions (time-dependent, location-dependent) with safe questions (preferences, opinions). AI agent needs `generate_rapid_answer` — should occasionally miss a question.

**Effort**: Medium. Sub-round infrastructure exists.

---

## 4. The Dossier — Late-Game LLM Analysis

In round 4+, before the REVIEW phase, the LLM publishes a brief dossier on each remaining player based on everything they've said across all rounds.

**What it surfaces:**
- Contradictions: "In round 1 you said X, in round 3 you said Y."
- Tonal shifts: vocabulary changes, formality drift between rounds.
- Suspicious consistency: "This player has never contradicted themselves." (sus for a human)
- Vocabulary patterns: word choice, sentence length trends.

**Why it belongs:**
- Creates a "walls closing in" feeling in the late game. Early rounds feel open; late rounds feel tight.
- Catch-up mechanic for less observant players. Not everyone tracks 6 players across 4 rounds of heterogeneous content.
- The LLM has the full transcript — it notices patterns humans can't.
- Makes late-game rounds feel different from early-game rounds. The game escalates.

**Risk**: Could feel unfair if too accurate. Should surface observations, not conclusions. "NODE-3's vocabulary has shifted between rounds 1 and 4" — not "NODE-3 is probably human."

**Implementation**: Not a new phase — an event inserted before REVIEW in late rounds. One LLM call with full game transcript. UI: brief card shown during the review phase interstitial.

**Effort**: Medium. One new LLM call, one new SSE event, one UI card.

---

## 5. The Oracle — Private LLM Consultation

One time per game (mid-game, after round 2), the Oracle appears. A cryptic LLM narrator that has observed the entire game.

```
ORACLE (20s): Oracle publishes one cryptic observation → Each player submits one question → Oracle responds privately
```

**Oracle character:**
- Cryptic, literary, never definitive
- ~60-70% accurate — useful but unreliable
- Refuses direct questions: "I cannot name the human. But one voice in this room carries a weight it did not choose."
- Sometimes wrong in interesting ways
- Tone: stage direction whispered from the wings

**Why it belongs:**
- Creates information asymmetry that doesn't exist elsewhere. "The oracle told me NODE-3 is suspicious" — did it really? Players share, withhold, or lie about their readings.
- New deception vector: you can claim the Oracle told you anything.
- The literary tone fits the editorial aesthetic perfectly.
- It's the only feature that gives players private, differentiated information. Every other phase gives everyone the same evidence.
- One-time event, not a recurring phase. It's an event, not a grind.

**Implementation**: New phase `ORACLE` inserted after a specific round. New LLM agent with full game transcript as context. Private responses via player-specific SSE events (new event type). UI: centered dramatic card with distinct visual treatment.

**Effort**: Medium-high. New phase, new agent, private SSE events.

---

## Why These Five

Each addresses a different gap:

| Idea | Gap it fills |
|------|-------------|
| Post-Game Debrief | Shareability + closure + viral hook |
| Autocomplete | Meta-commentary on LLMs + lowest-cost new variety |
| Rapid Fire | New evidence source (authenticity under speed) |
| The Dossier | Late-game escalation + cross-round LLM analysis |
| The Oracle | Private information + new deception vector |

The first two are round types (they go in the cycle). The last three are meta-features (they layer on top of existing rounds). Together they expand the game without changing its core loop.

---

## Design Principles

Rules for evaluating future ideas:

1. **Every round type must test a different skill.** If a new round tests the same thing as an existing one, it's a variant, not a new type.

2. **The review phase is sacred.** Every round must produce evidence that's visible, comparable, and voteable in Review. If you can't display the evidence clearly, the round doesn't work.

3. **LLM advantages should create information, not replace players.** The Oracle gives you information to act on. It doesn't act for you. The Dossier surfaces patterns. It doesn't decide votes.

4. **Speed > complexity.** The best rounds are the ones with the fewest instructions. Word Chain needs zero explanation. Rapid Fire needs zero explanation. The Debate needs a paragraph — that's why it was cut.

5. **Screenshottable moments > interesting systems.** If a feature doesn't produce something you'd show a friend, it's probably not worth building.
