---
name: seed-game
description: >
  Seeds a Tell game at any phase for debugging and testing.
  Translates natural language scenarios into valid game state
  and injects it via the debug endpoint. Handles all three round
  types (Task, Interrogation, Word Chain) and all phases including
  the CHAIN sub-round system. Triggers when testing a game phase,
  debugging UI rendering, setting up a test scenario, checking how
  voting or elimination works, or skipping to a specific game state.
---

# Seed Game

Inject a game at any phase into the running dev server. Describe the scenario in plain English — a bundled script builds valid state JSON and this skill POSTs it.

## Prerequisites

- Server running (`make dev` or `make backend`)
- `TELL_LOG_LEVEL=DEBUG` set in `.env` (this enables the `/debug/seed` endpoint)

## Workflow

1. Parse `$ARGUMENTS` for the desired scenario
2. Translate to CLI args for the generator script (see mapping below)
3. Run the script from the project root:

```bash
python .claude/skills/seed-game/scripts/generate_seed.py [args]
```

4. Capture the JSON output
5. POST it to `http://localhost:8501/debug/seed`:

```bash
python .claude/skills/seed-game/scripts/generate_seed.py [args] | curl -s -X POST http://localhost:8501/debug/seed -H "Content-Type: application/json" -d @-
```

6. If the response is a 422, read the validation error, fix the args, and retry
7. Report the game URL and suggest connecting as a player

## Translating requests to script args

The script accepts `--phase`, `--round`, `--humans`, `--ai`, `--eliminated`, `--no-timers`, `--no-ai`, `--sub-round`, `--round-type`, `--winner`. All optional with sensible defaults (prompt phase, round 1, 3 humans, 2 AI).

| User says | Script args |
|-----------|------------|
| "prompt phase" / "game in prompt" | `--phase prompt` (default) |
| "review phase" | `--phase review` |
| "round 2" / "second round" | `--round 2` |
| "one eliminated" / "someone dead" | `--eliminated 1` |
| "frozen" / "for screenshots" / "don't advance" | `--no-timers --no-ai` |
| "word chain mid-round" / "chain phase" | `--phase chain --round 3` (round 3 is first word_chain) |
| "4 sub-rounds done" | `--sub-round 4` |
| "late game" / "almost over" | `--round 3 --eliminated 2` |
| "game over, AI wins" | `--phase game_over --winner ai` |
| "interrogation review" | `--phase review --round 2` (round 2 is first interrogation) |
| "no AI behavior" / "humans only" | `--no-ai` |
| "4 humans, 3 AI" | `--humans 4 --ai 3` |

The round type is auto-determined from the round number using the cycle: round 1 = Task, round 2 = Interrogation, round 3 = Word Chain, round 4 = Task, etc. Override with `--round-type` if needed.

## Controlling timers and AI

| Intent | Flags |
|--------|-------|
| Full flow (phase auto-advances, AI acts) | _(default)_ |
| Freeze phase for UI inspection / screenshots | `--no-timers --no-ai` |
| Watch AI behavior only | _(default)_ |
| Test human interactions, no AI interference | `--no-ai` |

## Connecting as a player

After seeding, no browser is authenticated as any player. The frontend stores identity in `sessionStorage` key `tell-{game_id}` as `{"playerId": "<id>", "alias": "<alias>"}`.

To connect as a specific human player, use Playwright:

```
1. browser_navigate to http://localhost:3500/game/{game_id}
2. browser_evaluate: sessionStorage.setItem('tell-{game_id}', JSON.stringify({playerId: '<player_id>', alias: '<alias>'}))
3. browser_evaluate: location.reload()
```

Pick the player_id and alias from the script's JSON output (first human player is usually the simplest choice).

## Edge cases

The script validates impossible combinations and exits with clear error messages:
- Task rounds (1, 4, 7...) have no Q&A phases — no nominate/question/respond
- CHAIN phase only exists in word_chain rounds (3, 6, 9...)
- Can't eliminate more players than completed rounds (one elimination per round)
- Need at least 3 total players, at least 2 alive

## Customization beyond the script

For specific answer text, custom player names, or unusual scenarios not covered by the script args: generate baseline JSON from the script, then modify the output before POSTing. See [references/game-state-schema.md](references/game-state-schema.md) for the full state structure.

## Errors

- **404**: `TELL_LOG_LEVEL` is not `DEBUG` in `.env`, or server not running
- **422**: Invalid state JSON — read the validation error, fix, retry
