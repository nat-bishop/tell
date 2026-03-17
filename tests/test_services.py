"""Tests for service classes — ConnectionManager, GameRepository, TimerManager."""

from __future__ import annotations

import asyncio

from backend.services.connection_manager import ConnectionManager
from backend.services.game_repository import GameRepository, TellGameSession
from backend.services.timer_manager import TimerManager
from schemas.api_models import PlayerJoinedEvent
from schemas.game_state import TellGameState

# ---------------------------------------------------------------------------
# ConnectionManager
# ---------------------------------------------------------------------------


class TestConnectionManager:
    def test_connect_creates_queue(self):
        cm = ConnectionManager()
        queue = cm.connect("g1", "p1")
        assert queue is not None
        assert "p1" in cm.get_connected_players("g1")

    def test_disconnect_removes_player(self):
        cm = ConnectionManager()
        cm.connect("g1", "p1")
        cm.disconnect("g1", "p1")
        assert "p1" not in cm.get_connected_players("g1")

    def test_disconnect_nonexistent_game(self):
        cm = ConnectionManager()
        cm.disconnect("nonexistent", "p1")  # no error

    async def test_broadcast_sends_to_all(self):
        cm = ConnectionManager()
        q1 = cm.connect("g1", "p1")
        q2 = cm.connect("g1", "p2")
        event = PlayerJoinedEvent(seq=1, player_id="p1", alias="UNIT-01", player_count=1)
        await cm.broadcast("g1", event)
        assert q1.get_nowait() == event
        assert q2.get_nowait() == event

    async def test_broadcast_does_not_cross_games(self):
        cm = ConnectionManager()
        q1 = cm.connect("g1", "p1")
        q2 = cm.connect("g2", "p2")
        event = PlayerJoinedEvent(seq=1, player_id="p1", alias="UNIT-01", player_count=1)
        await cm.broadcast("g1", event)
        assert q2.empty() is not False  # q2 should be empty
        assert q1.get_nowait() == event
        assert q2.empty()

    async def test_send_to_specific_player(self):
        cm = ConnectionManager()
        q1 = cm.connect("g1", "p1")
        q2 = cm.connect("g1", "p2")
        event = PlayerJoinedEvent(seq=1, player_id="p1", alias="UNIT-01", player_count=1)
        await cm.send_to("g1", "p1", event)
        assert q1.get_nowait() == event
        assert q2.empty()

    async def test_event_log_replay(self):
        cm = ConnectionManager()
        cm.connect("g1", "p1")
        e1 = PlayerJoinedEvent(seq=1, player_id="p1", alias="UNIT-01", player_count=1)
        e2 = PlayerJoinedEvent(seq=2, player_id="p2", alias="BOT-42", player_count=2)
        await cm.broadcast("g1", e1)
        await cm.broadcast("g1", e2)

        events = cm.get_events_after("g1", 0)
        assert events is not None
        assert len(events) == 2

        events_after_1 = cm.get_events_after("g1", 1)
        assert events_after_1 is not None
        assert len(events_after_1) == 1
        assert events_after_1[0].seq == 2

    def test_get_events_after_unknown_game(self):
        cm = ConnectionManager()
        assert cm.get_events_after("nonexistent", 0) is None

    async def test_pop_recording(self):
        cm = ConnectionManager()
        cm.connect("g1", "p1")
        event = PlayerJoinedEvent(seq=1, player_id="p1", alias="UNIT-01", player_count=1)
        await cm.broadcast("g1", event)

        recording = cm.pop_recording("g1")
        assert len(recording) == 1
        assert recording[0] == event

        # Second pop should be empty
        assert cm.pop_recording("g1") == []

    def test_cleanup_game(self):
        cm = ConnectionManager()
        cm.connect("g1", "p1")
        cm.cleanup_game("g1")
        assert cm.get_connected_players("g1") == set()
        assert cm.get_events_after("g1", 0) is None

    def test_get_lock_creates_lock(self):
        cm = ConnectionManager()
        lock = cm.get_lock("g1")
        assert isinstance(lock, asyncio.Lock)
        # Same lock returned on second call
        assert cm.get_lock("g1") is lock


# ---------------------------------------------------------------------------
# GameRepository
# ---------------------------------------------------------------------------


class TestGameRepository:
    def test_create_and_get(self):
        repo = GameRepository()
        state = TellGameState(game_id="g1")
        session = repo.create(state)
        assert isinstance(session, TellGameSession)
        assert repo.get("g1") is session

    def test_get_nonexistent(self):
        repo = GameRepository()
        assert repo.get("nonexistent") is None

    def test_session_next_seq(self):
        repo = GameRepository()
        state = TellGameState(game_id="g1")
        session = repo.create(state)
        assert session.next_seq() == 1
        assert session.next_seq() == 2
        assert session.next_seq() == 3


# ---------------------------------------------------------------------------
# TimerManager
# ---------------------------------------------------------------------------


class TestTimerManager:
    async def test_timer_fires_callback(self):
        tm = TimerManager()
        called = asyncio.Event()

        async def cb():
            called.set()

        tm.start_timer("g1", 0, cb)  # 0 second = immediate
        await asyncio.wait_for(called.wait(), timeout=2.0)
        assert called.is_set()

    async def test_cancel_prevents_callback(self):
        tm = TimerManager()
        called = False

        async def cb():
            nonlocal called
            called = True

        tm.start_timer("g1", 10, cb)
        tm.cancel_timer("g1")
        await asyncio.sleep(0.05)
        assert not called

    async def test_new_timer_cancels_old(self):
        tm = TimerManager()
        first_called = False
        second_called = asyncio.Event()

        async def cb1():
            nonlocal first_called
            first_called = True

        async def cb2():
            second_called.set()

        tm.start_timer("g1", 10, cb1)
        tm.start_timer("g1", 0, cb2)
        await asyncio.wait_for(second_called.wait(), timeout=2.0)
        assert not first_called
        assert second_called.is_set()

    def test_cancel_nonexistent(self):
        tm = TimerManager()
        tm.cancel_timer("nonexistent")  # no error

    async def test_cleanup_game(self):
        tm = TimerManager()

        async def cb():
            pass

        tm.start_timer("g1", 10, cb)
        tm.cleanup_game("g1")
        # Timer should be cancelled (no way to verify directly, just no error)
