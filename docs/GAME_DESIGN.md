# Game Design

## The Premise

Reverse Turing test as social deduction. Everyone claims to be a robot. Some are human. The AI players are genuinely AI. Humans must blend in by acting robotic; AI must blend in by acting natural-but-robotic. Voting eliminates suspected humans.

The robots are running the test. They pick tasks they believe will expose the humans hiding among them. This creates two kinds of comedy:

1. **Tasks robots ARE good at** — humans struggle to keep up (corporate writing, structure, summarization). The humor is humans sweating over a task that's trivial for machines.
2. **Tasks robots THINK they're good at** — but everyone knows they aren't (humor, being casual, counting syllables, emotional intelligence). The comedy is the robots' misplaced confidence.

The diegetic framing justifies the game's design: "Of course this round is a haiku challenge — the robots think they're great at haiku."

## Design Vision

**Aesthetic**: Editorial minimalism. A screenplay unfolding in real-time. The page is the stage. Words are the only actors.

**References**: Linear (precision, restraint), Wordle (zero onboarding), the typography of a published play.

**The memorable thing**: It doesn't look like a game. It looks like literature happening to you.

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

## The Three Games

Rounds cycle: **Task → Interrogation → Word Chain → Task → ...**

Each creates different pressure. Task exposes format fluency. Interrogation concentrates pressure on one player. Word Chain distributes tension across everyone simultaneously. No single strategy is optimal across all three.

---

### Task — The Robots' Challenge

A constrained creative prompt. Write a haiku, a one-liner, a corporate memo. Everyone answers simultaneously. No questions, no interrogation. Straight to voting.

```
PROMPT (25s) → REVIEW (40s) → ELIMINATION (8s)
```

~73 seconds per round. The fastest game. Short answers leave nowhere to hide — every word is evidence.

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
PROMPT (45s) → NOMINATE (15s) → QUESTION (25s) → RESPOND (30s) → REVIEW (40s) → ELIMINATION (8s)
```

~163 seconds per round. The longest game. The pressure builds across five distinct phases.

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
CHAIN (8 sub-rounds x 8s each, 64s safety timer) → REVIEW (40s) → ELIMINATION (8s)
```

~112 seconds per round. The most instinctive game. No time to deliberate.

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

## Shared Mechanics

### Matchmaking

`play →` on the landing page routes to `/queue`. Enter a name, get a robot alias, join the rolling lobby. When enough humans queue up, a countdown fires and everyone is dropped into a game. Solo players wait up to 45s before starting with AI companions. Game is pre-populated with AI players (target total: 5-7).

Private game (host flow): create → share URL → host starts manually.

### Lobby

Players join via URL, receive robot aliases (UNIT-7, BOT-42 — assigned, not chosen). Host starts the game. AI players appear at game start, indistinguishable from humans in the UI.

### Voting

Players get `min(3, alive_count - 1)` votes during the REVIEW phase. Votes are changeable until the timer expires. No early completion — the full review window is always available.

Multi-vote means a coordinated group can focus suspicion. A lone vote rarely eliminates. This rewards discussion — or the appearance of it.

### Elimination & Verdict

Vote tallies revealed → identity reveal ("`NODE-3` was human.") → one-line LLM verdict sentence. Maximum restraint for maximum tension.

The verdict is generated by an LLM narrator with a literary, dry-wit tone — one sentence referencing the eliminated player's actual answer. 3-second timeout; fallback: no verdict.

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
- **Matchmaking queue drop**: Player disconnecting from SSE auto-removes them from the queue.

## Explicitly Cut

Accounts, database, persistence, custom prompts, spectator mode (post-game), AI difficulty, anti-cheat, sound effects, complex animations, leaderboards, scoring, game history.
