"""Tests for route handlers — HTTP validation layer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from schemas.game_state import (
    GamePhase,
    Matchup,
    QuestionEntry,
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
        game_id, _, _ = seed_game(GamePhase.REVIEW)
        resp = await client.post(
            f"/games/{game_id}/answer",
            json={"player_id": "h1", "answer": "test"},
        )
        assert resp.status_code == 400
        assert "not in prompt phase" in resp.json()["detail"].lower()

    async def test_dead_player(self, client, mock_ai):
        game_id, session, _ = seed_game(GamePhase.PROMPT)
        # Kill h2
        for p in session.state.players:
            if p.id == "h2":
                p.is_alive = False
        resp = await client.post(
            f"/games/{game_id}/answer",
            json={"player_id": "h2", "answer": "test"},
        )
        assert resp.status_code == 400
        assert "eliminated" in resp.json()["detail"].lower()

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
# Nominate player
# ---------------------------------------------------------------------------


class TestNominatePlayer:
    async def test_wrong_phase(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.PROMPT)
        resp = await client.post(
            f"/games/{game_id}/nominate",
            json={"player_id": "h1", "target_id": "a1"},
        )
        assert resp.status_code == 400

    async def test_invalid_target(self, client, mock_ai):
        game_id, session, _ = seed_game(GamePhase.NOMINATE, round_type=RoundType.INTERROGATION)
        # Kill a1 so it's invalid
        for p in session.state.players:
            if p.id == "a1":
                p.is_alive = False
        resp = await client.post(
            f"/games/{game_id}/nominate",
            json={"player_id": "h1", "target_id": "a1"},
        )
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower()

    async def test_success(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.NOMINATE, round_type=RoundType.INTERROGATION)
        resp = await client.post(
            f"/games/{game_id}/nominate",
            json={"player_id": "h1", "target_id": "a1"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Submit question
# ---------------------------------------------------------------------------


class TestSubmitQuestion:
    def _setup_question_phase(self):
        game_id, session, players = seed_game(
            GamePhase.QUESTION, round_type=RoundType.INTERROGATION
        )
        session.state.current_round.nominated_id = "h2"
        return game_id, session, players

    async def test_wrong_phase(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.PROMPT)
        resp = await client.post(
            f"/games/{game_id}/question",
            json={"player_id": "h1", "question": "Why?"},
        )
        assert resp.status_code == 400

    async def test_hot_seated_cannot_ask(self, client, mock_ai):
        game_id, _session, _ = self._setup_question_phase()
        resp = await client.post(
            f"/games/{game_id}/question",
            json={"player_id": "h2", "question": "Why?"},  # h2 is nominated
        )
        assert resp.status_code == 400
        assert "hot-seated" in resp.json()["detail"].lower()

    async def test_duplicate_question(self, client, mock_ai):
        game_id, session, _ = self._setup_question_phase()
        session.state.current_round.questions.append(
            QuestionEntry(
                questioner_id="h1", target_id="h2", target_alias="BOT-42", question="First"
            )
        )
        resp = await client.post(
            f"/games/{game_id}/question",
            json={"player_id": "h1", "question": "Second?"},
        )
        assert resp.status_code == 400
        assert "already submitted" in resp.json()["detail"].lower()

    async def test_success(self, client, mock_ai):
        game_id, _session, _ = self._setup_question_phase()
        resp = await client.post(
            f"/games/{game_id}/question",
            json={"player_id": "h1", "question": "Why did you say that?"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Submit response
# ---------------------------------------------------------------------------


class TestSubmitResponse:
    def _setup_respond_phase(self):
        game_id, session, players = seed_game(GamePhase.RESPOND, round_type=RoundType.INTERROGATION)
        session.state.current_round.nominated_id = "h2"
        session.state.current_round.questions = [
            QuestionEntry(
                questioner_id="h1",
                target_id="h2",
                target_alias="BOT-42",
                question="Why?",
            )
        ]
        return game_id, session, players

    async def test_wrong_phase(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.PROMPT)
        resp = await client.post(
            f"/games/{game_id}/respond",
            json={"player_id": "h1", "response": "Because"},
        )
        assert resp.status_code == 400

    async def test_non_nominated_cannot_respond(self, client, mock_ai):
        game_id, _, _ = self._setup_respond_phase()
        resp = await client.post(
            f"/games/{game_id}/respond",
            json={"player_id": "h1", "response": "Because"},  # h1 is not nominated
        )
        assert resp.status_code == 400
        assert "hot-seated" in resp.json()["detail"].lower()

    async def test_success(self, client, mock_ai):
        game_id, _, _ = self._setup_respond_phase()
        resp = await client.post(
            f"/games/{game_id}/respond",
            json={"player_id": "h2", "response": "Because I'm a robot"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Cast vote
# ---------------------------------------------------------------------------


class TestCastVote:
    async def test_wrong_phase(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.PROMPT)
        resp = await client.post(
            f"/games/{game_id}/vote",
            json={"player_id": "h1", "target_ids": ["a1"]},
        )
        assert resp.status_code == 400

    async def test_self_vote(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.REVIEW)
        resp = await client.post(
            f"/games/{game_id}/vote",
            json={"player_id": "h1", "target_ids": ["h1"]},
        )
        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"].lower()

    async def test_too_many_votes(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.REVIEW)
        # 4 alive = max 3 votes, try 4
        resp = await client.post(
            f"/games/{game_id}/vote",
            json={"player_id": "h1", "target_ids": ["h2", "a1", "a2", "h2"]},
        )
        assert resp.status_code == 400
        assert "max" in resp.json()["detail"].lower()

    async def test_invalid_target(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.REVIEW)
        resp = await client.post(
            f"/games/{game_id}/vote",
            json={"player_id": "h1", "target_ids": ["nonexistent"]},
        )
        assert resp.status_code == 400
        assert "invalid" in resp.json()["detail"].lower()

    async def test_success(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.REVIEW)
        resp = await client.post(
            f"/games/{game_id}/vote",
            json={"player_id": "h1", "target_ids": ["a1"]},
        )
        assert resp.status_code == 200

    async def test_changeable_votes(self, client, mock_ai):
        game_id, session, _ = seed_game(GamePhase.REVIEW)
        # Vote first time
        await client.post(
            f"/games/{game_id}/vote",
            json={"player_id": "h1", "target_ids": ["a1"]},
        )
        # Change vote
        resp = await client.post(
            f"/games/{game_id}/vote",
            json={"player_id": "h1", "target_ids": ["a2"]},
        )
        assert resp.status_code == 200
        assert session.state.current_round.votes["h1"] == ["a2"]


# ---------------------------------------------------------------------------
# Discussion messages
# ---------------------------------------------------------------------------


class TestDiscussionMessage:
    async def test_success(self, client, mock_ai):
        game_id, _session, _players = seed_game(GamePhase.REVIEW)
        with patch(
            "backend.api.routes.actions.record_discussion_message",
            create=True,
        ):
            resp = await client.post(
                f"/games/{game_id}/discussion-message",
                json={"player_id": "h1", "message": "I think a1 is human"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_rate_limit_fourth_message(self, client, mock_ai):
        game_id, session, _players = seed_game(GamePhase.REVIEW)
        # Pre-set discussion count to 3 (at limit)
        session.state.current_round.discussion_counts["h1"] = 3
        resp = await client.post(
            f"/games/{game_id}/discussion-message",
            json={"player_id": "h1", "message": "One more"},
        )
        assert resp.status_code == 400
        assert "limit" in resp.json()["detail"].lower()

    async def test_wrong_phase(self, client, mock_ai):
        game_id, _session, _players = seed_game(GamePhase.PROMPT)
        resp = await client.post(
            f"/games/{game_id}/discussion-message",
            json={"player_id": "h1", "message": "Hello"},
        )
        assert resp.status_code == 400
        assert "review" in resp.json()["detail"].lower()

    async def test_message_too_long(self, client, mock_ai):
        game_id, _session, _players = seed_game(GamePhase.REVIEW)
        resp = await client.post(
            f"/games/{game_id}/discussion-message",
            json={"player_id": "h1", "message": "x" * 121},
        )
        assert resp.status_code == 400
        assert "too long" in resp.json()["detail"].lower()

    async def test_dead_player_rejected(self, client, mock_ai):
        game_id, session, _players = seed_game(GamePhase.REVIEW)
        # Kill h1
        for p in session.state.players:
            if p.id == "h1":
                p.is_alive = False
                break
        resp = await client.post(
            f"/games/{game_id}/discussion-message",
            json={"player_id": "h1", "message": "Ghost message"},
        )
        assert resp.status_code == 400
        assert "eliminated" in resp.json()["detail"].lower()

    async def test_empty_message(self, client, mock_ai):
        game_id, _session, _players = seed_game(GamePhase.REVIEW)
        resp = await client.post(
            f"/games/{game_id}/discussion-message",
            json={"player_id": "h1", "message": "   "},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    async def test_nonexistent_game(self, client, mock_ai):
        resp = await client.post(
            "/games/nonexistent/discussion-message",
            json={"player_id": "h1", "message": "Hello"},
        )
        assert resp.status_code == 404


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
