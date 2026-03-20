# Design Principles

Checklist for evaluating new features, round types, and mechanic changes. Each principle is testable — a reviewer can check yes/no against a proposed change.

---

## Flow

1. **Pull-along.** The game always moves forward — timers advance with or without you. No player ever waits on another.

2. **One task at a time.** Each phase is exactly one action: write, vote, or tap. If a round needs instructions, simplify it.

3. **Simplest viable input.** Tap over type, four options over ten. Every choice should be meaningful and the input method should be the lightest one that serves the round.

4. **Contrast, not monotony.** Alternate fast/slow, tense/relaxed, solo/group. Never sustain maximum intensity.

## Detection

5. **Legible evidence.** Every round must produce output that's visible and comparable — gallery of answers, correctness grids, timing profiles. If you can't display the evidence clearly, the round doesn't work.

6. **Multiple explanations.** Any player action should have 5-8 plausible interpretations. One explanation means the game is solved; infinite means players disengage.

7. **Bidirectional viability.** Every answer should plausibly be human OR AI depending on interpretation. If an action can only make sense for one side, it reveals too much.

8. **Distinct skill axes.** Each round type tests a different ability. If a new round tests the same thing as an existing one, it's a variant, not a new type.

## Humor

9. **The game makes the player look funny.** Prompts are the setup, players are the punchline. Never add a feature that competes with players for laughs.

10. **Constraints create comedy.** Narrow the format, not the creativity. Word limits, syllable counts, time pressure — compression is where comedy lives.

11. **The reveal is the payoff.** "UNIT-7 was AI the whole time?" The post-game conversation is half the entertainment. Design for that moment.

## Simplicity

12. **No elimination.** Everyone plays every round. No spectators.

13. **Speed over complexity.** The best rounds need zero explanation. The UI makes the action obvious.

14. **Screenshottable over interesting.** If a feature doesn't produce something you'd show a friend, it's probably not worth building.

## AI Integration

15. **AI fills seats, not roles.** AI ensures games always fire and are fun at any player count. LLM features give players information to act on — they never act for players.

16. **Process over output.** The best detection surfaces come from *how* players interact (timing, click patterns, behavioral sequences), not just *what* they produce. Behavioral signatures are harder to fake than text.
