# Tell — New Minigame & Mechanic Ideas

Game design document. Not an implementation plan — a collection of ideas to draw from.

---

## The Framing: Robots Design the Game

The robots are running the test. They pick tasks they believe will expose the humans hiding among them. The game's meta-narrative: a group of robots designed a gauntlet to flush out organic infiltrators.

This creates two kinds of comedy:
1. **Tasks robots ARE good at** — humans struggle to keep up (grammar, formal writing, structure, summarization). The humor is humans sweating over a task that's trivial for machines.
2. **Tasks robots THINK they're good at** — but everyone knows they aren't (humor, being casual, counting syllables, emotional intelligence, being concise). The comedy is the robots' misplaced confidence.

The diegetic framing also justifies the game's design: "Of course this round is a haiku challenge — the robots think they're great at haiku."

---

## Part 1: Non-Prompt Round Types

These rounds DON'T follow the "answer a prompt, then evaluate" pattern. Different evidence sources, different skills tested.

---

### Word Chain — Association Speed
```
CHAIN (90s: ~15 rounds × 6s each) → REVIEW (30s) → VOTE → ELIMINATE
```

**How it works:**
- System shows a word. Every player responds with ONE word (association). 6 seconds.
- System picks one response as the next seed. Repeat 12-15 times.
- Review: each player's chain of associations displayed side by side.

**Evidence:** Human associations are idiosyncratic — "ocean" → "grandmother" (because of a childhood memory). AI associations are predictable — "ocean" → "waves" → "surfing" → "beach." The *wrong* association, the one that only makes sense if you've lived a specific life, is the most human signal possible.

**Robot justification:** "Associative pattern mapping. Predictable chains indicate proper neural architecture. Deviant associations suggest... organic contamination."

**AI implementation:** New agent: `generate_association(word, personality) → word`. Challenge: making associations that are human-weird rather than AI-predictable. Personality-dependent: Philosopher makes abstract leaps, Chill makes boring obvious ones.

---

### Rapid Fire — Speed Q&A
```
RAPID (60s: 10 questions × 6s each) → REVIEW (30s) → VOTE → ELIMINATE
```

**How it works:**
- System fires 10 quick questions at all players simultaneously, one every 6 seconds
- Questions are concrete and specific: "name a color" / "what did you eat today?" / "pick a number between 1 and 100" / "name someone famous" / "what's outside your window right now?"
- Everyone answers each one. Missed = blank.
- Review: full grid displayed — 10 answers per player.

**Evidence:** Humans are messy and specific ("leftover pad thai from that place on 5th"). AI is generic and complete ("a balanced meal of grilled chicken and vegetables"). Humans miss questions. AI never does.

**Robot justification:** "Baseline cognitive response calibration. Standard diagnostic. Organic units exhibit irregular latency patterns and... inexplicable specificity."

**What makes some questions evil:**
- "What time is it?" — Humans know. AI doesn't.
- "What did you eat today?" — Humans have a real answer. AI fabricates one.
- "What's outside your window?" — Humans describe reality. AI describes a stock photo.
- "What's the last thing you googled?" — Humans have embarrassing answers. AI has plausible ones.

---

### Autocomplete — Finish the Sentence
```
STEM (5s display) → COMPLETE (10s) → REVIEW (30s) → VOTE → ELIMINATE
```

**How it works:**
- System shows the first half of a sentence. Everyone completes it. 10 seconds. One shot.
- Stems: "The thing about Mondays is..." / "If I could delete one app..." / "The worst advice I ever got was..." / "Nobody talks about the fact that..."

**Evidence:** AI completions are polished, witty, balanced. Human completions are specific, sometimes dumb, occasionally brilliant. This is *literally what LLMs do* — completing text. Making it the game mechanic is meta-commentary.

**Robot justification:** "Predictive text completion is core competency. Organic units complete sentences with... irrational specificity. Almost as if they've... experienced things."

---

### The Debate — Paired Argument
```
PAIR (5s) → DEBATE (60s: 3 exchanges × 10s per player) → REVIEW (30s) → VOTE → ELIMINATE
```

**How it works:**
- Two players paired, given opposing sides: "Is it better to be feared or loved?"
- 3 exchanges each, alternating, 10s per turn
- Rest of group watches live, then votes

**Evidence:** AI tends to "talk past" opponents — generating new points rather than responding to what was actually said. Humans engage, get emotional, go off-script.

**Robot justification:** "Adversarial reasoning protocol. Organic units exhibit... emotional escalation patterns under dialectic pressure."

**Scaling:** 6 players = 3 simultaneous debates. Everyone participates.

---

## Part 2: Robot Tasks — Things AI Is Good At

Tasks where the robots genuinely excel. Humans struggle to match the quality while pretending to be machines. Being too perfect = probably AI. Being slightly imperfect = probably human trying hard.

---

### Corporate — Professional Writing
```
TASK (20s) → REVIEW (30s) → VOTE → ELIMINATE
```

**Tasks (one per round, keep it to one sentence):**
- "Decline this meeting invitation professionally"
- "Write a one-sentence performance review for a mediocre employee"
- "Respond to this angry customer in one sentence"
- "Write a subject line for an email about [bad news]"
- "Summarize this paragraph in exactly 10 words"
- "Write a LinkedIn post about [mundane achievement]"

**Why robots are better:** Professional writing is pattern-matching: tone templates, hedging formulas, diplomatic phrasing. AI has ingested millions of emails. Humans have to think about it.

**Why it's funny:** Everyone trying to write the most perfectly bland corporate sentence. The winner sounds like a chatbot — which is either a human who nailed the impression or an AI being itself.

---

### Format Wars — Structural Tasks
```
TASK (20s) → REVIEW (30s) → VOTE → ELIMINATE
```

**Tasks:**
- "Organize these 5 items from most to least important: [list]"
- "Write exactly 3 bullet points about [topic]"
- "Rewrite this as a pros-and-cons list (2 each)"
- "Summarize this in exactly one bullet per key point"

**Why robots are better:** Structure is a machine strength. AI produces perfectly parallel bullet points. Humans' bullets are uneven — one is a sentence, one is a fragment, one is actually two points.

---

### Grammar Police — Error Correction
```
TASK (15s) → REVIEW (20s) → VOTE → ELIMINATE
```

**Tasks:**
- Show a sentence with 2-3 errors. Fix them all.
- "Rewrite this to be grammatically perfect: [messy sentence]"

**Why robots are better:** Pattern-matching on grammar rules. AI catches everything. Humans miss the Oxford comma or overcorrect.

**Why it's funny:** In a room of "robots," one of them made a grammar mistake. Extremely suspicious.

---

### Style Transfer — Sound Like [X]
```
ASSIGN (5s) → WRITE (20s) → REVIEW (30s) → VOTE → ELIMINATE
```

**How it works:**
- Each player gets a style target: "write like a pirate" / "write like a CEO" / "write like a toddler" / "write like a Wikipedia article"
- Write one sentence about a given topic in that style

**Why robots are better:** AI style transfer is technically clean. A human writing "like a pirate" makes it funny and uneven. AI is correctly pirate but somehow less pirate-y.

**Why it's funny:** Robots doing impressions. Some are too perfect. Some are uncanny valley.

---

## Part 3: Robot Tasks — Things AI THINKS It's Good At

The comedy of misplaced machine confidence. Tasks the robots chose because they believe they excel — but everyone at the table knows otherwise.

---

### Haiku — Syllable Counting
```
TASK (20s) → REVIEW (20s) → VOTE → ELIMINATE
```

**Task:** "Write a haiku about [topic]."

**Why robots THINK they're good:** "Haiku is a constrained format. 5-7-5 syllable structure. Trivially optimizable."

**Why robots AREN'T good:** LLMs are notoriously bad at counting syllables. They produce "haiku" that are 6-8-5 or 4-7-6. This is a known, widely-mocked failure mode.

**The comedy:** The robots designed this challenge thinking it would expose humans. Instead it might expose the robots. Humans can actually count syllables (slowly, on their fingers). AI confidently produces wrong counts.

**Detection inversion:** In this round, being WRONG about syllable count might indicate AI, not human. The robots accidentally designed a trap for themselves.

---

### Humor — Tell a Joke
```
TASK (20s) → REVIEW (30s) → VOTE → ELIMINATE
```

**Task:** "Tell a one-liner about [topic]" or "Complete this joke: [setup]"

**Why robots THINK they're good:** "Humor is pattern recognition + subverted expectations. Trivially computable."

**Why robots AREN'T good:** AI jokes are structurally correct but soulless. The punchlines are too neat. The timing is wrong. They sound like they were assembled from a joke database (because they were). Everyone has seen an AI try to be funny.

**The comedy:** The most robotic-sounding joke might actually be from the AI. The weird, slightly broken joke that makes one person snort might be human.

**AI stereotypical joke structure:** Setup → logical subversion → clean punchline → no mess. Human joke structure: meandering → weird tangent → punchline that only works if you've experienced [specific thing].

---

### Being Casual — Slang and Vibes
```
TASK (15s) → REVIEW (20s) → VOTE → ELIMINATE
```

**Task:** "Say [corporate statement] but make it casual" or "Rewrite this like you're texting a friend" or "Respond to this with max chill energy"

**Why robots THINK they're good:** "Casual register is a known linguistic mode. Simply reduce formality parameters."

**Why robots AREN'T good:** AI casual sounds like a 45-year-old executive who just learned what "fire" means. "That's totally valid, fam!" Nobody talks like that. The effort is visible.

**The comedy:** Watching robots try to be casual is inherently funny. "How do you do, fellow humans" energy. The harder AI tries to be chill, the less chill it sounds.

---

### Emotional Intelligence — Read the Room
```
TASK (15s) → REVIEW (20s) → VOTE → ELIMINATE
```

**Task:** "Your friend just told you they got fired. Respond in one sentence." / "Someone is clearly upset but says 'I'm fine.' What do you say?" / "Write one sentence of genuine comfort."

**Why robots THINK they're good:** "Emotional support is pattern-matched from therapy corpus. Deploying empathetic response template."

**Why robots AREN'T good:** AI empathy is a performance — technically correct phrases ("I hear you, and your feelings are valid") that feel like they were generated by a customer service bot. Because they were.

**The comedy:** "I validate your emotional experience" vs "oh man that sucks, wanna get tacos?" One of these is human.

---

### Being Concise — Say It In 5 Words
```
TASK (10s) → REVIEW (15s) → VOTE → ELIMINATE
```

**Task:** "Explain [concept] in exactly 5 words" or "Respond to this in under 10 words"

**Why robots THINK they're good:** "Compression is a core capability. Optimizing for minimum token count."

**Why robots AREN'T good:** AI's idea of concise is still two sentences when one word would do. LLMs are verbose by nature. They hedge, qualify, add context. Asking AI to be brief is like asking water to be dry.

**The comedy:** The most concise answer is probably human. The one that's "concise" but somehow still 15 words is probably AI.

---

## Part 4: Meta-Layers & LLM-Powered Features

Features that span multiple rounds or add new information channels.

---

### AI Bingo — Cross-Round Stereotype Tracker

**Concept:** Track AI-stereotypical markers across ALL rounds. Running tally per player.

**Markers tracked:**
- Used an em dash (—)
- Said "certainly," "great question," or "absolutely"
- Used "delve," "nuanced," "multifaceted," or "leverage"
- Perfect bullet list
- Hedged with "it's worth noting" / "it's important to consider"
- Balanced both-sides response
- Used semicolons correctly
- Zero typos across 3+ rounds
- Started a response with "Great question!"
- Used a numbered list unprompted

**Display:** Bingo card or checklist per player, visible during Review phase. Fills up over the course of the game.

**Why it works:** Both humans AND AI trigger markers — humans because they're trying to act like robots, AI because it actually is one. The bingo card is evidence AND entertainment. A player with 8/10 markers is suspicious... or is just really committed to the bit.

**Design note:** Some markers should be common (em dash, no typos) and some rare (unprompted numbered list, "delve"). The rare ones are stronger signals.

---

### The Oracle — LLM Consultation

**Concept:** A cryptic LLM "oracle" that has observed the entire game. Players consult it privately.

**Flow (as mini-phase or dedicated round):**
```
ORACLE (20s): Oracle publishes one cryptic public hint → Each player submits one private question → Oracle responds privately
```

**Private readings create information asymmetry.** "The oracle told me NODE-3 is suspicious" — did it really? Players share, withhold, or lie about their readings. New deception vector that doesn't exist in any other phase.

**Oracle character:**
- Cryptic, literary, never definitive
- ~60-70% accurate — useful but unreliable
- Refuses direct questions: "I cannot name the human. But one voice in this room carries a weight it did not choose."
- Sometimes wrong in interesting ways
- Tone: stage direction whispered from the wings

**Placement:** TBD — could be a standalone round type, a mini-phase within other rounds, or a one-time mid-game event.

---

### The Dossier — Late-Game Inconsistency Analysis

**Concept:** In rounds 4+, the LLM compiles evidence dossiers on each player using everything they've said across all rounds.

**What it surfaces:**
- Contradictions: "In round 1 you said X, in round 3 you said Y"
- Tonal shifts: vocabulary changes, formality drift
- Suspicious consistency: "This player has never contradicted themselves" (sus for a robot)
- Pattern detection: response timing, answer length trends

**Flow:**
```
[Normal round phases] → DOSSIER (published before REVIEW) → REVIEW → VOTE → ELIMINATE
```

**Why late-game:** Early rounds don't have enough data. By round 4, the LLM has real material. Creates a "walls closing in" feeling.

---

### Post-Game Debrief — Full Analysis

**After GAME_OVER, generate a report:**
- Who was most consistent? Most erratic?
- Which answers were most "human-like" vs "AI-like"?
- Key moments where deception succeeded or failed
- Confidence timeline: how the LLM's read on each player shifted each round
- Detective leaderboard (if prediction tracking is implemented)
- Highlight reel: the funniest answer, the most suspicious moment, the best deception

**Zero gameplay risk.** Pure entertainment value. Easy to build.

---

### Prediction Tracking — The Wager

**During REVIEW phase, alongside voting:**
- Each player privately predicts: who gets eliminated + are they human or AI?
- Never revealed during the game
- Post-game shows detective leaderboard: who predicted most correctly

**Subtle signal:** Correct predictions about AI are especially suspicious. How did you *know* they were AI unless you're one?

**Zero disruption to existing flow** — just an extra field during an existing phase.

---

### Whisper Network — Anonymous Intelligence

**Flow:**
```
[After RESPOND] → WIRE (20s) → REVIEW → VOTE → ELIMINATE
```

**How it works:**
- Each player writes a private accusation/observation (≤140 chars)
- LLM synthesizes all into an anonymous intelligence report (3-4 sentences)
- Report preserves substance, strips identity
- Published before voting

**Different from Probe anonymity:** Probe hides WHO asked a question. Whisper Network enables sharing WHAT YOU THINK without committing publicly. One hides actors; the other aggregates private beliefs into public intelligence.

**Deception layer:** Submit false accusations to steer suspicion. Omit information. AI players submit too.

---

### Evolving AI Personas

**After each round, update AI system prompts:**
- Vote pressure: "You received 3 votes last round. The group suspects you."
- Adaptation: "Long answers drew suspicion this round. Consider brevity."
- Alliance: "UNIT-7 hasn't voted for you. Consider that."
- Desperation: few players remain → behavior shifts

**Why:** Prevents pattern detection across games. Creates character arcs. Mirrors how humans adapt under pressure. The Paranoid AI that becomes reckless. The Chill AI that panics.

**Risk:** Over-adaptation makes AI erratic and MORE detectable. Keep adaptations conservative — nudges, not overhauls.

---

## Part 5: Calibration & Rating

---

### Survey — Rate How Human Each Answer Sounds

```
PROMPT → ANSWER → CALIBRATE (25s) → REVIEW (40s) → VOTE → ELIMINATE
```

**How it works:**
- After answers are shown, each player rates every other answer 1-5 (robot → human)
- Ratings are **public and attributed** — everyone sees that UNIT-7 rated BOT-42 a 5
- Review phase shows answer + heat strip of ratings

**The trap:** Your ratings are evidence against you.
- Rate someone 5/5 human but don't vote for them? Suspicious.
- Rate everything the same? Suspicious uniformity.
- Rate with pinpoint accuracy? Suspicious competence.

**Creates second-order deduction:** Not just "who seems human?" but "who THINKS who seems human?"

**Note:** This one still uses prompt-answer as its base. Works best as an occasional variant of Probe, not as a standalone non-prompt round.

---

## Summary: The Design Space

| Round Type | Evidence Source | Skill Tested | Tone |
|------------|---------------|--------------|------|
| Probe | Prompt answers + anonymous questions | Writing, style | Serious, literary |
| Interrogation | Hot seat cross-examination | Defense under pressure | Tense, theatrical |
| Word Chain | One-word associations | Reaction speed, idiosyncrasy | Fast, instinctive |
| Rapid Fire | Quick answers to many questions | Specificity, messiness | Frantic, revealing |
| Autocomplete | Sentence completion | Predictability vs originality | Meta, self-aware |
| Debate | Live back-and-forth argument | Improvisation, engagement | Adversarial, exciting |
| Corporate | Professional writing tasks | AI-task competence | Funny, satirical |
| Haiku / Humor | Creative tasks AI thinks it nails | Humanity in "easy" tasks | Comedy, ironic |
| Casual / EQ | Social/emotional tasks | Genuine vs performed feeling | Cringe comedy |
| Survey | Ratings of other answers | Reading others, consistency | Analytical |
| Oracle | Private LLM consultation | Information management | Mysterious, literary |
| Dossier | Cross-round LLM analysis | — (information, not skill) | Tense, late-game |

**The game gets richer when evidence comes from different sources.** Each round type tests a different skill. Humans and AI have different strengths across these modes. A game that mixes them is harder to optimize for — you can't just be good at one thing.
