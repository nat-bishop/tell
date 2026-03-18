# Game Design

## The Premise

"Be yourself, find the AI."

A group of players — some human, some AI — answer the same prompts. Then everyone votes, head-to-head, on which answer sounds more human. Highest score after 5 rounds wins. Big reveal at the end.

The frame flip: humans no longer pretend to be robots. They play as themselves. The AI players are the ones performing — trying to pass as human. This is the actual Turing test, made social and competitive.

The question isn't "can you hide your humanity?" It's "can you tell who's faking?"

## Why This Game, Right Now

"Is this AI?" has become a reflexive question. "Slop" was Merriam-Webster's Word of the Year 2025. Bot traffic exceeded human traffic for the first time. Dead Internet Theory went mainstream. A casual scroll through any feed now feels like a test.

Human or Not (AI21 Labs, 2023) proved 15 million people wanted to play "spot the AI" — but 1:1 chat couldn't sustain engagement. Two minutes, one binary guess, no social dynamics. Tell adds the layer that makes it replayable: it's not just "detect AI," it's "judge a room while being judged." Running scores, the big reveal, and the head-to-head matchup format create the emergent stories that 1:1 detection games can't.

## Design Vision

**Aesthetic**: Editorial minimalism. A screenplay unfolding in real-time. The page is the stage. Words are the only actors.

**References**: Linear (precision, restraint), Wordle (zero onboarding), the typography of a published play.

**The memorable thing**: It doesn't look like a game. It looks like literature happening to you.

### Diegetic Text

Phase transitions are voiced by a robot narrator persona — not a game UI label. `PhaseInterstitial` rotates through 5 robot voice archetypes (clinical, bureaucratic, military, malfunctioning, friendly) that shift per round. Each archetype issues directives for the incoming phase ("SUBMIT YOUR RESPONSE WITHIN THE ALLOTTED WINDOW.") rather than describing it neutrally. Situation lines reference cumulative game state ("round 3 of 5. scores are close.").

The cold open ("N UNITS ASSEMBLED / some are not what they seem") fires once when the game starts, before round 1. The landing page copy uses the same register: "a reverse turing test", "enter test →", "isolated examination".

## Typography

Two typefaces, each with a purpose:

- **Cormorant** (+ Cormorant SC) — literary content. Character names in small caps. Dialogue in regular weight. Warm, distinctly bookish.
- **IBM Plex Mono** — timer, system messages, phase labels. The mechanical layer.

The contrast between serif dialogue and monospace system text reinforces the theme: reading a play inside a machine.

## Color

```
--page:  #FAFAF8   warm off-white, like good paper
--ink:   #1C1C1A   warm near-black
--dim:   #9A9A92   secondary text, system messages
--rule:  #E5E5E0   dividers
--warm:  #B85C38   terracotta — ONLY for: timer warning, vote selection, "human" reveal
```

`--warm` appears in exactly three places. Everywhere else is ink on paper.

---

## The Two Games

Round type is selected dynamically each round — no repeat of the previous type.

Each creates different pressure. Matchup exposes voice and judgment simultaneously. Quick Draw is a speed test with a right answer — the gap between human and AI accuracy becomes visible without any social voting.

---

### Matchup — Head-to-Head

A constrained creative prompt. Everyone answers simultaneously. Then players are paired — all answers shown two at a time. Everyone votes on which of the two sounds more human. Winner of each head-to-head gets +1 point.

```
PROMPT (25s) → MATCHUP (sub-round loop, 12s each) → scoring → next round
```

~60-90 seconds per round depending on player count. Short answers leave nowhere to hide — every word is evidence.

#### The 7 Prompt Categories

Each category exploits a different AI blindspot or strength:

| Category | Example prompt | The tell |
|---|---|---|
| **haiku** | "Write a haiku about Monday mornings." | LLMs notoriously miscounting syllables. Getting it wrong might be the AI tell. Getting it right (slowly, on your fingers) is human. |
| **concise** | "Explain love in exactly 5 words." | LLMs are constitutionally verbose. They hedge, qualify, add context. The most concise answer is probably human. |
| **humor** | "Write a fortune cookie message that's unsettling." | AI jokes are structurally correct but soulless. The weird, slightly broken joke that makes one person snort is human. |
| **corporate** | "Write a polite way to say 'this meeting could have been an email.'" | AI has ingested millions of corporate emails. Being too polished is the tell. |
| **casual** | "Explain quantum physics using only slang." | AI casual sounds like a 45-year-old executive who just learned what "fire" means. The effort is visible. |
| **style** | "Describe breakfast like a nature documentary narrator." | AI style transfer is technically clean. Human impressions are funnier and uneven. |
| **emotional_task** | "Write the text you'd send at 2am to someone you miss." | AI empathy is a performance. "I validate your emotional experience" vs "hey. just thinking about you." |

42 prompts total (6 per category). No repeats, no same-category back-to-back.

#### How the Matchup Works

Players are paired in order (player 0 vs player 1, player 2 vs player 3, etc.). Odd player out gets a bye for that matchup loop — they don't appear in a head-to-head but their score accumulates normally. Each matchup shows both answers with no labels. All players vote on which sounds more human. The side with more votes wins; winning player gets +1.

#### What Makes It Fun

The constraint is the detector. When you only get 5 words or 17 syllables, there's nowhere for AI to hide behind qualifications and hedging. The head-to-head format makes the comparison visceral — you're not abstractly evaluating "is this AI," you're choosing between two specific answers. The judgment is concrete. The review produces the best screenshots: a haiku grid where one haiku is clearly from a person who has actually experienced Monday mornings.

**Skill tested**: Format fluency, creative economy, reading answers for humanity under time pressure.

---

### Quick Draw — The Evidence Round

No writing of your own. No head-to-head. A rapid sequence of multiple-choice challenges — estimation, common knowledge, trick questions, pattern completion. Everyone taps an option. Points awarded for correct answers.

```
BRAIN_TEST (5 challenges × 12s each, 75s safety timer) → BRAIN_TEST_RESULTS (15s) → next round
```

~90 seconds per round. The only round with a right answer.

#### How It Works

1. Five challenges appear one at a time, 12 seconds each. A new `BrainTestChallengeEvent` fires for each, with 4 option buttons.
2. All players tap one of the 4 options. AI selects an option via LLM.
3. After all challenges, `BRAIN_TEST_RESULTS` shows every player's selections with correct/incorrect indicators and running scores.
4. No vote. `do_after_brain_test()` starts the next round directly.

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

Quick Draw is a pressure valve. After a Matchup round with social judgment, a round with no voting feels like a reprieve. But it isn't — the choices become permanent record, accumulated in running scores that everyone can see. The gap between a human who second-guesses the trick question and an AI that answers confidently wrong creates information.

**Skill tested**: Speed, general knowledge, reading questions carefully under time pressure.

---

## Pacing

### Fixed 5 Rounds, No Elimination

The game runs exactly 5 rounds. No one leaves. Scores accumulate. The final reveal happens all at once.

This is a deliberate departure from social deduction orthodoxy (Among Us, Mafia, Werewolf) where elimination is the primary mechanic. Eliminating players creates spectators; five rounds is short enough that no one waits. The big-reveal structure concentrates drama at the end rather than distributing it across eliminations.

Total game: ~8-12 minutes. The party game sweet spot for a single-session experience.

### Round Variety

Two round types alternate (no consecutive repeat):

| Round | Duration | What it tests |
|-------|----------|--------------|
| Matchup | ~60-90s | Voice, creativity, human judgment |
| Quick Draw | ~90s | Speed, knowledge, AI accuracy |

The alternation prevents monotony. After judging creative answers, a round of objective questions resets the dynamic before returning to social reads.

### The Reveal

All roles are revealed simultaneously at game end — not one by one. Everyone sees everyone's true identity at the same moment. The post-reveal conversation ("UNIT-7 was AI the whole time? But the haiku was so good!") is half the entertainment.

The `FinalRevealEvent` fires before `GameOverEvent`, giving the frontend a reveal-first, score-second sequence.

---

## Humor

The game is funny. This section explains why, so future design decisions preserve it.

### The Jackbox Principle

"The game's job is to make the player look funny, not to be funny itself." The prompts are the setup; the players are the punchline. A good prompt reliably produces funny answers from normal people. The game never tells a joke — it creates conditions where players can't help being funny.

### Constraint Creates Comedy

"Explain love in 5 words" is funnier than "write something funny." The constraint eliminates the blank-page problem and narrows the comedic path. Every format restriction — word count, syllable count, style imitation — forces creative compression, which is where comedy lives. Time pressure amplifies this: you can't self-edit in 25 seconds, so you get gut reactions instead of polished responses.

### Three Sources of Humor

1. **The answers themselves** — constrained prompts produce inherently quotable responses. A haiku about Monday mornings written in 25 seconds will be imperfect and human and funny.
2. **The juxtaposition** — seeing answers head-to-head during matchup. One player wrote a cry for help; the AI wrote something technically perfect but soulless. The comparison is the joke.
3. **The reveal** — "UNIT-7 was AI" after everyone voted them as the most human. The post-reveal conversation is half the entertainment.

---

## Shared Mechanics

### Matchmaking

`play →` on the landing page routes to `/queue`. Enter a name, get a robot alias, join the rolling lobby. When enough humans queue up, a countdown fires and everyone is dropped into a game. Solo players wait up to 45s before starting with AI companions. Game is pre-populated with AI players (target total: 5-7).

Private game (host flow): create → share URL → host starts manually.

### Lobby

Players join via URL, receive robot aliases (UNIT-7, BOT-42 — assigned, not chosen). Host starts the game. AI players appear at game start, indistinguishable from humans in the UI.

### Voting (Matchup)

Each matchup is shown for 12 seconds. All players vote 0 (left) or 1 (right) — which answer sounds more human? Vote is changeable until the sub-round ends. The winning side's player gets +1 point. Ties: no point awarded.

### Scores

Running scores are visible throughout the game in the player bar. `Player.score` is a cumulative int. After each round, `MatchupResultsEvent` or `BrainTestResultsEvent` carries the updated `scores` dict (player_id → score). Final scores shown in the reveal.

### AI Personalities

5 personalities, randomly assigned to AI players (no duplicates per game). AI players try to pass as human. Each personality shapes answer generation and vote behavior:

| Name | Style | Vote Strategy |
|---|---|---|
| Paranoid | Suspicious, probing | Picks the answer that seems most designed to deceive |
| Chill | Short, casual, unremarkable | Random-ish |
| Overachiever | Detailed, analytical | Picks the least detailed answer as "most human" |
| Glitchy | Typos, repetition, erratic | Unpredictable |
| Philosopher | Abstract, existential | Picks the most emotionally resonant answer |

Each personality has a `fallback_response` for LLM failures.

### The Narrator

A persistent LLM show host fires at four transition points: game start, after all answers are submitted, between rounds, and at game over. The narrator is the robot running the test — dry, literary, increasingly invested. Its voice is `NARRATOR_SYSTEM_PROMPT` in `backend/llm/prompts.py`.

Narration arrives as a floating overlay (`Narration` component), auto-dismissing after 6 seconds. Game-over narration persists inline on the game over screen. The narrator never blocks game flow — `_fire_narration()` fires as `asyncio.create_task()`. It retains memory of its last 5 lines for continuity within a game.

The narrator knows everyone's role. It never reveals that directly — but the wording shifts as the game progresses.

## Edge Cases

- **Player disconnect**: Auto-skip during timed phases. Reconnect replays missed events.
- **Host disconnect**: Next connected human promoted to host.
- **Empty answer**: Submitted as "[no response]". Legitimate strategy.
- **Matchup bye**: Odd player out stored as `bye_player_id` on `RoundState`. They don't appear in a head-to-head but their score accumulates normally.
- **Vote tie in matchup**: No point awarded to either player.
- **Brain Test: no response to a challenge**: Shown as blank in results grid. No point.
- **All players tie at game end**: `winner_ids` contains all tied player IDs.
- **Matchmaking queue drop**: Player disconnecting from SSE auto-removes them from the queue.
