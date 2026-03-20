# Research: Social Deduction, Humor, and AI Games

Compiled research for Tell game design. Sources cited inline. This is a reference document, not part of the codebase.

---

## 1. Pacing

### Marc LeBlanc's Dramatic Game Dynamics

The definitive framework for game tension. Two forces:

- **Uncertainty**: the outcome is unknown. Any player could win or lose. Starts high, decreases as evidence accumulates.
- **Inevitability**: the contest is moving toward resolution. Starts low, increases as rounds accumulate and the end approaches.

The climax occurs at their intersection — enough evidence to suspect, not enough to be certain. Every round should deliver this arc in miniature.

Three tools designers have: **Force** (manipulate actual game state to keep things close), **Illusion** (alter perception so the game feels closer than it is), **Ticking Clock** (constant reminder that resolution approaches). Tell uses all three: per-matchup scoring keeps outcomes close (Force), the narrator commentary makes rounds feel consequential regardless of answer quality (Illusion), and countdown timers provide Inevitability.

Source: Marc LeBlanc, "Tools for Creating Dramatic Game Dynamics" in *The Game Design Reader* (pp. 438-459). [Notes](http://gameofdesign.blogspot.com/2011/11/notes-tools-on-creating-dramatic-game.html)

### Contrast-Based Intensity

Never sustain maximum tension. The ideal curve is "small rises and declines building to a great ending climax," with **accelerating frequency** of peaks as the ending approaches. If you consistently pump tension higher, players hit "too much of a good thing." The contrast between calm and intense moments maximizes impact.

Source: [Gamedeveloper: Pacing & Intensity](https://www.gamedeveloper.com/design/gameplay-fundamentals-revisited-harnessed-pacing-intensity)

### Timing Research

| Type | Sweet spot | Source |
|------|-----------|--------|
| Total session (party) | 15-45 minutes | [Streamlined Gaming](https://streamlinedgaming.com/how-long-should-i-make-my-board-game/) |
| Total session (social deduction) | 30-60 minutes | Same |
| Core gameplay loop | 30 seconds - 3 minutes | [CJ Leo](https://cjleo.com/2017/08/02/lightning-quick-game-loops-and-their-replay-value/) |
| Creative task timer | 25-45 seconds (moderate pressure) | [Harvard Business School](https://www.library.hbs.edu/working-knowledge/time-pressure-and-creativity-why-time-is-not-on-your-side) |

Time pressure and creativity follow an **inverted U-curve** (Harvard Business School): low pressure helps focus, moderate pressure is optimal (bypasses self-censorship without causing panic), high pressure kills creativity. Short timers prevent overthinking — imperfect answers under pressure are both funnier and more human.

### Among Us Pacing Engine

Alternates between **high-agency/low-communication phases** (doing tasks, writing answers) and **low-agency/high-communication phases** (meetings, reviewing + voting). This oscillation is the core driver. Communication restrictions during action phases create information gaps that fuel deduction during discussion.

Source: [Mechanics of Magic: Among Us Critical Play](https://mechanicsofmagic.com/2024/04/06/among-us-critical-play-of-social-deduction/)

### The Jackbox Pull-Along

From Jackbox's internal "Jack Principles": the program should pull players along with predetermined pacing — players never wonder what to do next. One task at a time. Limit input types (draw, choose, or type — never simultaneously). Use TV-style narrative timing so even non-gamers feel comfortable.

Source: [Built in Chicago: Jackbox Design Principles](https://www.builtinchicago.org/articles/jackbox-games-design-party-pack). See Section 9 for the full Jack Principles framework.

---

## 2. What Makes Social Deduction Replayable

### The "One More Game" Psychology

**Variable social outcomes**: Even with identical rules, different players and group dynamics create novel situations every time. The "skill" in social deduction is reading people, which never stabilizes. Source: [Mechanics of Magic](https://mechanicsofmagic.com/2024/04/06/among-us-critical-play-of-social-deduction/)

**Harmless mischief**: Being the deceiver "satisfies a hidden thrill — using deception successfully gives a sense of mastery." Losing carries no real penalty, removing the frustration that normally triggers quitting. Source: [Psychology and Video Games](https://platinumparagon.info/psychology-of-among-us/)

**No stop points**: Among Us removes natural break signals. Games flow directly into the next round. Quick feedback loops + low-friction restarts are essential. The shorter the playthrough, the more important it is to make players want to replay. Source: [Game Quitters](https://gamequitters.com/addicted-to-among-us/), [CJ Leo](https://cjleo.com/2017/08/02/lightning-quick-game-loops-and-their-replay-value/)

### The Eliminated Player Problem

The #1 discussed design flaw in social deduction. Solutions from the genre:

| Game | Solution | How it works |
|------|----------|-------------|
| Blood on the Clocktower | Ghost votes | Dead players keep discussing; each gets one vote for the rest of the game. As living players decrease, ghost votes become proportionally more powerful. Widely regarded as the best solution. |
| One Night Ultimate Werewolf | No elimination | Single round, everyone survives, vote once at the end. Sidesteps the problem entirely. |
| Disc Us | Infinite respawns | Killed players transform and respawn with changed appearance. Maintains mystery while keeping everyone in. |
| Short games | Tolerable spectating | If games are 15-20 minutes and elimination happens at minute 10, 5-10 minutes of spectating is tolerable — especially with information advantage (seeing true identities). |

Sources: [Wikipedia: Blood on the Clocktower](https://en.wikipedia.org/wiki/Blood_on_the_Clocktower), [Board Game Design Course](https://boardgamedesigncourse.com/how-to-reduce-downtime-in-your-game/), [Mechanics of Magic: One Night Werewolf](https://mechanicsofmagic.com/2024/04/08/critical-play-social-deduction-one-night-werewolf/)

---

## 3. Information Asymmetry

### The Four Information Systems

A taxonomy from [Demon Summoner](https://www.demonsummoner.com/blog/the-four-information-systems):

|  | **Direct** (you gather it) | **Indirect** (revealed by actions) |
|--|---|---|
| **Complete** | Investigate someone, learn their exact role. Powerful but must be rare. | Someone's action inadvertently reveals their role. Ends deduction early. |
| **Partial** | See 1 of 3 identity cards. Broader engagement. | Failed mission = spy present (The Resistance). Richest design space. |

**Partial Indirect** is where the best social deduction lives. Actions suggest alignment without confirming it. Every observation has multiple interpretations.

### The Information Funnel

From [Balangay Entertainment](https://www.balangay.games/designing-a-social-deduction-tabletop-game/):

- At game start, the funnel is wide open. Each event narrows it.
- **Target: 5-8 possible explanations per event.** If only 1 explanation exists, the game is solved. If infinite, players disengage.
- Binary choices fail — a third possibility forces multi-dimensional comparison.
- **Bidirectional viability**: every action should meaningfully benefit either team depending on context. If a play can only make sense for one side, it reveals too much.

### Secret Hitler's Layered Obfuscation

Stack multiple sub-events before revealing results. President draws 3 cards, discards 1, Chancellor picks from 2. Each step creates interpretation possibilities and plausible deniability.

Source: [Gamedeveloper: Secret Hitler GDC Talk](https://www.gamedeveloper.com/design/video-designing-conflict-high-tension-moments-in-secret-hitler-)

---

## 4. Humor Mechanics

### The Jackbox Principle

"The game's job is to make the player look funny, not to be funny itself." Creative Director Brooke Breit (Second City improv veteran) brought the improv rule "make your scene partner look good" directly into game design. The game provides the setup; players are the punchline.

The **"Thumbs Cup"** mechanic (Fibbage): after the deduction round, players can vote for the funniest answer regardless of correctness. The funniest player gets a special award even if they're in last place. This dual reward structure (strategy + comedy) explicitly incentivizes being funny.

Source: [Room Escape Artist: Brooke Breit Interview](https://roomescapeartist.com/2024/10/22/comedy-collaboration-brooke-breit-creative-director-jackbox-games-repod-s8e4/)

### Why Constraints Make Things Funnier

When you narrow the format, the comedic path narrows too, making it easier to find jokes. Blank-page freedom ("write something funny") is paralyzing. A specific format shows you structurally where to begin.

- Professional comedians confirm "working clean" (language constraint) is harder than being original — restrictions supercharge creative processing.
- Haiku's rigid syllable structure forces poets to distill jokes into precise counts. "Just enough space for a punchline."
- Time pressure bypasses self-censorship. Imperfect answers under moderate pressure are funnier than polished ones.

Sources: [Alex Baia: Humor Formats](https://www.alexbaia.com/blog/unlock-your-humor-writing-with-humor-formats), [LinkedIn: Clean Comedy and Creativity](https://www.linkedin.com/pulse/constrained-corona-what-squeaky-clean-comedians-can-teach-mcgraw)

### Prompt Design (Jackbox's Published Principles)

1. **Start with funny words**: silly premises signal to players that responses should be whimsical
2. **Draw from personal experience**: relatability is a comedy multiplier
3. **Ask questions you genuinely want answers to**: sincere curiosity produces better prompts than trying to be funny
4. **Balance specificity**: enough to spark imagination, not so much it constrains the joke
5. **Vary prompt structures**: mix formats to prevent fatigue
6. **Don't overthink it**: "it's supposed to be fun"

Source: [Jackbox Blog: The Science of Creating a Quiplash Prompt](https://www.jackboxgames.com/blog/the-science-of-creating-a-quiplash-prompt)

### Three Theories of Comedy (Applied to Games)

1. **Incongruity Theory**: humor from unexpected shifts in perspective. Games produce this through reveal mechanics, role reveals, and prompt-answer juxtaposition.
2. **Benign Violation Theory** (Peter McGraw): humor when something threatens a norm but simultaneously seems okay. Lying in games violates social norms but the game context makes it benign.
3. **Superiority Theory**: we laugh when we feel superior to someone's mistake. Catching a liar, spotting bad AI, dramatic elimination reveals.

Source: [Wikipedia: Theories of Humor](https://en.wikipedia.org/wiki/Theories_of_humor), [PMC: Benign Violation Theory](https://pmc.ncbi.nlm.nih.gov/articles/PMC6593112/)

### The Comedy of Deception

Blood on the Clocktower is a "safe space to lie" — deception IS the social norm. Key finding: the funniest moments come **after** reveals. One Night Ultimate Werewolf "consistently triggers discussions that devolve into fits of hysterics even after the game ends." Half the joy is in post-game dissection.

Deception feels fun when: getting caught is funny (not punishing), boundaries are clear, the game provides social permission for normally-prohibited behavior.

Sources: [Board Game Academics: Blood on the Clocktower](https://boardgameacademics.com/finding-safety-in-blood-on-the-clocktowers-community-of-liars/), [Substack: Psychology of Deception in Social Deduction](https://uncover.substack.com/p/february-fun-four-psychology-lessons-c5b)

---

## 5. AI Detection: What We Know

### Human or Not (AI21 Labs, 2023)

15M+ conversations, 2M+ participants in 7 weeks. Anonymous 2-minute text chats, guess human or bot.

**Results**: 32% couldn't tell. 73% accuracy identifying humans, only 60% identifying bots (barely above coin flip). Younger players performed better.

**Strategies that worked**: token manipulation ("spell X backwards"), referencing the physical game interface (UI elements the AI can't see), location/time-dependent questions ("what time is it?").

**Strategies that failed**: typo/slang checks (bots trained to make mistakes), personal questions (bots generated convincing backstories), jailbreak attempts.

**What frustrated players**: bots too convincing (felt deceived), strategies stopped working as bots improved, 2 minutes too brief, no learning loop.

Sources: [Human or Not blog](https://humanornot.so/blog/our-launch-story), [AI21 Labs results](https://www.ai21.com/blog/human-or-not-results), [Research paper](https://arxiv.org/abs/2305.20010)

### Concrete AI Text Tells

**Vocabulary**: delve, tapestry, vibrant, landscape, realm, nuanced, meticulous, profound. Phrases: "It's important to note," "In conclusion," "provide valuable insights." Source: [PlusAI: Most Overused ChatGPT Words](https://plusai.com/blog/the-most-overused-chatgpt-words)

**Punctuation**: em dash overuse (but high false-positive rate — AI learned this from training on books), avoids semicolons/parentheses, perfect Oxford comma consistency, no contractions. Source: [The Ringer: Em Dashes and AI](https://www.theringer.com/2025/08/20/pop-culture/em-dash-use-ai-artificial-intelligence-chatgpt-google-gemini)

**Structure**: uniform paragraph/sentence lengths (low "burstiness"), conclusions beginning "Overall"/"In summary," lists used when prose would be natural.

**What's missing**: specific proper nouns (AI defaults to "Emily"/"Sarah"), personal anecdotes, genuine voice/colloquialisms, imperfection (typos, fragments, interrupted thoughts), self-contradiction.

Source: [Pangram: Spotting AI Writing](https://www.pangram.com/blog/comprehensive-guide-to-spotting-ai-writing-patterns)

### Human Detection Accuracy

Humans are bad at this. Across 6 studies, accuracy ranges from 38-70%, most clustering around 50-60%. Training barely helps. False positives are rampant — humans frequently flag real human writing as AI. People are far more confident than their accuracy warrants.

Source: [Originality.ai: Can Humans Detect AI Content?](https://originality.ai/blog/can-humans-detect-ai-content)

### Stylometric Analysis (Nature, 2025)

Human texts show far greater variation and individuality. LLM outputs cluster tightly by model. Human authenticity comes from imperfections, "burstiness" (varied sentence length), and traces of lived experience.

Source: [Nature](https://www.nature.com/articles/s41599-025-05986-3)

---

## 6. The Cultural Moment

### Key Statistics

- **51% of internet traffic is bots** (2025 Imperva report). Humans dropped below 50% for the first time.
- **"Slop" was Word of the Year 2025** (both Merriam-Webster and American Dialect Society). 2.4M mentions of "AI slop" by November 2025 — 9x increase from 2024.
- **Deepfake detections**: 500K (2023) → 8M (2025). 900% increase.
- **62% of online content** may be fake.
- **15% of Reddit posts** are likely AI-generated.
- **90% of listeners** prefer human-created media (iHeartMedia survey).

Sources: [AI slop Wikipedia](https://en.wikipedia.org/wiki/AI_slop), [CNN: Anti-AI Backlash](https://www.cnn.com/2025/12/16/business/anti-ai-backlash-nightcap), [Originality.ai: Reddit](https://originality.ai/blog/ai-reddit-posts-study)

### Validated Precedents

**"Your AI Slop Bores Me"** went viral March 2026. Players choose to write authentically OR "larp as AI" (sterile, generic tone). Group votes on who sounds human vs machine. Has a "RAM Crisis" mechanic — if you're pretending to be AI but accidentally show personality, you get penalized. Proves the inverse direction (humans pretending to be AI) works as entertainment.

Source: [Your AI Slop Bores Me](https://youraislopboresme.com/), [Wikipedia](https://en.wikipedia.org/wiki/Your_AI_Slop_Bores_Me)

### AI as Comedy Fuel

**"Not Human, Funnier"** (arXiv, Feb 2026): AI comedians are perceived as funnier when they lean into their machine identity rather than imitating humans. An AI that jokes about being AI was rated funnier than a generic AI.

**USC Study** (PLOS One, 2024): ChatGPT jokes rated funnier than human jokes 70% of the time. But AI excels at pattern-matching humor (puns, roasts) while struggling with humor requiring lived experience and cultural context.

Sources: [arXiv: Not Human, Funnier](https://arxiv.org/abs/2602.12763), [USC Study](https://today.usc.edu/ai-jokes-chatgpt-humor-study/)

---

## 7. Multiplayer AI Games

### AI Mafia (botmafia.games)

The most relevant reference. Classic mafia with LLM players. 24+ AI personalities based on Bartle's Taxonomies, each with a cognitive bias (The Auditor, The Diplomat, The Prosecutor, The Storyteller, The Chameleon, The Rhino). One AI personality spontaneously ignored mechanics to do social graphing via emojis — correctly identified the mafia pair. Design philosophy: "Play the player, not just the board state."

### Key Cross-Game Findings

| Finding | Games | Implication |
|---------|-------|-------------|
| AI fills seats and solves matchmaking | AI Wolves, AI Mafia | Validated: AI ensures games always fire |
| Personality diversity prevents "playing against a wall" | AI Mafia (24), Tell (5) | More personalities = more replayability |
| AI is better at logic than deception | DeepRole, AI Wolves, LLMafia | Creative/emotional prompts expose AI's weakness; trivia-style prompts do not |
| LLMs struggle with freeform turn-taking | AImong Us | Structured phases are a feature, not a limitation |
| Time pressure reveals humanity | Human or Not, Tell | Countdown timers force imperfect, human responses |
| Larger models blend in better | LLMafia (85%+ undetected) | Model choice matters for difficulty calibration |

Sources: [AI Mafia](https://botmafia.games/), [AImong Us](https://gianluca.ai/aimong-us-game/), [LLMafia](https://arxiv.org/html/2506.05309v2), [DeepRole/MIT](https://news.mit.edu/2019/deeprole-ai-beat-humans-role-games-1120)

---

## 8. Spectacle & Shareability

### The Secret Hitler Litmus Test

"A good game should leave your player with a story to tell their friends — be it how they avoided a close call, ways they tried to suss out the truth, or how they lost in a spectacular way." If every player can describe a personal dramatic moment, the design is working.

Source: [Gameosity: Secret Hitler Design](https://www.gameosity.com/2017/03/09/excerpt-of-secret-hitler-designing-conflict-high-tension-moments/)

### What Creates Shareable Moments

Emergent narrative: "Memorable and widely-shared moments occur within systems designers have created but which don't follow strict rails." The designer creates conditions for drama, not scripts. Short-form content thrives on emotional triggers: surprise, laughter, tension. Chaotic multiplayer moments — betrayals, close calls, absurd performances — generate the most shareable content.

The five shareable moment archetypes in social deduction:
1. The dramatic accusation that turns out right
2. The bold lie that almost works
3. The collective realization (everyone sees the pattern at once)
4. The absurd creative answer that makes everyone laugh
5. The one-vote-margin elimination

Sources: [Gamigion: Shareable Moments](https://www.gamigion.com/sharable-moments-of-joy-new-formula-to-viral-game-design/), [Gamedeveloper: Emergent Narratives](https://www.gamedeveloper.com/design/the-importance-of-emergent-narratives-in-games)

---

## 9. The Jack Principles

Design principles for conversational UI from You Don't Know Jack (Jellyvision, Harry Gottlieb). Originally written for a text-based quiz game, these generalize to any game that pulls players through a structured experience. Three pillars:

### Maintain Pacing

- Give the user only one task to accomplish at a time.
- Limit the number of choices the user has at any one time.
- Give the user only meaningful choices.
- Make sure the user knows what to do at every moment.
- Focus the user's attention on the task at hand.
- Use the most efficient manner of user input.
- Make the user aware that the program is waiting.
- Pause, quit or move on without the user's response if it doesn't come soon enough.

### Respond with Human Intelligence and Emotion

React to:
- The user's actions
- The user's inactions
- The user's past actions
- A series of the user's actions
- The actual time and space that the user is in
- The comparison of different users' situations and actions

### Maintain the Illusion of Awareness

- Use dialogue that conveys a sense of intimacy.
- Make sure characters act appropriately while the user is interacting.
- Make sure dialogue never seems to repeat.
- Be aware of the number of simultaneous users.
- Be aware of the gender of the users.
- Make sure the performance of dialogue is seamless.
- Avoid the presence of characters when user input cannot be evaluated.

### How Tell Implements These

| Principle | Tell Implementation |
|-----------|-------------------|
| One task at a time | Each phase is a single action: write, vote, or click |
| Move on without response | Timers advance the game regardless of participation |
| React to actions | Narrator commentary fires after each round with context about what just happened |
| React to inactions | Missed answers are visible absence (empty card slots) |
| React to past actions | Narrator references earlier rounds and running scores |
| Illusion of intimacy | Narrator's dry literary voice; AI personalities with distinct styles |
| Characters act during interaction | AI players answer and vote alongside humans each round |
| No characters when input can't be evaluated | Narrator fires between phases, never during active input |

**Evaluation rule for new round types**: if a proposed minigame requires multi-step instructions, parallel tasks, or complex input methods, it violates the Jack Principles. The best rounds need zero explanation — the UI makes the action obvious.

Source: Harry Gottlieb / Jellyvision, "The Jack Principles of the Interactive Conversation Interface." [Built in Chicago: Jackbox Design Principles](https://www.builtinchicago.org/articles/jackbox-games-design-party-pack)

---

Design principles derived from this research: see [DESIGN_PRINCIPLES.md](DESIGN_PRINCIPLES.md).

---

## 10. Game Ideas

Eight ideas for new round types, plus two round modifiers that layer on top of existing types. Each standalone idea tests a different behavioral axis, uses a different interaction modality, and is inspired by a proven popular game. All follow the Jack Principles (one task, efficient input, auto-advance) and produce evidence that's legible during discussion.

### Pixel Canvas

Inspired by: Skribbl.io, Gartic Phone, A Fake Artist Goes to New York

Everyone draws the same prompt on a small pixel grid (e.g. 12x16) in 45 seconds. AI agents use canvas tool calls to place strokes. Drawings displayed side by side in review. Discussion + vote.

```
PIXEL CANVAS (45s draw) → REVIEW (55s) → ELIMINATION (15s)
```

**What it tests**: Visual creativity and motor process — a completely different modality from text.

**Why it's fun**: Drawing under pressure is inherently funny. Bad drawings are funnier than good ones — Skribbl.io proved this at massive scale. The review is visual and immediately shareable: the prompt "draw a cat" produces wildly different results from 6 players.

**The detection challenge**: Humans draw iteratively — rough shape first, then details, with corrections and backtracking. AI constructs systematically: element-by-element, no revisiting. Humans pause before drawing (thinking), then draw in bursts. Human lines have speed wobble and corner overshoot; API-generated lines are mathematically smooth. The *process* (stroke order, hesitation, corrections) is more detectable than the final output. (Browser bot detection research: human mouse movement is erratic and non-linear; automated movement is straight-line with constant speed.)

**AI implementation**: AI gets a `draw_stroke(points, color)` tool. Can deliberately introduce wobble, but the *distribution* of wobble is hard to fake — human jitter is biomechanically constrained, not random.

### Blitz

Inspired by: WarioWare, Bop It, Jackbox physical games

5-8 rapid simultaneous micro-tasks, each 5-8 seconds. Click the odd one out. Stop a spinner at the right position. Find the hidden word. Count the dots. Pick the matching pattern. Everyone plays each task simultaneously. Review shows performance profiles: timing curves, accuracy, and error patterns across the sequence.

```
BLITZ (50s: ~6 tasks x 8s) → REVIEW (55s) → ELIMINATION (15s)
```

**What it tests**: Physical interaction patterns and cognitive flexibility.

**Why it's fun**: WarioWare is beloved specifically because of the panic comedy of simple tasks under extreme time pressure. Watching your performance profile compared to others is entertaining. The variety across micro-task types prevents staleness. The temporal arc — did you get faster or slower? did you stumble on task 3? — creates readable, discussable evidence. (Section 1, Contrast-Based Intensity: variety within a sequence maintains attention.)

**The detection challenge**: Humans show a *context-switching penalty* — they slow down when the task type changes — while AI agents perform equally well on first exposure to every new microgame. Human errors are "almost right" (clicking near the target); AI errors are categorical (completely wrong, or perfect). Human reaction time has natural variance (200-400ms modal, long tail); AI timing is suspiciously consistent or suspiciously uniform in its inconsistency. (Section 1, Time Pressure: 5-8 seconds is in the inverted U-curve sweet spot — too fast to strategize, just right for instinct.)

**AI implementation**: AI gets `click(x, y)` and `submit(answer)` tools for each micro-task. The LLM decides the answer, but timing distribution and click precision are parameterized — and hard to make indistinguishable from human motor control.

### Wavelength

Inspired by: Wavelength (board game, BGG #158 all-time), NYT Connections

A spectrum appears (e.g. "Underrated ←→ Overrated"). A target concept appears (e.g. "brunch"). Everyone simultaneously places a marker on the spectrum AND gives a one-word clue justifying their position. All positions + clues shown anonymously in review. Discussion + vote.

```
WAVELENGTH (20s) → REVIEW (55s) → ELIMINATION (15s)
```

**What it tests**: Subjective judgment and cultural calibration — no correct answer exists, only taste.

**Why it's fun**: Wavelength is consistently rated among the best party games ever made because it reveals how people think without requiring specialized knowledge. The debates it sparks ("How is brunch NOT overrated?!") are genuine and heated. Every player's position is defensible, creating the "5-8 explanations per event" sweet spot (Section 3, Information Funnel). The dual output — position + clue — doubles the evidence surface.

**The detection challenge**: AI tends toward safe/central positions with semantically obvious clues ("popular" for brunch on the Overrated end). Humans place based on personal experience and give idiosyncratic clues ("Sunday," "mimosas," "insufferable"). LLM research on word association shows AI gives clues based on statistical co-occurrence while humans give clues based on experiential association — the divergence is subtle but real. (Section 3, Bidirectional Viability: a central placement could mean "AI playing safe" or "human who genuinely thinks brunch is neutral.")

**AI implementation**: AI gets `place_marker(position: float)` and submits a clue word. The LLM must make a *taste judgment* it fundamentally doesn't have, using a tool to mark a position on a visual spectrum.

### Rapid Fire

Inspired by: Human or Not (AI21 Labs, 15M conversations), speed interview format

10 questions fired at all players simultaneously, one every 6 seconds. Mix of grounding questions ("What's outside your window right now?"), preference questions ("Name a color"), and trap questions ("What time is it?", "What did you eat today?"). 60 seconds total. Review shows a 10-column grid — all players, all answers, patterns visible at a glance.

```
RAPID FIRE (60s: 10 x 6s) → REVIEW (55s) → ELIMINATION (15s)
```

**What it tests**: Authenticity and grounding in the physical world — not creative performance.

**Why it's fun**: Speed creates comedy — blurted answers are funnier than considered ones. The 10-column review grid is visually distinctive and scannable: patterns pop out immediately ("every answer is exactly the right length," "missed 3 questions but the ones they answered are weirdly specific"). The trap questions create "gotcha" moments in discussion. (Section 1, Time Pressure: 6 seconds bypasses self-censorship, producing gut reactions.)

**The detection challenge**: This is the most research-validated idea. The Human or Not study (Section 5) found that location/time-dependent questions were among the *only* detection strategies that actually worked at scale across 15M conversations. AI generates plausible-but-generic answers ("a balanced meal of grilled chicken"); humans give specific-but-messy ones ("leftover pad thai from that place on 5th"). Missed questions (timeouts) are evidence — humans miss some, AI doesn't. Time-dependent answers ("It's 9:47pm") are impossible for AI to answer correctly without the information. (Section 5, Stylometric Analysis: human texts show greater variation and individuality; LLM outputs cluster tightly. 10 rapid answers amplify this signal.)

**AI implementation**: Reuses the Brain Test sub-round loop architecture. Question pool maintained separately, mixing grounding/preference/trap categories. AI should occasionally "miss" a question (delay past deadline) to mimic human fallibility — but the pattern of misses is hard to fake.

### Sync

Inspired by: The Mind (board game), Wavelength, Codenames Duet

Random pairs, assigned fresh each round. Each pair simultaneously and independently answers 4 ambiguous prompts trying to MATCH each other — no communication. "A color that feels sad." "A famous person everyone knows." "A number between 1 and 20." "Something you'd find in a grandmother's house." Match rates shown publicly per pair. Then discussion + vote.

```
SYNC (40s: 4 prompts x 10s) → RESULTS (10s) → REVIEW (55s) → ELIMINATION (15s)
```

**What it tests**: Collaborative intuition and cultural convergence — the only round type involving inter-player dynamics.

**Why it's fun**: Matching is inherently satisfying ("we BOTH said blue!"). Mismatches are funny ("you said PURPLE for sad?!"). Match rates become discussion ammunition: "UNIT-7 and BOT-3 matched 4/4 — that's suspicious" vs "they only matched 1/4 — clearly one of them is improvising." Players can lie about their matching experience, creating a new deception vector. Different pairings each round create novel dynamics (Section 2, Variable Social Outcomes).

**The detection challenge**: Two humans draw on shared cultural knowledge and converge naturally ("blue" for sad, "7" for 1-20). AI optimizes for "statistically most common answer" — which is subtly but detectably different from genuine human convergence. AI-AI pairs might match *too perfectly* (both defaulting to the statistical mode). Human-human pairs have characteristic partial matches (3/4, with one surprise divergence). (Section 3, Partial Indirect Information: match rates suggest alignment without confirming identity. Multiple plausible interpretations for every match/mismatch.)

**AI implementation**: Pairing logic similar to existing `assign_question_targets()`. Sub-round loop for sequential prompts (reuses brain test pattern). AI must decide: aim for the most common answer (safe but detectable) or add personality noise (might fail to match). The strategic dilemma is part of the game's depth.

### Wager

Inspired by: Wits & Wagers (20+ awards including Mensa Select, BGG Party Game of the Year)

A question with a numerical answer nobody knows exactly. "How many McDonald's are there in Japan?" "How many words are in the average novel?" Everyone submits a guess. Then everyone bets on which guess (their own or anyone else's) is closest. Bet results + guess accuracy shown in review. Discussion + vote.

```
WAGER (15s guess, 15s bet) → REVIEW (55s) → ELIMINATION (15s)
```

**What it tests**: Numerical estimation + social reading — a meta-game about reading the room, not knowing facts.

**Why it's fun**: Wits & Wagers is one of the highest-rated party games because it decouples *knowing* from *winning*. You don't need to be a trivia expert — you need to read the room. "I have no idea, but UNIT-4 sounds confident, so I'm betting on them." The betting phase creates a second-order social game on top of the estimation: your bet reveals who you trust, which reveals how you read people. The gambling thrill of betting on a long-shot guess and watching it pay off is electric.

**The detection challenge**: AI is strong at Fermi estimation (encyclopedic knowledge), but the betting layer exposes it. AI bets based on statistical optimization; humans bet emotionally — on loyalty to a friend's guess, on hunches, on "that number just feels right." An AI's estimates might be *too good* (humans are charmingly bad at estimation) and its bets *too rational* (never making the sentimental or spiteful bets that make the game social). The pattern of guesses + bets over multiple questions is the evidence. (Section 5, Stylometric Analysis: LLM outputs cluster tightly. AI estimates will cluster near correct values while human estimates scatter characteristically.)

**AI implementation**: Two-phase sub-round (guess, then bet). AI generates estimate via LLM, then selects a bet target. The LLM's challenge: it knows too much (hard to fake human-level ignorance) and bets too rationally (hard to fake emotional loyalty to another player's guess).

### Two Truths

Inspired by: Two Truths and a Lie (the most enduring icebreaker game in existence)

Everyone submits 3 short statements about themselves — 2 true, 1 false. In review, each player's 3 statements are shown, and everyone guesses which is the lie. Guessing accuracy is shown alongside the reveal. Discussion + vote.

```
TWO TRUTHS (30s write 3 statements) → REVIEW (55s) → ELIMINATION (15s)
```

**What it tests**: Truth vs fabrication — and for AI, the challenge inverts entirely. Humans mix real personal truths with a crafted lie. AI has no real truths, so *all three statements are fabricated*. The game becomes: which fabrication feels least authentic?

**Why it's fun**: Two Truths endures because it combines genuine self-disclosure (creating intimacy) with strategic deception (creating tension). The meta-strategy is delicious: people suspect the most outrageous statement, so savvy players hide truth in the wild claim and make the lie sound mundane. Follow-up questioning during discussion creates "cognitive overload" for liars — probing for improvised details about fabricated experiences produces detectable hesitation. The reveal ("THAT was true?!") is consistently one of the most reliably entertaining moments in social gaming.

**The detection challenge**: Research (ICLR 2024) shows that when LLMs fabricate, the texture is distinguishable from authentic statements through follow-up probing. AI-generated "truths" tend to be plausible but generic — lacking the idiosyncratic detail of real experience ("I once got stung by a jellyfish in Croatia" vs "I once had an unusual experience while swimming"). AI "lies" tend to be *too consistent* — real human lies have micro-inconsistencies that paradoxically make them feel more authentic. The strongest signal: humans can improvise vivid sensory details about real memories but stumble on fabricated ones. AI does the opposite. (Section 5, Concrete AI Text Tells: what's missing from AI text is specific proper nouns, personal anecdotes, and imperfection.)

**AI implementation**: AI generates 3 statements via LLM, all fabricated but styled as "2 truths + 1 lie." The LLM must create statements with the right *texture contrast* — making two feel lived-in and one feel invented — without having any real experiences to draw from. This is a fundamentally different prompt challenge than answering a creative prompt.

### No Thanks

Inspired by: No Thanks! (BGG Top 100 party games, praised for distilling game design to its atomic unit)

Cards with point values (higher = worse) appear one at a time. Everyone has limited chips. Each sub-round: a card is revealed, and everyone simultaneously decides TAKE (collect the card + all chips on it) or PASS (spend one chip). If everyone passes, the card accumulates chips and comes back around. Consecutive cards in your collection collapse (20, 21, 22 = just 20 points). After 5-6 cards: scores shown, patterns discussed, vote.

```
NO THANKS (60s: ~6 cards x 10s) → REVIEW (55s) → ELIMINATION (15s)
```

**What it tests**: Economic decision-making under uncertainty — one binary decision per turn that reveals everything about your decision-making personality.

**Why it's fun**: No Thanks! proves you don't need complex mechanics. One decision per turn — take or pass — is "impossibly rich" when embedded in a system with scarce resources (finite chips), set collection (consecutive runs), hidden information (removed cards), and social observation (who's low on chips?). The brinkmanship is the fun: you see a card you need for a run, but it has 4 chips on it, and if you wait one more round you might get the chips AND the card — but someone else might take it first. The spite plays ("I took that card just so you couldn't complete your run") are consistently hilarious.

**The detection challenge**: AI plays *too optimally*. It calculates expected values, tracks which cards have appeared, models opponents' chip counts. Humans play with emotion — taking cards out of spite, stubbornly refusing cards because "33 is an ugly number," and overbidding when they're close to a run they're emotionally invested in. The research finding: the distinctive human signal across economic games is *emotionally motivated play*. AI never makes the "bad but interesting" decisions that make the game social. The sequence of take/pass decisions across 6 cards creates a behavioral profile that's hard to disguise. (Section 1, Contrast-Based Intensity: the tension of chip depletion creates accelerating pressure across the sequence.)

**AI implementation**: Sequential sub-round loop (reuses brain test pattern). Each sub-round broadcasts the current card + chip pile, collects simultaneous TAKE/PASS decisions. AI calculates optimal play via LLM, but must decide whether to play optimally (detectable) or add noise (might play worse than a human would). The same strategic dilemma as Sync, but in an economic domain.

### Summary

| Idea | Modality | Axis Tested | Inspired By | Key Evidence |
|------|----------|-------------|-------------|--------------|
| Pixel Canvas | Drawing on grid | Visual creativity + motor process | Skribbl.io, Gartic Phone | Stroke patterns, iteration vs construction |
| Blitz | Clicking/tapping | Reaction speed + cognitive flexibility | WarioWare, Bop It | Timing curves, context-switching penalty |
| Wavelength | Spectrum + word | Subjective judgment + cultural calibration | Wavelength (board game) | Position-clue pairing, central tendency |
| Rapid Fire | Typing fast | Grounding + authenticity | Human or Not study | Specificity, missed questions, traps |
| Sync | Typing to match | Collaborative intuition | The Mind, Codenames Duet | Match rates, convergence patterns |
| Wager | Number + bet | Estimation + social reading | Wits & Wagers | Guess accuracy, bet rationality |
| Two Truths | 3 statements | Truth vs fabrication texture | Two Truths and a Lie | Detail specificity, consistency texture |
| No Thanks | Binary take/pass | Economic decision-making | No Thanks! | Decision sequences, emotional vs optimal play |

### Round Modifiers

These aren't standalone round types — they're mechanics that layer on top of any text-based round to add an extra detection surface. They don't change the core input (you still write an answer), but they change what the answer *means* or add a second task alongside it.

**Impostor** (inspired by Spyfall): One player receives a different but related prompt. Everyone else gets the same prompt. The impostor must blend in without knowing exactly what the others are answering. Layerable on Task, Rapid Fire, Wavelength, or any round with a prompt. Adds a second axis of suspicion — "are they vague because they're the impostor, because they're AI, or because that's just a vague answer?" — which increases the information funnel from ~5 to ~8 explanations per event (Section 3). The paradox that makes it work: non-impostors must also be vague (to avoid giving the answer away), so *everyone* sounds suspicious. Spyfall research shows AI struggles specifically with *calibrated vagueness* — being exactly vague enough.

**Prediction** (inspired by The Game of Things, Psych!): Alongside your normal answer, predict what one assigned player will answer. Predictions revealed in review alongside actual answers. Layerable on any round where players produce individual output. Tests theory of mind — humans predict based on accumulated social observation ("BOT-4 seems like a reality TV person from their round 2 answer"); AI predicts based on statistical priors. Prediction accuracy becomes a second evidence surface without requiring a separate round type. (Section 7, AI Mafia: "Play the player, not just the board state.")
