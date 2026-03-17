# Research: Social Deduction, Humor, and AI Games

Compiled research for Tell game design. Sources cited inline. This is a reference document, not part of the codebase.

---

## 1. Pacing

### Marc LeBlanc's Dramatic Game Dynamics

The definitive framework for game tension. Two forces:

- **Uncertainty**: the outcome is unknown. Any player could win or lose. Starts high, decreases as evidence accumulates.
- **Inevitability**: the contest is moving toward resolution. Starts low, increases as players are eliminated.

The climax occurs at their intersection — enough evidence to suspect, not enough to be certain. Every round should deliver this arc in miniature.

Three tools designers have: **Force** (manipulate actual game state to keep things close), **Illusion** (alter perception so the game feels closer than it is), **Ticking Clock** (constant reminder that resolution approaches). Tell uses all three: multi-vote keeps outcomes close (Force), the synthesis paragraph makes interrogation feel intense regardless of question quality (Illusion), and countdown timers provide Inevitability.

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

Source: [Built in Chicago: Jackbox Design Principles](https://www.builtinchicago.org/articles/jackbox-games-design-party-pack)

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
| AI is better at logic than deception | DeepRole, AI Wolves, LLMafia | Interrogation rounds exploit AI's weakness |
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
