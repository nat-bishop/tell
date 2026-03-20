# Game Design

## The Premise

"Be yourself, find the AI."

A group of players — some human, some AI — answer the same prompts. Then everyone votes on which answers sound most human. Most-suspected players lose points. Highest score after 5 rounds wins. Big reveal at the end.

The frame flip: humans no longer pretend to be robots. They play as themselves. The AI players are the ones performing — trying to pass as human. This is the actual Turing test, made social and competitive.

The question isn't "can you hide your humanity?" It's "can you tell who's faking?"

## Why This Game, Right Now

"Is this AI?" has become a reflexive question. "Slop" was Merriam-Webster's Word of the Year 2025. Bot traffic exceeded human traffic for the first time. Dead Internet Theory went mainstream. A casual scroll through any feed now feels like a test.

Human or Not (AI21 Labs, 2023) proved 15 million people wanted to play "spot the AI" — but 1:1 chat couldn't sustain engagement. Two minutes, one binary guess, no social dynamics. Tell adds the layer that makes it replayable: it's not just "detect AI," it's "judge a room while being judged." Running scores, the big reveal, and the gallery vote format create the emergent stories that 1:1 detection games can't.

## Design Vision

**Aesthetic**: Editorial minimalism. A screenplay unfolding in real-time. The page is the stage. Words are the only actors.

**References**: Linear (precision, restraint), Wordle (zero onboarding), the typography of a published play.

**The memorable thing**: It doesn't look like a game. It looks like literature happening to you.

### Diegetic Text

Phase transitions are voiced by a robot narrator persona — not a game UI label. `TransitionOverlay` rotates through 5 robot voice archetypes (clinical, bureaucratic, military, malfunctioning, friendly) that shift per round. Each archetype issues directives for the incoming phase ("SUBMIT YOUR RESPONSE WITHIN THE ALLOTTED WINDOW.") rather than describing it neutrally. Situation lines reference cumulative game state ("round 3 of 5. scores are close.").

The cold open ("N SUBJECTS DETECTED / some are not what they seem") fires once when the game starts, before round 1. The landing page copy uses the same register: "a reverse turing test", "enter test →", "isolated examination".

## Typography

Two typefaces, each with a purpose:

- **Cormorant** (+ Cormorant SC) — literary content. Character names in small caps. Dialogue in regular weight. Warm, distinctly bookish.
- **IBM Plex Mono** — timer, system messages, phase labels. The mechanical layer.

The contrast between serif dialogue and monospace system text reinforces the theme: reading a play inside a machine.

## Color

```
--page:    #0F1114   dark background
--surface: #1A1D23   card/panel background
--raised:  #242830   elevated surface
--ink:     #E8E6E3   primary text
--dim:     #6B7084   secondary text, system messages
--rule:    #2A2D35   dividers
--warm:    #E07A5F   terracotta — ONLY for: timer warning, vote selection, "human" reveal
--cold:    #5B8FB9   AI blue — system accents, cold indicators
```

`--warm` is reserved for moments of human signal. Everywhere else is ink on dark.

---

## The Four Game Types

Round type is selected dynamically each round — no repeat of the previous type.

Each creates different pressure. Gallery Vote exposes voice and judgment simultaneously. Quick Draw is objective — no social reads, just accuracy. Wager reveals how people reason about uncertainty. Signal tests whether you can decode a deliberately constrained communication.

---

### Gallery Vote — Find the AI

A linguistic task prompt. Everyone answers simultaneously. Then all answers are shown at once and everyone votes for the player who sounds most human. Votes received = negative points (−1 per vote). Being suspected costs you.

```
PROMPT (45s) → ACTIVE (all answers visible, tap to vote)
  → RESULTS (vote counts, 8s) → next round
```

~60-75 seconds per round. Task quality leaves nowhere to hide — every word is evidence.

#### The 7 Prompt Categories

Each category exploits a different AI blindspot:

| Category | Example prompt | The tell |
|---|---|---|
| **style_transfer** | "Rewrite 'I had a terrible day at work' as a pirate would say it." | AI style transfer is technically clean. Human impressions are funnier and uneven. |
| **translation** | "Translate to French: 'The meeting has been rescheduled to Thursday.'" | AI is fluent; humans miss accents or overthink idioms. The too-perfect translation is the tell. |
| **pattern** | "Complete the sequence: A, C, E, G, ___" | AI answers instantly and correctly. A human might second-guess or overthink it. |
| **grammar** | "Fix the grammar: 'Me and him went to the store yesterday, we buyed milk.'" | AI corrections are impeccable. Human fixes might overcorrect or add voice. |
| **format_conversion** | "Rewrite as a haiku: 'The sunset was beautiful over the calm ocean.'" | AI haiku are syllabically correct but lifeless. Human haiku are imperfect and evocative. |
| **summary** | "Summarize in one sentence: [3-sentence passage]" | AI summaries are precise but generic. Humans compress differently — they notice different things. |
| **rewrite** | "Make this sentence casual: 'I would like to inquire about the availability...'" | AI casual sounds like a 45-year-old executive who just learned what "fire" means. |

36 prompts total (5 per category, some with 6). No repeats, no same-category back-to-back.

#### How the Gallery Vote Works

All answers are shown at once with player aliases visible. Each player taps one answer — voting for the player who sounds most human. You cannot vote for yourself. Votes are changeable until the timer expires or all votes are in. After voting, `TaskHandler.build_results()` tallies `gallery_votes` and returns score deltas: `−1` for each vote received.

#### What Makes It Fun

The scoring inversion is the key: you want to be overlooked, not celebrated. The most "human-sounding" answer loses points. This creates a perverse incentive — being too polished, too AI-like all have the same cost. The gallery format (all answers visible at once) means you're comparing the whole room.

**Skill tested**: Linguistic imperfection, reading the room for AI tells under time pressure.

---

### Quick Draw — The Evidence Round

No writing of your own. A rapid sequence of multiple-choice challenges — estimation, common knowledge, trick questions, pattern completion. Everyone taps an option. Points awarded for correct answers.

```
ACTIVE (5 challenges × 12s each, 75s safety timer) → RESULTS (15s) → next round
```

~75 seconds per round. The only round with a right answer.

#### How It Works

1. Five challenges appear one at a time, 12 seconds each. A new `SubRoundEvent(round_type="brain_test", ...)` fires for each, with 4 option buttons.
2. All players tap one of the 4 options. AI selects an option via LLM.
3. After all challenges, `RESULTS` phase shows every player's selections with correct/incorrect indicators and running scores.
4. No vote. `do_results_complete()` starts the next round directly.

#### Scoring

Pure correctness: `selected_index == correct_index` → 1 point per challenge. No fuzzy matching.

#### The 4 Challenge Types

| Type | Example | What it exposes |
|---|---|---|
| **estimation** | "How many piano tuners are in London?" (4 options) | Tests calibrated intuition vs. AI's tendency to pick precise answers. |
| **common_knowledge** | "Which country has the most time zones?" (4 options) | AI gets these trivially right. A human under pressure might second-guess. |
| **trick** | "A rooster lays an egg on a roof — which side?" (4 options) | Tests whether players read carefully vs. pattern-match. Trick questions catch AI. |
| **pattern** | "What comes next: 2, 6, 12, 20, ?" (4 options) | Speed of recognition. The right answer reveals nothing; the wrong one reveals everything. |

21 challenges total across 4 types. `select_brain_test_challenges()` picks a balanced mix each round.

#### The Design Tension

Quick Draw is a pressure valve. After a Gallery Vote round with social judgment, a round with no voting feels like a reprieve. But it isn't — the choices become permanent record. The gap between a human who second-guesses the trick question and an AI that answers confidently wrong creates information.

**Skill tested**: Speed, general knowledge, reading questions carefully under time pressure.

---

### Wager — Estimation + Betting

Numerical estimation followed by social betting. Everyone guesses a number, then bets on whose guess is closest. No creativity — just calibrated intuition and reading your opponents.

```
ACTIVE: 3 questions × [GUESS 15s → BET 15s], 100s safety timer
→ RESULTS (15s) → next round
```

~105 seconds per round. Scoring is transparent — you can see all guesses before betting.

#### How It Works

1. A question appears with a number line range (e.g., "How many astronauts have walked on the Moon?" 0–100). All players drag a marker to their estimate.
2. After the GUESS window, all guesses are revealed. Players then bet on whose guess is closest. Self-betting allowed.
3. After 3 questions: `RoundResultsEvent` carries final scores and a breakdown per question.

#### Scoring

+1 for having the closest guess. +1 for betting on a player with the closest guess. Max 2 points per question, 6 total. Ties in closest guess: all tied players get the +1.

#### The 6 Question Categories

`geography`, `science`, `history`, `pop_culture`, `economics`, `nature`. 26 questions total. `select_wager_questions()` picks a category-diverse mix of 3 each round.

#### What Makes It Fun

The bet phase creates a reveal moment mid-round. You see your opponents' guesses, assess who might be closest, and decide whether to self-bet or chase someone else's confident number. AI guesses are personality-driven — an eccentric AI might anchor to a wild number. A sardonic one might bet on itself reflexively.

**Skill tested**: Numerical calibration, reading confidence in opponents, risk assessment.

---

### Signal — Phrase Transformation

Drawful-style. Each player gets a secret phrase and everyone uses the same constraint to transform it. Others try to guess the original.

```
PROMPT (20s — each player sees their secret phrase + shared constraint, submits transformation)
→ ACTIVE: N sub-rounds × 12s each — one featured player's transformation per sub-round
→ LLM batch-judges all guesses → RESULTS (15s) → next round
```

~90-120 seconds per round depending on player count.

#### How It Works

1. During PROMPT: each player sees their secret phrase (e.g., "a dog chasing a squirrel") and the shared constraint (e.g., "Only questions — describe using only questions, no statements"). They write their transformation.
2. During ACTIVE: one player's transformation is featured per sub-round. All other players read it and type their guess at the original phrase.
3. After all sub-rounds: LLM judges all guesses via batch Y/N format (parallelized per featured player). Fuzzy match fallback if LLM fails.
4. RESULTS: shows phrase / transformation / all guesses with correct/incorrect judgment cards per player.

#### Scoring

+1 per correct guess (guesser). +1 for the transmitter if >= half of guessers got it right. LLM judging uses semantic equivalence — not exact wording.

#### The Constraints

15 shared constraints, selected without repeat. Examples:

| Constraint | Instruction |
|---|---|
| Only questions | Describe the phrase using only questions. No statements. |
| No nouns | Describe the phrase without using any nouns. |
| Opposite day | Describe the opposite of the phrase. Everything reversed. |
| As a recipe | Describe the phrase as if it were a cooking recipe. |
| News headline | Describe the phrase as a breaking news headline. |
| Text message | Describe the phrase as a casual text to a friend. Use abbreviations. |

40 secret phrases — concrete everyday scenarios ("stepping on a Lego barefoot", "trying to fold a fitted sheet"). Must be visually evocable for constraint-based transformation.

#### What Makes It Fun

The constraint forces creative compression under absurd rules. "A dog chasing a squirrel" transformed via "Only questions" becomes something like "Why is it always the squirrels? Why can't we just walk?" — which may or may not be guessable. The judging moment (does the LLM think "a furious pursuit in the park" counts?) creates tension. AI players transform and guess via LLM — their constraints produce characteristically flat transformations, which ironically makes them easier to decode.

**Skill tested**: Creative constraint satisfaction, theory-of-mind (can others decode what you transformed?), pattern-matching under time pressure.

---

## Pacing

### Fixed 5 Rounds, No Elimination

The game runs exactly 5 rounds. No one leaves. Scores accumulate. The final reveal happens all at once.

This is a deliberate departure from social deduction orthodoxy (Among Us, Mafia, Werewolf) where elimination is the primary mechanic. Eliminating players creates spectators; five rounds is short enough that no one waits. The big-reveal structure concentrates drama at the end rather than distributing it across eliminations.

Total game: ~8-12 minutes. The party game sweet spot for a single-session experience.

### Round Variety

Four round types, no consecutive repeat:

| Round | Duration | What it tests |
|-------|----------|--------------|
| Gallery Vote | ~60-75s | Linguistic imperfection, reading the room |
| Quick Draw | ~75s | Speed, knowledge, AI accuracy |
| Wager | ~105s | Numerical calibration, social betting |
| Signal | ~90-120s | Creative constraint, theory-of-mind |

The variety prevents monotony. Each round type creates distinct information — linguistic style, factual accuracy, quantitative calibration, decoding skill. No single strength dominates across all four.

### The Reveal

All roles are revealed simultaneously at game end — not one by one. Everyone sees everyone's true identity at the same moment. The post-reveal conversation ("UNIT-7 was AI the whole time? But the transformation was so good!") is half the entertainment.

The `FinalRevealEvent` fires before `GameOverEvent`, giving the frontend a reveal-first, score-second sequence.

---

## Humor

The game is funny. This section explains why, so future design decisions preserve it.

### The Jackbox Principle

"The game's job is to make the player look funny, not to be funny itself." The prompts are the setup; the players are the punchline. A good prompt reliably produces funny answers from normal people. The game never tells a joke — it creates conditions where players can't help being funny.

### Constraint Creates Comedy

"Rewrite this as a pirate" is funnier when you can see everyone else's version simultaneously. The constraint eliminates the blank-page problem and narrows the comedic path. Every format restriction — style imitation, format conversion, transformation rule — forces creative compression. Time pressure amplifies this: you can't self-edit in 12 seconds, so you get gut reactions instead of polished responses.

### Three Sources of Humor

1. **The answers themselves** — constrained prompts produce inherently quotable responses. "Make this casual: 'I would like to inquire about the availability of the aforementioned product'" produces wildly different results in 12 seconds.
2. **The juxtaposition** — seeing all answers together in the gallery. One player's translation has a charming error; the AI's is flawless and sterile. The comparison is the joke.
3. **The reveal** — "UNIT-7 was AI" after everyone voted them as the most human. The post-reveal conversation is half the entertainment.

---

## Shared Mechanics

### Matchmaking

`play →` on the landing page routes to `/queue`. Enter a name, get a robot alias, join the rolling lobby. When 2+ humans queue, a countdown fires and everyone drops into a game filled to 8 total with AI players.

Private game (host flow): create → share URL → host starts manually.

### Lobby

Players join via URL, receive robot aliases (UNIT-7, BOT-42 — assigned, not chosen). Host starts the game. AI players appear at game start, indistinguishable from humans in the UI.

### Voting (Task / Gallery Vote)

All answers are shown at once during the ACTIVE phase. Each player taps one answer — voting for the player who sounds most human. Cannot vote for yourself. Vote is changeable until time expires or all votes are in. Votes received = −1 point each.

### Scores

Running scores are visible throughout the game in the HUD panel. `Player.score` is a cumulative int. After each round, `RoundResultsEvent` carries the updated `scores` dict (player_id → score). Final scores shown in the reveal.

### AI Personalities

5 personalities, randomly assigned to AI players (no duplicates per game). AI players try to pass as human. Each personality shapes answer generation and vote behavior:

| Name | Style | Vote Strategy |
|---|---|---|
| Anxious | Overthinker, hedges, shares tangents | Overthinks the comparison |
| Chill | Low-effort, brief, casual | Picks casually |
| Earnest | Warm, specific anecdotes, overshares | Picks the most emotionally resonant answer |
| Eccentric | Unexpected angles, non-sequiturs | Unpredictable |
| Sardonic | Dry, world-weary, sharp observations | Picks the most polished answer as suspicious |

Each personality has a `fallback_response` for LLM failures.

### The Narrator

A persistent LLM show host fires at four transition points: game start, after all answers are submitted, between rounds, and at game over. The narrator is the robot running the test — dry, literary, increasingly invested. Its voice is `NARRATOR_SYSTEM_PROMPT` in `backend/llm/prompts.py`.

Narration arrives as a floating overlay (`FacilityNarration` component), auto-dismissing after 6 seconds. Game-over narration persists inline on the game over screen. The narrator never blocks game flow — `_fire_narration()` fires as `asyncio.create_task()`. It retains memory of its last 5 lines for continuity within a game.

The narrator knows everyone's role. It never reveals that directly — but the wording shifts as the game progresses.

## Edge Cases

- **Player disconnect**: Auto-skip during timed phases. Reconnect replays missed events.
- **Host disconnect**: Next connected human promoted to host.
- **Empty answer**: Submitted as "[no response]". Legitimate strategy.
- **Gallery vote: no votes on a player**: Zero vote count shown in results. No score change for that player.
- **Brain Test: no response to a challenge**: Shown as blank in results grid. No point.
- **Wager: player misses guess window**: Cannot be a bet target (route validates target has a guess).
- **Signal: featured player cannot guess their own phrase**: Route rejects `player_id == featured_pid`.
- **Signal: LLM judge fails**: Falls back to fuzzy match (case-insensitive substring containment).
- **Signal: no guesses for a featured player**: Score deltas are empty for that sub-round; transmitter gets no bonus.
- **All players tie at game end**: `winner_ids` contains all tied player IDs.
- **Matchmaking queue drop**: Player disconnecting from SSE auto-removes them from the queue.
