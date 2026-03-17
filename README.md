# Tell

A multiplayer social deduction game. Players join a group chat where some participants are AI, some are human. Everyone pretends to be a robot. Each round: answer a prompt, discuss, vote on who's human. Reverse Turing test meets Among Us.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 18+
- A Google API key (for Gemini AI players)

## Quick Start

```bash
cp .env.example .env
# Edit .env to add your GOOGLE_API_KEY

make dev
```

Backend starts on `http://localhost:8501`, frontend on `http://localhost:3500`. Dependencies install automatically.

Open the frontend. Click **play** to enter matchmaking (finds a game automatically), or **private game** to create a shareable link.

## Commands

Run `make` to see all targets.

| Command | Description |
|---|---|
| `make dev` | Start backend + frontend together |
| `make backend` | Start backend only |
| `make frontend` | Start frontend only |
| `make codegen` | Regenerate frontend types from backend OpenAPI |
| `make lint` | Lint + format Python |
| `make test` | Run all tests |
| `make clean` | Remove caches and build artifacts |

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — real-time system, state machine, AI scheduling
- [Game Design](docs/GAME_DESIGN.md) — mechanics, prompts, design rationale
