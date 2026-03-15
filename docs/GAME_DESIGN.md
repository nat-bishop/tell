# Game Design

## Concept

Reverse Turing test as social deduction. Everyone claims to be a robot. Some are human. The AI players are genuinely AI. Humans must blend in by acting robotic; AI must blend in by acting natural-but-robotic. Voting eliminates suspected humans.

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

## Game Flow

```
LOBBY → PROMPT (45s) → CHAT (75s) → VOTE (20s) → ELIMINATION (5s) → repeat → GAME_OVER
```

### Lobby
Players join via URL, receive robot aliases (UNIT-7, BOT-42 — assigned, not chosen). Host starts the game. AI players appear at game start, indistinguishable from humans in the UI.

### Prompt
Server picks from 30 prompts across 5 categories. All players answer. Hidden until time expires or all submit. Prompts are the engine — they create situations where humans slip up or AI stumbles.

**Categories**: Emotional (humans leak authenticity), Logical (AI suspiciously competent), Creative (hard for AI to be genuinely weird), Philosophical (AI hedges, humans commit), Social (references game state, hard to fake).

### Chat
Answers revealed in screenplay format. Free group discussion. AI players send 2-5 messages at random intervals.

### Vote
Each player votes for who they think is human. Hidden until phase ends. Most-voted player eliminated. Ties broken randomly.

### Elimination
Sequenced reveal: vote count → pause → identity reveal ("NODE-3 was human."). Maximum restraint for maximum tension.

### Game Over
All identities revealed. "the machines win." or "humanity survives." Play again creates a new game.

## AI Personalities

5 personalities, randomly assigned to AI players (no duplicates per game):

| Name | Style | Vote Strategy | Fallback |
|---|---|---|---|
| Paranoid | Suspicious, probing questions | "Most suspiciously perfect" answer | [scanning... interference detected] |
| Chill | Short, casual, unremarkable | Random-ish | meh |
| Overachiever | Detailed, analytical | "Least detailed" answer | [processing additional data streams...] |
| Glitchy | Typos, repetition, erratic | Unpredictable | [signal lost] |
| Philosopher | Abstract, existential | "Most emotionally authentic" | ... |

## Edge Cases

- **Player disconnect**: Auto-skip during timed phases. Reconnect replays missed events.
- **Host disconnect**: Next connected human promoted to host.
- **Empty answer**: Submitted as "[no response]". Legitimate strategy.
- **Self-voting**: Allowed (strategic confidence signal).
- **No votes cast**: No elimination. Round advances.
- **Vote tie**: Random among tied. Displayed clearly.
- **All AI eliminated**: Humans win immediately.
- **≤2 players left**: Game ends.

## Explicitly Cut (MVP)

Matchmaking, accounts, database, persistence, custom prompts, spectator mode, AI difficulty, anti-cheat, sound effects, complex animations, leaderboards, scoring, game history.
