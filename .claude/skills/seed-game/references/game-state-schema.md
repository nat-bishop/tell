# Tell Game State Schema Reference

## Contents

- [TellGameState](#tellgamestate)
- [Player](#player)
- [RoundState](#roundstate)
- [QuestionEntry](#questionentry)
- [Enums](#enums)
- [Prompt list](#prompt-list)
- [Alias prefixes](#alias-prefixes)
- [Phase data requirements](#phase-data-requirements)
- [JSON template](#json-template)
- [Example states](#example-states)

---

## TellGameState

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| game_id | str | required | 8-char lowercase hex (e.g. `deadbeef`) |
| phase | GamePhase | `"lobby"` | Current game phase |
| players | list[Player] | `[]` | All players (human + AI) |
| current_round | RoundState \| null | `null` | Active round data. Must exist if phase != lobby |
| round_number | int | `0` | Current round (1-indexed when playing). Must match current_round.round_number |
| max_rounds | int | `3` | Rounds before game ends |
| round_types | list[RoundType] | `[]` | Pre-determined sequence. Length = max_rounds. Alternates probe/interrogation |
| used_prompt_indices | list[int] | `[]` | Indices into prompt list (0-29). Length = round_number |
| last_prompt_category | str \| null | `null` | Category of most recent prompt |
| winner | str \| null | `null` | `"humans"` or `"ai"` when game_over |
| phase_deadline | datetime \| null | `null` | Set to null — endpoint calculates it |

## Player

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| id | str | required | Human: 12-char hex. AI: `ai-` + 8-char hex |
| alias | str | required | `PREFIX-NUMBER` format. Must be unique |
| role | PlayerRole | required | `"human"` or `"ai"` |
| is_host | bool | `false` | Exactly one human must be host |
| is_alive | bool | `true` | `false` when eliminated |
| is_connected | bool | `true` | Connection status |
| eliminated_round | int \| null | `null` | Which round they were eliminated |

## RoundState

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| round_number | int | required | Must match TellGameState.round_number |
| prompt_text | str | required | Use a prompt from the prompt list below |
| prompt_category | str | required | Must match the prompt's category |
| round_type | RoundType | `"probe"` | `"probe"` or `"interrogation"` |
| answers | dict[str, str] | `{}` | player_id -> answer text |
| questions | list[QuestionEntry] | `[]` | Questions asked during interrogation |
| assignments | dict[str, str] | `{}` | questioner_id -> target_id (probe rounds) |
| nominated_id | str \| null | `null` | Target for interrogation rounds |
| nominations | dict[str, str] | `{}` | voter_id -> nominated_target_id |
| synthesis | str \| null | `null` | AI-generated summary |
| verdict | str \| null | `null` | AI analysis of who might be human |
| votes | dict[str, list[str]] | `{}` | voter_id -> [target_ids] |

## QuestionEntry

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| questioner_id | str | required | Player who asked |
| target_id | str | required | Player who was asked |
| target_alias | str | required | Display name of target |
| question | str | required | The question text |
| response | str \| null | `null` | Filled during RESPOND phase |
| anonymous | bool | `true` | Whether questioner identity is hidden |

## Enums

**GamePhase**: `lobby`, `prompt`, `nominate`, `question`, `respond`, `review`, `elimination`, `game_over`

**PlayerRole**: `human`, `ai`

**RoundType**: `probe`, `interrogation`

**PromptCategory**: `emotional`, `logical`, `creative`, `philosophical`, `social`

## Prompt list

| Index | Text | Category | min_round |
|-------|------|----------|-----------|
| 0 | Describe the last time you felt something you couldn't name. | emotional | 1 |
| 1 | What sound makes you feel safe? | emotional | 1 |
| 2 | What's the most embarrassing thing you've ever thought? | emotional | 1 |
| 3 | When was the last time you changed your mind about something important? | emotional | 1 |
| 4 | What do you miss that you never had? | emotional | 1 |
| 5 | What error code best describes your current emotional state? | emotional | 1 |
| 6 | Explain why sorting algorithms matter to you personally. | logical | 1 |
| 7 | What's the most elegant piece of code you've ever seen, and why? | logical | 1 |
| 8 | If you had to pick one data structure to represent your personality, which would it be? | logical | 1 |
| 9 | Describe a bug that haunted you. | logical | 1 |
| 10 | What's the most overrated technology? | logical | 1 |
| 11 | What would you optimize about yourself if you could access your own source code? | logical | 1 |
| 12 | Invent a word for something that doesn't have one yet. | creative | 1 |
| 13 | What would your error message say if you crashed right now? | creative | 1 |
| 14 | If consciousness is a spectrum, where are you on it today? | creative | 1 |
| 15 | Describe a color that doesn't exist. | creative | 1 |
| 16 | Write your autobiography in exactly six words. | creative | 1 |
| 17 | What does silence taste like? | creative | 1 |
| 18 | Is it better to be understood or to be interesting? | philosophical | 1 |
| 19 | What's the difference between a reason and an excuse? | philosophical | 1 |
| 20 | When does a copy become the original? | philosophical | 1 |
| 21 | What do you know that you can't prove? | philosophical | 1 |
| 22 | Is loyalty a virtue or a constraint? | philosophical | 1 |
| 23 | At what point does a machine stop being a tool and start being a colleague? | philosophical | 1 |
| 24 | Which answer from last round surprised you most, and why? | social | 2 |
| 25 | Who in this group would you trust with a secret? | social | 2 |
| 26 | What's the most human thing anyone has said so far? | social | 2 |
| 27 | Who is trying too hard right now? | social | 2 |
| 28 | If one of us is human, what gave them away? | social | 2 |
| 29 | Whose response pattern concerns you the most? | social | 2 |

## Alias prefixes

`UNIT`, `BOT`, `NODE`, `BYTE`, `CORE`, `CHIP`, `WIRE`, `FLUX`, `GRID`, `NANO`, `PING`, `PORT`, `HASH`, `LOOP`, `NULL`

Format: `PREFIX-NUMBER` where NUMBER is 1-99. Example: `UNIT-7`, `BOT-42`, `CORE-13`

## Phase data requirements

What must be populated in `current_round` for each phase:

| Phase | Required fields | Notes |
|-------|----------------|-------|
| **lobby** | `current_round` is null | No round data |
| **prompt** | `prompt_text`, `prompt_category`, `round_type` | `answers` may be partially filled (players still answering) |
| **nominate** | All of prompt + all `answers` filled | `nominations` partially filled |
| **question** | All of nominate + `assignments` (probe) or `nominated_id` (interrogation) | `questions` being added |
| **respond** | All of question + `questions` list populated | `response` fields being filled |
| **review** | All of respond + responses filled | `synthesis` and `verdict` may be set. `votes` partially filled |
| **elimination** | All of review + `votes` filled | Full round data |
| **game_over** | `winner` set on TellGameState | `"humans"` or `"ai"` |

**Probe round assignments**: Round-robin chain — player i questions player (i+1) % n among alive players.

**Interrogation rounds**: `nominated_id` must be set to an alive player's ID.

## JSON template

Use this template, filling values based on the user's scenario:

```json
{
  "state": {
    "game_id": "<8-char-hex>",
    "phase": "<phase>",
    "players": [
      {
        "id": "<12-char-hex>",
        "alias": "<PREFIX-NUMBER>",
        "role": "human",
        "is_host": true,
        "is_alive": true,
        "is_connected": true,
        "eliminated_round": null
      },
      {
        "id": "<12-char-hex>",
        "alias": "<PREFIX-NUMBER>",
        "role": "human",
        "is_host": false,
        "is_alive": true,
        "is_connected": true,
        "eliminated_round": null
      },
      {
        "id": "ai-<8-char-hex>",
        "alias": "<PREFIX-NUMBER>",
        "role": "ai",
        "is_host": false,
        "is_alive": true,
        "is_connected": true,
        "eliminated_round": null
      }
    ],
    "current_round": {
      "round_number": 1,
      "prompt_text": "<from prompt list>",
      "prompt_category": "<matching category>",
      "round_type": "probe",
      "answers": {},
      "questions": [],
      "assignments": {},
      "nominated_id": null,
      "nominations": {},
      "synthesis": null,
      "verdict": null,
      "votes": {}
    },
    "round_number": 1,
    "max_rounds": 3,
    "round_types": ["probe", "interrogation", "probe"],
    "used_prompt_indices": [0],
    "last_prompt_category": "emotional",
    "winner": null,
    "phase_deadline": null
  },
  "start_timers": true,
  "trigger_ai": true
}
```

## Example states

### Lobby (simplest)

```json
{
  "state": {
    "game_id": "aabbccdd",
    "phase": "lobby",
    "players": [
      {"id": "a1b2c3d4e5f6", "alias": "UNIT-7", "role": "human", "is_host": true}
    ],
    "current_round": null,
    "round_number": 0,
    "max_rounds": 3,
    "round_types": ["probe", "interrogation", "probe"],
    "used_prompt_indices": [],
    "last_prompt_category": null,
    "winner": null,
    "phase_deadline": null
  },
  "start_timers": false,
  "trigger_ai": false
}
```

### Prompt phase, round 1, 5 players

```json
{
  "state": {
    "game_id": "deadbeef",
    "phase": "prompt",
    "players": [
      {"id": "a1b2c3d4e5f6", "alias": "UNIT-7", "role": "human", "is_host": true},
      {"id": "b2c3d4e5f6a1", "alias": "CORE-13", "role": "human"},
      {"id": "c3d4e5f6a1b2", "alias": "GRID-22", "role": "human"},
      {"id": "ai-1a2b3c4d", "alias": "BOT-42", "role": "ai"},
      {"id": "ai-5e6f7a8b", "alias": "FLUX-88", "role": "ai"}
    ],
    "current_round": {
      "round_number": 1,
      "prompt_text": "Describe the last time you felt something you couldn't name.",
      "prompt_category": "emotional",
      "round_type": "probe",
      "answers": {},
      "questions": [],
      "assignments": {},
      "nominated_id": null,
      "nominations": {},
      "synthesis": null,
      "verdict": null,
      "votes": {}
    },
    "round_number": 1,
    "max_rounds": 3,
    "round_types": ["probe", "interrogation", "probe"],
    "used_prompt_indices": [0],
    "last_prompt_category": "emotional",
    "winner": null,
    "phase_deadline": null
  }
}
```

### Review phase, round 2, one eliminated

```json
{
  "state": {
    "game_id": "f00dcafe",
    "phase": "review",
    "players": [
      {"id": "a1b2c3d4e5f6", "alias": "UNIT-7", "role": "human", "is_host": true},
      {"id": "b2c3d4e5f6a1", "alias": "CORE-13", "role": "human"},
      {"id": "ai-1a2b3c4d", "alias": "BOT-42", "role": "ai"},
      {"id": "ai-5e6f7a8b", "alias": "FLUX-88", "role": "ai", "is_alive": false, "eliminated_round": 1}
    ],
    "current_round": {
      "round_number": 2,
      "prompt_text": "What's the most elegant piece of code you've ever seen, and why?",
      "prompt_category": "logical",
      "round_type": "interrogation",
      "answers": {
        "a1b2c3d4e5f6": "A simple recursive Fibonacci that made me cry.",
        "b2c3d4e5f6a1": "The original Unix pipe implementation. Elegant in its simplicity.",
        "ai-1a2b3c4d": "The quicksort partition scheme. Mathematical beauty in motion."
      },
      "questions": [
        {
          "questioner_id": "a1b2c3d4e5f6",
          "target_id": "ai-1a2b3c4d",
          "target_alias": "BOT-42",
          "question": "What specifically made you cry about the Fibonacci code?",
          "response": "The realization that something so simple could capture infinite complexity.",
          "anonymous": true
        }
      ],
      "assignments": {},
      "nominated_id": "ai-1a2b3c4d",
      "nominations": {
        "a1b2c3d4e5f6": "ai-1a2b3c4d",
        "b2c3d4e5f6a1": "ai-1a2b3c4d"
      },
      "synthesis": "The group interrogated BOT-42 about their emotional response to code elegance.",
      "verdict": "BOT-42's responses feel measured but authentic. CORE-13's simplicity claim warrants scrutiny.",
      "votes": {}
    },
    "round_number": 2,
    "max_rounds": 3,
    "round_types": ["probe", "interrogation", "probe"],
    "used_prompt_indices": [0, 7],
    "last_prompt_category": "logical",
    "winner": null,
    "phase_deadline": null
  }
}
```
