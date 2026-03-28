"""Session DESTROYED 状态与清理机制测试"""

from __future__ import annotations

import pytest

from core.session.session import (
    InvalidSessionTransition,
    Session,
    SessionConfig,
    SessionLimits,
    SessionStats,
    SessionStatus,
)
from core.session.session_manager import SessionManagerImpl
from infra.sqlite_session_store import SqliteSessionStore


def _make_config() -> SessionConfig:
    limits = SessionLimits(
        max_tokens=1000,
        max_context_window=1000,
        max_loops=5,
        timeout_seconds=300.0,
    )
    return SessionConfig(model="stub", skills=[], security="none", limits=limits)


class TestSessionDestroyTransitions:
    """测试 DESTROYED 状态转换"""

    def test_active_to_destroyed(self) -> None:
        store = SqliteSessionStore.ephemeral()
        manager = SessionManagerImpl(store)
        session = manager.create_session("user1", "cli", _make_config())
        assert session.status == SessionStatus.ACTIVE

        destroyed = manager.trigger_destroy(session.session_id)
        assert destroyed is not None
        assert destroyed.status == SessionStatus.DESTROYED

    def test_idle_to_destroyed(self) -> None:
        store = SqliteSessionStore.ephemeral()
        manager = SessionManagerImpl(store)
        session = manager.create_session("user1", "cli", _make_config())
        manager.update_status(session.session_id, SessionStatus.IDLE)

        destroyed = manager.trigger_destroy(session.session_id)
        assert destroyed is not None
        assert destroyed.status == SessionStatus.DESTROYED

    def test_archived_to_destroyed(self) -> None:
        store = SqliteSessionStore.ephemeral()
        manager = SessionManagerImpl(store)
        session = manager.create_session("user1", "cli", _make_config())
        manager.trigger_archive(session.session_id)

        destroyed = manager.trigger_destroy(session.session_id)
        assert destroyed is not None
        assert destroyed.status == SessionStatus.DESTROYED

    def test_destroyed_is_terminal(self) -> None:
        store = SqliteSessionStore.ephemeral()
        manager = SessionManagerImpl(store)
        session = manager.create_session("user1", "cli", _make_config())
        manager.trigger_destroy(session.session_id)

        with pytest.raises(InvalidSessionTransition):
            manager.update_status(session.session_id, SessionStatus.ACTIVE)

        with pytest.raises(InvalidSessionTransition):
            manager.update_status(session.session_id, SessionStatus.IDLE)

        with pytest.raises(InvalidSessionTransition):
            manager.update_status(session.session_id, SessionStatus.ARCHIVED)


class TestSessionPhysicalDelete:
    """测试物理删除功能"""

    def test_physical_delete_removes_session(self) -> None:
        store = SqliteSessionStore.ephemeral()
        manager = SessionManagerImpl(store)
        session = manager.create_session("user1", "cli", _make_config())
        session_id = session.session_id

        result = manager.trigger_destroy(session_id, physical_delete=True)
        assert result is None

        retrieved = manager.get_session(session_id)
        assert retrieved is None

    def test_physical_delete_removes_archive(self) -> None:
        store = SqliteSessionStore.ephemeral()
        manager = SessionManagerImpl(store)
        session = manager.create_session("user1", "cli", _make_config())
        session_id = session.session_id

        manager.trigger_archive(session_id)
        archives_before = manager.list_archives_for_user("user1")
        assert len(archives_before) == 1

        manager.trigger_destroy(session_id, physical_delete=True)

        archives_after = manager.list_archives_for_user("user1")
        assert len(archives_after) == 0

    def test_delete_nonexistent_session(self) -> None:
        store = SqliteSessionStore.ephemeral()
        result = store.delete_session("nonexistent")
        assert result is False


class TestSessionStoreDeleteSession:
    """测试 SessionStore.delete_session"""

    def test_delete_existing_session(self) -> None:
        store = SqliteSessionStore.ephemeral()
        limits = SessionLimits(
            max_tokens=1000,
            max_context_window=1000,
            max_loops=5,
            timeout_seconds=300.0,
        )
        config = SessionConfig(model="stub", skills=[], security="none", limits=limits)
        session = Session(
            session_id="test-session",
            user_id="user1",
            channel="cli",
            config=config,
            status=SessionStatus.ACTIVE,
            stats=SessionStats(),
            messages=[],
        )
        store.create_session(session)

        assert store.get_session("test-session") is not None

        result = store.delete_session("test-session")
        assert result is True

        assert store.get_session("test-session") is None

    def test_delete_with_archive(self) -> None:
        store = SqliteSessionStore.ephemeral()
        limits = SessionLimits(
            max_tokens=1000,
            max_context_window=1000,
            max_loops=5,
            timeout_seconds=300.0,
        )
        config = SessionConfig(model="stub", skills=[], security="none", limits=limits)
        session = Session(
            session_id="test-session",
            user_id="user1",
            channel="cli",
            config=config,
            status=SessionStatus.ACTIVE,
            stats=SessionStats(),
            messages=[],
        )
        store.create_session(session)
        store.set_status("test-session", SessionStatus.ARCHIVED)

        archives = store.list_archives_for_user("user1")
        assert len(archives) == 1

        store.delete_session("test-session")

        archives = store.list_archives_for_user("user1")
        assert len(archives) == 0
