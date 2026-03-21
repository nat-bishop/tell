"""Tests for route handlers — HTTP validation layer."""

from __future__ import annotations

from schemas.game_state import (
    GamePhase,
    RoundType,
    WagerQuestion,
)
from tests.conftest import seed_game
from tests.factories import make_wager_question

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
        game_id, _session, _players = seed_game(GamePhase.ROUND)
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
            json={"player_id": "p1"},
        )
        assert resp.status_code == 404

    async def test_start_non_host(self, client, mock_ai):
        game_id, _session, _players = seed_game(GamePhase.LOBBY)
        resp = await client.post(
            f"/games/{game_id}/start",
            json={"player_id": "h2"},  # h2 is not host
        )
        assert resp.status_code == 400
        assert "host" in resp.json()["detail"].lower()

    async def test_start_already_started(self, client, mock_ai):
        game_id, _session, _players = seed_game(GamePhase.ROUND)
        resp = await client.post(
            f"/games/{game_id}/start",
            json={"player_id": "h1"},
        )
        assert resp.status_code == 400
        assert "already started" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Submit answer
# ---------------------------------------------------------------------------


class TestSubmitAnswer:
    async def test_wrong_step(self, client, mock_ai):
        # current_step_index=2 is the vote step for task, not compose
        game_id, _, _ = seed_game(GamePhase.ROUND, round_type=RoundType.TASK, current_step_index=2)
        resp = await client.post(
            f"/games/{game_id}/answer",
            json={"player_id": "h1", "answer": "test"},
        )
        assert resp.status_code == 400
        assert "compose" in resp.json()["detail"].lower()

    async def test_nonexistent_player(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.ROUND)
        resp = await client.post(
            f"/games/{game_id}/answer",
            json={"player_id": "nonexistent", "answer": "test"},
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()

    async def test_answer_overwrite(self, client, mock_ai):
        game_id, session, _ = seed_game(GamePhase.ROUND)
        session.state.current_round.answers["h1"] = "already answered"
        resp = await client.post(
            f"/games/{game_id}/answer",
            json={"player_id": "h1", "answer": "updated answer"},
        )
        assert resp.status_code == 200
        assert session.state.current_round.answers["h1"] == "updated answer"

    async def test_success(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.ROUND)
        resp = await client.post(
            f"/games/{game_id}/answer",
            json={"player_id": "h1", "answer": "my answer"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Gallery vote
# ---------------------------------------------------------------------------


class TestGalleryVote:
    async def test_success(self, client, mock_ai):
        game_id, session, _ = seed_game(
            GamePhase.ROUND, round_type=RoundType.TASK, current_step_index=2
        )
        resp = await client.post(
            f"/games/{game_id}/vote",
            json={"player_id": "h1", "voted_for_player_id": "a1"},
        )
        assert resp.status_code == 200
        assert session.state.current_round.gallery_votes["h1"] == "a1"

    async def test_wrong_step(self, client, mock_ai):
        # compose step (index 1), not vote
        game_id, _, _ = seed_game(GamePhase.ROUND)
        resp = await client.post(
            f"/games/{game_id}/vote",
            json={"player_id": "h1", "voted_for_player_id": "a1"},
        )
        assert resp.status_code == 400
        assert "vote" in resp.json()["detail"].lower()

    async def test_vote_for_self(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.ROUND, round_type=RoundType.TASK, current_step_index=2)
        resp = await client.post(
            f"/games/{game_id}/vote",
            json={"player_id": "h1", "voted_for_player_id": "h1"},
        )
        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"].lower()

    async def test_duplicate_vote_overwrites(self, client, mock_ai):
        game_id, session, _ = seed_game(
            GamePhase.ROUND, round_type=RoundType.TASK, current_step_index=2
        )
        # First vote
        resp = await client.post(
            f"/games/{game_id}/vote",
            json={"player_id": "h1", "voted_for_player_id": "a1"},
        )
        assert resp.status_code == 200
        assert session.state.current_round.gallery_votes["h1"] == "a1"

        # Change vote
        resp = await client.post(
            f"/games/{game_id}/vote",
            json={"player_id": "h1", "voted_for_player_id": "a2"},
        )
        assert resp.status_code == 200
        assert session.state.current_round.gallery_votes["h1"] == "a2"

    async def test_invalid_target(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.ROUND, round_type=RoundType.TASK, current_step_index=2)
        resp = await client.post(
            f"/games/{game_id}/vote",
            json={"player_id": "h1", "voted_for_player_id": "nonexistent"},
        )
        assert resp.status_code == 400
        assert "target" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Wager guess
# ---------------------------------------------------------------------------


def seed_wager_game(
    *,
    current_step_index: int = 1,
    wager_questions: list[WagerQuestion] | None = None,
):
    """Seed a game at ROUND/WAGER with wager questions.

    Step indices (after preroll at 0): guess_0=1, bet_0=2, guess_1=3, bet_1=4, ...
    """
    game_id, session, players = seed_game(
        GamePhase.ROUND, round_type=RoundType.WAGER, current_step_index=current_step_index
    )
    rs = session.state.current_round
    rs.wager_questions = wager_questions or [make_wager_question()]
    # Derive question index from step name
    step = session.state.round_step_defs[current_step_index]
    step_name = step["name"]
    if step_name.startswith(("guess_", "bet_")):
        rs.current_sub_round = int(step_name.rsplit("_", 1)[-1])
    else:
        rs.current_sub_round = 0
    return game_id, session, players


class TestWagerGuess:
    async def test_success(self, client, mock_ai):
        game_id, session, _ = seed_wager_game(current_step_index=1)
        resp = await client.post(
            f"/games/{game_id}/wager-guess",
            json={"player_id": "h1", "question_index": 0, "value": 42},
        )
        assert resp.status_code == 200
        assert session.state.current_round.wager_questions[0].guesses["h1"] == 42

    async def test_wrong_phase(self, client, mock_ai):
        game_id, _, _ = seed_game(GamePhase.ROUND, round_type=RoundType.TASK)
        resp = await client.post(
            f"/games/{game_id}/wager-guess",
            json={"player_id": "h1", "question_index": 0, "value": 100},
        )
        assert resp.status_code == 400
        assert "guess" in resp.json()["detail"].lower()

    async def test_value_clamped(self, client, mock_ai):
        game_id, session, _ = seed_wager_game(current_step_index=1)
        resp = await client.post(
            f"/games/{game_id}/wager-guess",
            json={"player_id": "h1", "question_index": 0, "value": 9999},
        )
        assert resp.status_code == 200
        assert session.state.current_round.wager_questions[0].guesses["h1"] == 100

    async def test_overwrite_allowed(self, client, mock_ai):
        game_id, session, _ = seed_wager_game(current_step_index=1)
        await client.post(
            f"/games/{game_id}/wager-guess",
            json={"player_id": "h1", "question_index": 0, "value": 30},
        )
        resp = await client.post(
            f"/games/{game_id}/wager-guess",
            json={"player_id": "h1", "question_index": 0, "value": 70},
        )
        assert resp.status_code == 200
        assert session.state.current_round.wager_questions[0].guesses["h1"] == 70

    async def test_wrong_sub_round(self, client, mock_ai):
        # step index 2 = bet_0, not guess
        game_id, _, _ = seed_wager_game(current_step_index=2)
        resp = await client.post(
            f"/games/{game_id}/wager-guess",
            json={"player_id": "h1", "question_index": 0, "value": 100},
        )
        assert resp.status_code == 400
        assert "guess" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Wager bet
# ---------------------------------------------------------------------------


class TestWagerBet:
    async def test_success(self, client, mock_ai):
        q = make_wager_question(guesses={"h2": 200})
        game_id, session, _ = seed_wager_game(current_step_index=2, wager_questions=[q])
        resp = await client.post(
            f"/games/{game_id}/wager-bet",
            json={"player_id": "h1", "question_index": 0, "target_player_id": "h2"},
        )
        assert resp.status_code == 200
        assert session.state.current_round.wager_questions[0].bets["h1"] == "h2"

    async def test_self_bet_allowed(self, client, mock_ai):
        q = make_wager_question(guesses={"h1": 200})
        game_id, session, _ = seed_wager_game(current_step_index=2, wager_questions=[q])
        resp = await client.post(
            f"/games/{game_id}/wager-bet",
            json={"player_id": "h1", "question_index": 0, "target_player_id": "h1"},
        )
        assert resp.status_code == 200
        assert session.state.current_round.wager_questions[0].bets["h1"] == "h1"

    async def test_overwrite_allowed(self, client, mock_ai):
        q = make_wager_question(guesses={"h2": 200, "a1": 150})
        game_id, session, _ = seed_wager_game(current_step_index=2, wager_questions=[q])
        await client.post(
            f"/games/{game_id}/wager-bet",
            json={"player_id": "h1", "question_index": 0, "target_player_id": "h2"},
        )
        resp = await client.post(
            f"/games/{game_id}/wager-bet",
            json={"player_id": "h1", "question_index": 0, "target_player_id": "a1"},
        )
        assert resp.status_code == 200
        assert session.state.current_round.wager_questions[0].bets["h1"] == "a1"

    async def test_invalid_target(self, client, mock_ai):
        q = make_wager_question(guesses={"h2": 200})
        game_id, _, _ = seed_wager_game(current_step_index=2, wager_questions=[q])
        resp = await client.post(
            f"/games/{game_id}/wager-bet",
            json={"player_id": "h1", "question_index": 0, "target_player_id": "nonexistent"},
        )
        assert resp.status_code == 400
        assert "target" in resp.json()["detail"].lower()

    async def test_target_has_no_guess(self, client, mock_ai):
        # h2 exists but hasn't guessed
        q = make_wager_question(guesses={"h1": 200})
        game_id, _, _ = seed_wager_game(current_step_index=2, wager_questions=[q])
        resp = await client.post(
            f"/games/{game_id}/wager-bet",
            json={"player_id": "h1", "question_index": 0, "target_player_id": "h2"},
        )
        assert resp.status_code == 400
        assert "no guess" in resp.json()["detail"].lower()

    async def test_wrong_sub_round(self, client, mock_ai):
        # step index 1 = guess_0, not bet
        q = make_wager_question(guesses={"h2": 200})
        game_id, _, _ = seed_wager_game(current_step_index=1, wager_questions=[q])
        resp = await client.post(
            f"/games/{game_id}/wager-bet",
            json={"player_id": "h1", "question_index": 0, "target_player_id": "h2"},
        )
        assert resp.status_code == 400
        assert "bet" in resp.json()["detail"].lower()
