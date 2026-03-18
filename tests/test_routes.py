"""Tests for route handlers — HTTP validation layer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from schemas.game_state import (
    GamePhase,
    Matchup,
    RoundType,
)
from tests.conftest import seed_game

# ---------------------------------------------------------------------------
# Create / Get game
# ---------------------------------------------------------------------------


class TestCreateAndGetGame:
    async def test_create_game(self, client, mock_ai):
        resp = await client.post("/games")
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
        assert "join_url" in data

    async def test_get_game(self, client, mock_ai):
        create = await client.post("/games")
        gid = create.json()["game_id"]
        resp = await client.get(f"/games/{gid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["game_id"] == gid
        assert data["phase"] == "lobby"

    async def test_get_nonexistent_game(self, client, mock_ai):
        resp = await client.get("/games/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Join game
# ---------------------------------------------------------------------------


class TestJoinGame:
    async def test_join_success(self, client, mock_ai):
        create = await client.post("/games")
        gid = create.json()["game_id"]
        resp = await client.post(f"/games/{gid}/join", json={"player_name": "Alice"})
        assert resp.status_code == 200
        data = resp.json()
        assert "player_id" in data
        assert "alias" in data
        assert data["game_id"] == gid

    async def test_join_nonexistent_game(self, client, mock_ai):
        resp = await client.post("/games/nonexistent/join", json={"player_name": "Alice"})
        assert resp.status_code == 404

    async def test_join_game_in_progress(self, client, mock_ai):
        game_id, _session, _players = seed_game(GamePhase.PROMPT)
        resp = await client.post(f"/games/{game_id}/join", json={"player_name": "Alice"})
        assert resp.status_code == 400
        assert "already in progress" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Start game
# ---------------------------------------------------------------------------


class TestStartGame:
    async def test_start_nonexistent(self, client, mock_ai):
        resp = await client.post(
            "/games/nonexistent/start",
            json={"player_id": "p1", "ai_count": 2},
        )
        assert resp.status_code == 404

    async def test_start_non_host(self, client, mock_ai):
        game_id, _session, _players = seed_game(GamePhase.LOBBY)
        resp = await client.post(
            f"/games/{game_id}/start",
            json={"player_id": "h2", "ai_count": 2},  # h2 is not host
        )
        assert resp.status_code == 400
        assert "host" in resp.json()["detail"].lower()

    async def test_start_already_started(self, client, mock_ai):
        game_id, _session, _players = seed_game(GamePhase.PROMPT)
        resp = await client.post(
            f"/games/{game_id}/start",
            json={"player_id": "h1", "ai_count": 2},
        )
        assert resp.status_code == 400
        assert "already started" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Submit answer
# ---------------------------------------------------------------------------


class TestSubmitAnswer:
    async def test_wrong_phase(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.MATCHUP)
        resp = await client.post(
            f"/games/{game_id}/answer",
            json={"player_id": "h1", "answer": "test"},
        )
        assert resp.status_code == 400
        assert "not in prompt phase" in resp.json()["detail"].lower()

    async def test_nonexistent_player(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.PROMPT)
        resp = await client.post(
            f"/games/{game_id}/answer",
            json={"player_id": "nonexistent", "answer": "test"},
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()

    async def test_duplicate_answer(self, client, mock_ai):
        game_id, session, _ = seed_game(GamePhase.PROMPT)
        session.state.current_round.answers["h1"] = "already answered"
        resp = await client.post(
            f"/games/{game_id}/answer",
            json={"player_id": "h1", "answer": "another"},
        )
        assert resp.status_code == 400
        assert "already answered" in resp.json()["detail"].lower()

    async def test_success(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.PROMPT)
        resp = await client.post(
            f"/games/{game_id}/answer",
            json={"player_id": "h1", "answer": "my answer"},
        )
        assert resp.status_code == 200

    async def test_reading_period_rejection(self, client, mock_ai):
        game_id, session, _ = seed_game(GamePhase.PROMPT)
        # Set writing_begins_at to the future
        session.state.current_round.writing_begins_at = datetime.now(UTC) + timedelta(seconds=30)
        resp = await client.post(
            f"/games/{game_id}/answer",
            json={"player_id": "h1", "answer": "test"},
        )
        assert resp.status_code == 400
        assert "reading period" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Matchup vote
# ---------------------------------------------------------------------------


class TestMatchupVote:
    def _seed_matchup_game(self):
        game_id, session, players = seed_game(GamePhase.MATCHUP, round_type=RoundType.TASK)
        session.state.current_round.matchups = [
            Matchup(
                pair=["h1", "h2"],
                prompt_text="test prompt",
                prompt_category="test",
            ),
            Matchup(
                pair=["a1", "a2"],
                prompt_text="test prompt 2",
                prompt_category="test",
            ),
        ]
        return game_id, session, players

    async def test_success(self, client, mock_ai):
        game_id, session, _ = self._seed_matchup_game()
        resp = await client.post(
            f"/games/{game_id}/matchup-vote",
            json={"player_id": "a1", "matchup_index": 0, "choice": 0},
        )
        assert resp.status_code == 200
        assert session.state.current_round.matchups[0].votes["a1"] == 0

    async def test_wrong_phase(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.PROMPT)
        resp = await client.post(
            f"/games/{game_id}/matchup-vote",
            json={"player_id": "h1", "matchup_index": 0, "choice": 0},
        )
        assert resp.status_code == 400
        assert "matchup" in resp.json()["detail"].lower()

    async def test_own_matchup_rejected(self, client, mock_ai):
        game_id, _, _ = self._seed_matchup_game()
        # h1 is in matchup 0, can't vote on it
        resp = await client.post(
            f"/games/{game_id}/matchup-vote",
            json={"player_id": "h1", "matchup_index": 0, "choice": 0},
        )
        assert resp.status_code == 400
        assert "own matchup" in resp.json()["detail"].lower()

    async def test_invalid_choice(self, client, mock_ai):
        game_id, _, _ = self._seed_matchup_game()
        resp = await client.post(
            f"/games/{game_id}/matchup-vote",
            json={"player_id": "a1", "matchup_index": 0, "choice": 2},
        )
        assert resp.status_code == 400

    async def test_invalid_matchup_index(self, client, mock_ai):
        game_id, _, _ = self._seed_matchup_game()
        resp = await client.post(
            f"/games/{game_id}/matchup-vote",
            json={"player_id": "a1", "matchup_index": 99, "choice": 0},
        )
        assert resp.status_code == 400
