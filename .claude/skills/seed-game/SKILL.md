---
name: seed-game
description: >
  Seeds a Tell game with a specific state for debugging and testing.
  Translates natural language scenarios into valid TellGameState JSON
  and POSTs to the backend debug endpoint. Use when the user wants to
  set up a game scenario, inject test state, create a debug game, or
  skip to a specific game phase.
---

# Seed Game

Inject a game at any phase into the running dev server. Describe the scenario in plain English — this skill builds valid state JSON and POSTs it.

## Workflow

1. Parse `$ARGUMENTS` for the desired scenario
2. Read [references/game-state-schema.md](references/game-state-schema.md) for the full schema, valid values, and JSON template
3. Generate a complete `TellGameState` JSON object following the template
4. POST to the debug endpoint:

```bash
curl -s -X POST http://localhost:8501/debug/seed \
  -H "Content-Type: application/json" \
  -d '{"state": <JSON>, "start_timers": true, "trigger_ai": true}'
```

5. If the response is a 422, read the error, fix the JSON, and retry
6. Report the result including the game URL
7. Suggest using Playwright MCP to open the page and test interactions

## Critical invariants

- **Player IDs**: humans = 12-char lowercase hex (`a1b2c3d4e5f6`), AI = `ai-` + 8-char hex (`ai-1a2b3c4d`)
- **Aliases**: `PREFIX-NUMBER` where PREFIX is from [UNIT, BOT, NODE, BYTE, CORE, CHIP, WIRE, FLUX, GRID, NANO, PING, PORT, HASH, LOOP, NULL] and NUMBER is 1-99. All aliases unique.
- **Exactly one** human player has `is_host: true`
- If phase is not `lobby`: `current_round` must exist, `round_number` must match `current_round.round_number`
- **`round_types`**: list of `max_rounds` entries, alternating `"probe"` / `"interrogation"` starting with `"probe"`
- **`used_prompt_indices`**: length equals `round_number`, values are valid prompt indices (0-29)
- **`last_prompt_category`**: matches the category of the prompt at `used_prompt_indices[-1]`
- **Eliminated players**: `is_alive: false`, `eliminated_round` set, must NOT appear in current round's `answers` or `votes`
- **`phase_deadline`**: set to `null` — the endpoint calculates it when `start_timers: true`
- See the schema reference for phase-specific data requirements

## Defaults

When the user doesn't specify, use:
- 3 humans, 2 AI players
- Round 1, probe type
- Prompt index 0 ("Describe the last time you felt something you couldn't name.", category "emotional")
- `start_timers: true`, `trigger_ai: true`
- `max_rounds: 3`

## Examples

**Input**: `game in prompt phase`

**Output**: POST succeeds, report:
```
Seeded game `a1b2c3d4` in prompt phase with 5 players (3 human, 2 AI).
Open: http://localhost:3500/game/a1b2c3d4
```

**Input**: `review phase, 4 players, round 2, one eliminated`

**Output**: POST succeeds, report:
```
Seeded game `f00dcafe` in review phase, round 2.
4 players (2 human, 2 AI), 1 eliminated in round 1.
Open: http://localhost:3500/game/f00dcafe
```

## After seeding

Tell the user the game URL and suggest:
- Open the URL in a browser to see the game
- Use `mcp__plugin_playwright_playwright__browser_navigate` to open the page programmatically
- Use `mcp__plugin_playwright_playwright__browser_snapshot` to verify the rendered state

## Errors

- **404**: `TELL_DEBUG` is not set to `true`, or the server is not running
- **422**: Invalid state JSON — read the validation error, fix, and retry
