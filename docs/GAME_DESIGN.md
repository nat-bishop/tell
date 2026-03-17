# Game Design

## The Premise

Reverse Turing test as social deduction. Everyone claims to be a robot. Some are human. The AI players are genuinely AI. Humans must blend in by acting robotic; AI must blend in by acting natural-but-robotic. Voting eliminates suspected humans.

The robots are running the test. They pick tasks they believe will expose the humans hiding among them. This creates two kinds of comedy:

1. **Tasks robots ARE good at** — humans struggle to keep up (corporate writing, structure, summarization). The humor is humans sweating over a task that's trivial for machines.
2. **Tasks robots THINK they're good at** — but everyone knows they aren't (humor, being casual, counting syllables, emotional intelligence). The comedy is the robots' misplaced confidence.

The diegetic framing justifies the game's design: "Of course this round is a haiku challenge — the robots think they're great at haiku."

## Why This Game, Right Now

"Is this AI?" has become a reflexive question. "Slop" was Merriam-Webster's Word of the Year 2025. Bot traffic exceeded human traffic for the first time. Dead Internet Theory went mainstream. A casual scroll through any feed now feels like a test.

Human or Not (AI21 Labs, 2023) proved 15 million people wanted to play "spot the AI" — but 1:1 chat couldn't sustain engagement. Two minutes, one binary guess, no social dynamics. Tell adds the layer that makes it replayable: it's not just "detect AI," it's "deceive a group while reading a room." The multiplayer social deduction structure — alliances, betrayals, public accusations, private suspicions — creates the emergent stories that 1:1 detection games can't.

The reverse framing is the key insight: everyone pretends to be a robot. This creates comedy (humans sweating to sound artificial), strategic depth (AI blends in more easily when everyone's performing), and cultural resonance (we're all already performing for algorithms). The question isn't "can you spot the AI?" — it's "can you hide your humanity?"

## Design Vision

**Aesthetic**: Editorial minimalism. A screenplay unfolding in real-time. The page is the stage. Words are the only actors.

**References**: Linear (precision, restraint), Wordle (zero onboarding), the typography of a published play.

**The memorable thing**: It doesn't look like a game. It looks like literature happening to you.

### Diegetic Text

Phase transitions are voiced by a robot narrator persona — not a game UI label. `PhaseInterstitial` rotates through 5 robot voice archetypes (clinical, bureaucratic, military, malfunctioning, friendly) that shift per round. Each archetype issues directives for the incoming phase ("SUBMIT YOUR RESPONSE WITHIN THE ALLOTTED WINDOW.") rather than describing it neutrally. Spectators get distinct variants. Situation lines reference cumulative game state ("3 units remain. the machines grow confident.").

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

## The Four Games

Rounds cycle: **Task → Word Chain → Brain Test → Interrogation → Task → ...**

Each creates different pressure. Task exposes format fluency. Word Chain is instinctive and distributed. Brain Test is competitive — no one gets eliminated, but your answers become evidence. Interrogation concentrates pressure on one player for the longest, highest-stakes round. No single strategy is optimal across all four.

---

### Task — The Robots' Challenge

A constrained creative prompt. Write a haiku, a one-liner, a corporate memo. Everyone answers simultaneously. No questions, no interrogation. Straight to voting.

```
PROMPT (25s) → REVIEW (40s) → ELIMINATION (12s)
```

~77 seconds per round. The fastest game. Short answers leave nowhere to hide — every word is evidence.

#### The 7 Prompt Categories

Each category exploits a different AI blindspot or strength:

| Category | Example prompt | The tell |
|---|---|---|
| **haiku** | "Write a haiku about Monday mornings." | LLMs notoriously miscounting syllables. Getting it wrong might be the AI tell. Getting it right (slowly, on your fingers) is human. The robots designed this challenge thinking it would expose humans — instead it exposes them. |
| **concise** | "Explain love in exactly 5 words." | LLMs are constitutionally verbose. They hedge, qualify, add context. The most concise answer is probably human. |
| **humor** | "Write a fortune cookie message that's unsettling." | AI jokes are structurally correct but soulless. The weird, slightly broken joke that makes one person snort is human. |
| **corporate** | "Write a polite way to say 'this meeting could have been an email.'" | AI has ingested millions of corporate emails. Being too polished is the tell. |
| **casual** | "Explain quantum physics using only slang." | AI casual sounds like a 45-year-old executive who just learned what "fire" means. The effort is visible. |
| **style** | "Describe breakfast like a nature documentary narrator." | AI style transfer is technically clean. Human impressions are funnier and uneven. |
| **emotional_task** | "Write the text you'd send at 2am to someone you miss." | AI empathy is a performance. "I validate your emotional experience" vs "hey. just thinking about you." |

42 prompts total (6 per category). No repeats, no same-category back-to-back.

#### What Makes It Fun

The constraint is the detector. When you only get 5 words or 17 syllables, there's nowhere for AI to hide behind qualifications and hedging. The review phase — a grid of everyone's answers side-by-side — produces the best screenshots: a haiku grid where one haiku is clearly from a person who has actually experienced Monday mornings.

**Skill tested**: Format fluency, creative economy, knowing when imperfection is authentic.

---

### Interrogation — The Hot Seat

The group answers a prompt, then nominates one player for cross-examination. Everyone writes questions. An LLM narrator synthesizes all questions into one pointed paragraph. The nominated player responds. Then everyone votes.

```
PROMPT (45s) → NOMINATE (15s) → QUESTION (25s) → RESPOND (30s) → REVIEW (40s) → ELIMINATION (12s)
```

~167 seconds per round. The longest game. The pressure builds across five distinct phases.

#### How It Works

1. **PROMPT**: Server picks from 30 prompts across 5 categories. All players answer simultaneously.
2. **NOMINATE**: Everyone votes for who to interrogate. Plurality wins; ties broken randomly.
3. **QUESTION**: All non-nominated players write a follow-up question for the hot-seated player. The nominated player cannot submit questions — they only watch.
4. **RESPOND**: An LLM narrator synthesizes all questions into a single cross-examination paragraph. The nominated player responds to this synthesis, not the individual questions.
5. **REVIEW**: All answers, the synthesis, and the response are visible. Vote.
6. **ELIMINATION**: Reveal.

#### The 5 Prompt Categories

| Category | Example prompt | What it exposes |
|---|---|---|
| **emotional** | "Describe the last time you felt something you couldn't name." | Humans leak authenticity. AI simulates it. |
| **logical** | "If you had to pick one data structure to represent your personality, which?" | AI is suspiciously competent. Humans are endearingly wrong. |
| **creative** | "Invent a word for something that doesn't have one yet." | Hard for AI to be genuinely weird. |
| **philosophical** | "Is it better to be understood or to be interesting?" | AI hedges and considers both sides. Humans commit. |
| **social** (round 2+ only) | "Who is trying too hard right now?" | References in-game reality. Requires having actually been present. |

30 prompts total (6 per category). Social prompts excluded from round 1.

#### The Synthesis

All submitted questions are fed to an LLM narrator that weaves them into one cohesive cross-examination paragraph. This surfaces the sharpest angles, removes redundancy, and makes the interrogation feel like a tribunal rather than a pile-on. 5-second timeout; fallback is a numbered list of the raw questions.

#### What Makes It Fun

Concentrated pressure. One person in the spotlight. The synthesis makes every question count — the narrator sharpens weak questions and finds the through-line. The nominated player's response reveals everything: how they handle pressure, whether their personality is consistent between the original answer and the defense.

**Skill tested**: Defense under pressure, consistency, improvisation under scrutiny.

---

### Word Chain — The Association Test

No writing prompt. A seed word appears. Everyone submits one word association. The server picks the most unique submission as the next seed. Repeat 8 times. Review shows everyone's full chain side-by-side.

```
CHAIN (8 sub-rounds x 8s each, 64s safety timer) → REVIEW (40s) → ELIMINATION (12s)
```

~116 seconds per round. The most instinctive game. No time to deliberate.

#### How It Works

1. A seed word appears (from a pool of 110 curated words).
2. All players submit one word association. 8 seconds.
3. The server counts submissions. Words submitted by exactly one player (unique associations) are preferred over popular ones. The chosen word becomes the next seed.
4. Repeat 8 times. The chain grows on screen in real-time: `ocean → grandmother → kitchen → ...`
5. Review shows each player's full chain of associations side-by-side.

#### The Tension

Unique = interesting, but exposed. Popular = safe, but boring. You must simultaneously signal creativity and avoid standing out.

`ocean → waves → surfing → beach` is predictable — AI pattern.
`ocean → grandmother` (because of a childhood memory) is idiosyncratic — human signal.

The wrong association — the one that only makes sense if you've lived a specific life — is the most human signal possible. But submitting too-unique words risks standing out as suspicious.

#### What Makes It Fun

Speed. Instinct over deliberation. You can't overthink a word association in 8 seconds. The chain grows on screen in real-time, creating momentum. In review, the patterns are immediately visible: one player's chain is all synonyms, another's is all vibes, another's makes no sense at all. The round is the fastest, most visceral, and produces the clearest visual evidence.

**Skill tested**: Reaction speed, idiosyncratic thinking, calibrating uniqueness.

---

### Brain Test — The Evidence Round

No writing, no voting, no elimination. A rapid sequence of challenges — estimation, common knowledge, trick questions, pattern completion. Everyone competes. The winner earns an ability that affects the next REVIEW.

```
BRAIN_TEST (5 challenges × 12s each, 75s safety timer) → BRAIN_TEST_RESULTS (15s) → next round
```

~90 seconds per round. The only round with a right answer.

#### How It Works

1. Five challenges appear one at a time, 12 seconds each. A new `BrainTestChallengeEvent` fires for each.
2. All players type a free-form answer. AI answers via personality-aware LLM calls.
3. After all challenges, `BRAIN_TEST_RESULTS` shows every player's answers side-by-side with scores and the correct answer where applicable.
4. The highest scorer wins a random ability (PARTIAL SCAN or DOUBLE VOTE) announced in the interstitial before the next round.
5. No vote. No elimination. `do_after_brain_test()` starts the next round directly.

#### Scoring

| Challenge type | Scoring rule |
|---|---|
| **trick** / **pattern** | Fuzzy match against `correct_answer` → 1 point |
| **estimation** / **common_knowledge** | Unique answer (only one player gave it) → 1 point |

#### The 4 Challenge Types

| Type | Example | What it exposes |
|---|---|---|
| **estimation** | "How many piano tuners are in Chicago?" | Humans have calibrated intuitions; AI has memorized reference class answers. An unusually precise AI answer is a tell. |
| **common_knowledge** | "What is the boiling point of water at sea level?" | AI gets these trivially right. A human who's nervous might blank. |
| **trick** | "A rooster lays an egg on a roof — which side does it roll down?" | Tests whether players are actually reading vs. pattern-matching. AI can be tripped by surface framing. |
| **pattern** | "What comes next: 2, 4, 8, 16, ___?" | Humans show their work in how they phrase the answer. AI states the answer cleanly. |

20 challenges total (5 per type). `select_brain_test_challenges()` picks a balanced mix each round.

#### The Design Tension

Brain Test is a pressure valve. After an intense Interrogation or a chaotic Word Chain, a round with no voting feels like a reprieve. But it isn't — the answers become permanent record, and the winner's ability changes the next round's dynamics. "Why did UNIT-7 think water boils at 90°C?" is ammunition for REVIEW. The stakes are low in the moment and highest in retrospect.

The "no elimination" structure also resets paranoia. Players who were about to be targeted get a free round. The game breathes before it bites.

**Skill tested**: Speed, general knowledge, reading questions carefully under time pressure.

---

## Pacing

### The Tension Curve

Two forces drive every social deduction game (Marc LeBlanc's Dramatic Game Dynamics):

- **Uncertainty** — "Who's human?" Starts high, decreases as evidence accumulates.
- **Inevitability** — "Someone's getting eliminated." Starts low, increases with each vote.

The climax occurs at their intersection: enough evidence to suspect, not enough to be sure. Every round should deliver this arc in miniature, and the full game should deliver it across all rounds.

### Why Four Round Types Matter

Contrast-based intensity — never sustain maximum tension. The four round types oscillate:

| Round | Duration | Pressure type | Agency |
|-------|----------|---------------|--------|
| Task | ~77s | Low — fast, everyone equal | High (writing) then low (voting) |
| Word Chain | ~116s | Medium — distributed, instinctive | High (rapid-fire association) |
| Brain Test | ~90s | Low — competitive, no elimination | Pure performance (answering) |
| Interrogation | ~167s | High — one player in the spotlight | Mixed (writing, questioning, defending) |

Brain Test sits between Word Chain and Interrogation as a deliberate release valve. It accumulates evidence without demanding a verdict — the pressure deferred makes the following Interrogation hit harder.

This maps to the Among Us insight: alternate between high-agency/low-communication phases (writing answers) and low-agency/high-communication phases (reviewing + voting). Monotonous round lengths kill pacing; varied lengths keep attention.

### Timing

Total game: ~15-20 minutes (4-5 rounds). This is the party game sweet spot (15-45 minutes total, individual rounds 30s-3m).

Timer pressure for creative tasks: 25-45 seconds. Enough to think, not enough to overthink. Research shows moderate time pressure is the sweet spot — it bypasses self-censorship, which means imperfect answers under pressure are both funnier and more human. This is a feature, not a constraint.

### Late-Game Acceleration

Research says tension peaks should accelerate toward the ending. This happens naturally: fewer players = faster phases = quicker rounds. The final round with 3 players left moves noticeably faster than the opening round with 7.

Future consideration: shorter timers in round 4+ for explicit acceleration.

---

## Humor

The game is funny. This section explains why, so future design decisions preserve it.

### The Jackbox Principle

"The game's job is to make the player look funny, not to be funny itself." The prompts are the setup; the players are the punchline. A good prompt reliably produces funny answers from normal people. The game never tells a joke — it creates conditions where players can't help being funny.

### Constraint Creates Comedy

"Explain love in 5 words" is funnier than "write something funny." The constraint eliminates the blank-page problem and narrows the comedic path. Every format restriction — word count, syllable count, style imitation — forces creative compression, which is where comedy lives. Time pressure amplifies this: you can't self-edit in 25 seconds, so you get gut reactions instead of polished responses.

### Four Sources of Humor

1. **The answers themselves** — constrained prompts produce inherently quotable responses. A haiku about Monday mornings written in 25 seconds will be imperfect and human and funny.
2. **The juxtaposition** — seeing all answers side-by-side during review. One player wrote a corporate memo, another wrote a cry for help, the AI wrote something technically perfect but soulless. The comparison is the joke. (This is Quiplash's "head-to-head reveal" principle.)
3. **The deception** — watching someone desperately try to sound robotic. The human who writes "I am functioning within normal parameters" and the AI that writes the same thing. Who's performing? The uncertainty is comedic.
4. **The reveal** — "UNIT-7 was HUMAN" after everyone was sure they were a robot. The post-reveal conversation ("I KNEW it because of the haiku!") is half the entertainment.

### The Comedy of Misplaced Confidence

The diegetic framing (robots designed the test) creates comedy even before anyone writes anything. "Write a haiku" is funny because the robots think they're great at haiku — but LLMs notoriously can't count syllables. "Be casual" is funny because AI casual sounds like an executive who just discovered slang. The comedy is structural: the robots are confidently testing skills they're bad at.

### Prompt Design Principles

From Jackbox's published design research:

- **Start with funny words or relatable scenarios.** "Write a passive-aggressive out-of-office reply" is inherently funny. "Write a response" is not.
- **Balance specificity.** Too vague = blank-page paralysis. Too constrained = no room for personality. The sweet spot: a clear format with room for voice.
- **Ask questions you genuinely want answers to.** If the designer wouldn't laugh reading the responses, the prompt is wrong.
- **Vary format across categories.** Haiku, then one-liner, then word association, then hot-seat defense. Variety prevents fatigue and ensures different skills (and different types of humor) surface each round.

---

## Shared Mechanics

### Matchmaking

`play →` on the landing page routes to `/queue`. Enter a name, get a robot alias, join the rolling lobby. When enough humans queue up, a countdown fires and everyone is dropped into a game. Solo players wait up to 45s before starting with AI companions. Game is pre-populated with AI players (target total: 5-7).

Private game (host flow): create → share URL → host starts manually.

### Lobby

Players join via URL, receive robot aliases (UNIT-7, BOT-42 — assigned, not chosen). Host starts the game. AI players appear at game start, indistinguishable from humans in the UI.

### Voting

REVIEW runs 40 seconds split into three server-driven sub-phases:

1. **REVEAL** (0-8s): All answers visible. Absorb the evidence.
2. **DISCUSS** (8-26s): Live chat — players send short messages (120 chars, 3 max). Screenplay aesthetic: alias + message, no chat bubbles. AI players participate. If PARTIAL SCAN is active, scan results appear here.
3. **VOTE** (26-40s): Multi-vote UI + Comedy Cup row.

Players get `min(3, alive_count - 1)` votes. Votes are changeable until the timer expires. No early completion — the full window is always available.

Multi-vote means a coordinated group can focus suspicion. The discussion window gives that coordination a place to happen — or to be performed.

**Comedy Cup**: A secondary vote row in REVIEW lets players mark the funniest answer. One vote, changeable, can vote for yourself. The winner is announced during Elimination alongside the verdict.

### Abilities

The Brain Test winner earns one of two abilities that activates in the next REVIEW:

**PARTIAL SCAN**: At REVIEW start, the holder gets scan results on 2 players — one true role, one randomized (50/50 correct). Results are shuffled and broadcast to all players during DISCUSS. Nobody knows which result is verified — the uncertainty is the mechanic.

**DOUBLE VOTE**: The holder's votes count 2× during resolution. Announced in the phase interstitial; badge shown in PlayerBar. Simple, transparent, high-stakes.

Abilities clear after each round. Only one ability is active at a time.

### Elimination & Verdict

The elimination reveal is 12 seconds — long enough for a 5-step sequence with a dramatic beat before the role reveal. The stepped reveal:

1. **Vote map** — who voted for whom, voter aliases linking to target alias. The social graph becomes visible. Eliminated target highlighted in warm.
2. **Identity reveal** — "`NODE-3` was human." The moment of truth.
3. **Role context** — "N units remain."
4. **LLM verdict** — one sentence of literary commentary. Dry wit, referencing the eliminated player's actual answer. The verdict reframes the entire round — it's the punchline.
5. **Comedy Cup winner** — "funniest unit: UNIT-7" shown alongside the verdict.

3-second timeout on the verdict; fallback: no verdict. Maximum restraint for maximum tension.

This is the Secret Hitler litmus test: "A good game should leave your player with a story to tell their friends." Every elimination produces a retellable moment: the bold lie that almost worked, the dramatic accusation that turned out right, the AI that fooled everyone for three rounds, the human whose haiku was too perfect.

### Eliminated Players

The #1 design flaw in social deduction is eliminated players with nothing to do. Tell's approach:

- **Short games**: 15-20 minutes total. Elimination happens ~minute 5+. Waiting 10 minutes is tolerable, especially with entertainment value.
- **Information advantage**: Eliminated players see true identities. They know something the living don't. Spectating becomes satisfying because you're watching people make wrong decisions with incomplete information.
- **Future consideration**: Blood on the Clocktower's ghost vote — eliminated players get one vote in the final round. Their accumulated knowledge makes this vote dramatically weighted. Low-effort addition with high engagement value.

### AI Personalities

5 personalities, randomly assigned to AI players (no duplicates per game):

| Name | Style | Vote Strategy | Question Style | Fallback |
|---|---|---|---|---|
| Paranoid | Suspicious, probing | "Most suspiciously perfect" answer | Probes emotional authenticity | [scanning... interference detected] |
| Chill | Short, casual, unremarkable | Random-ish | Minimal effort | meh |
| Overachiever | Detailed, analytical | "Least detailed" answer | Demands specificity | [processing additional data streams...] |
| Glitchy | Typos, repetition, erratic | Unpredictable | Erratic follow-ups | [signal lost] |
| Philosopher | Abstract, existential | "Most emotionally authentic" | Existential probing | ... |

Each personality shapes answer generation, question writing, nomination strategy, vote behavior, and word chain associations.

### The Narrator

A persistent LLM show host fires at four transition points: game start, after all answers are submitted, between rounds, and at game over. The narrator is the robot running the test — dry, literary, increasingly invested. Its voice is `NARRATOR_SYSTEM_PROMPT` in `backend/llm/prompts.py`.

Narration arrives as a floating overlay (`Narration` component), auto-dismissing after 6 seconds. Game-over narration persists inline on the game over screen. The narrator never blocks game flow — `_fire_narration()` fires as `asyncio.create_task()`. It retains memory of its last 5 lines for continuity within a game.

The narrator is the only character in the game who knows everyone's role. It never reveals that directly — but the wording shifts as the game progresses.

## Edge Cases

- **Player disconnect**: Auto-skip during timed phases. Reconnect replays missed events.
- **Host disconnect**: Next connected human promoted to host.
- **Empty answer**: Submitted as "[no response]". Legitimate strategy.
- **No votes cast**: No elimination. Round advances.
- **Vote tie**: Random among tied. Displayed clearly.
- **Nomination tie**: Random among tied.
- **Hot-seated player submits question**: Rejected — 400 error.
- **All AI eliminated**: Humans win immediately.
- **<=2 players left**: Game ends.
- **Word Chain: no responses in a sub-round**: Server picks a random fallback association.
- **Brain Test: no responses to a challenge**: Shown as blank in results grid.
- **Matchmaking queue drop**: Player disconnecting from SSE auto-removes them from the queue.

## Explicitly Cut

Accounts, database, persistence, custom prompts, spectator mode (post-game), AI difficulty, anti-cheat, sound effects, complex animations, leaderboards, scoring, game history.
