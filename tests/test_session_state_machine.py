"""Session 状态机：转换校验 + SessionManagerImpl 行为测试。"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from core.session.session import (
    InvalidSessionTransition,
    Session,
    SessionConfig,
    SessionLimits,
    SessionStats,
    SessionStatus,
    _VALID_TRANSITIONS,
    validate_session_transition,
)
from core.session.session_manager import SessionManagerImpl
from core.session.message_factory import new_message
from infra.sqlite_session_store import SqliteSessionStore


# ── helpers ──

def _limits() -> SessionLimits:
    return SessionLimits(max_tokens=4096, max_context_window=4096, max_loops=10, timeout_seconds=300)


def _config() -> SessionConfig:
    return SessionConfig(model="stub", skills=[], security="baseline", limits=_limits())


def _manager() -> SessionManagerImpl:
    store = SqliteSessionStore.ephemeral()
    return SessionManagerImpl(store)


# ════════════════════════════════════════════════
# 1. validate_session_transition 单元测试
# ════════════════════════════════════════════════

class TestValidateSessionTransition:
    """纯函数级别：校验 _VALID_TRANSITIONS 表。"""

    @pytest.mark.parametrize("src,dst", list(_VALID_TRANSITIONS))
    def test_valid_transitions_pass(self, src: SessionStatus, dst: SessionStatus) -> None:
        validate_session_transition("sid-ok", src, dst)

    def test_same_status_is_noop(self) -> None:
        for s in SessionStatus:
            validate_session_transition("sid-noop", s, s)

    @pytest.mark.parametrize(
        "src,dst",
        [
            (SessionStatus.ARCHIVED, SessionStatus.ACTIVE),
            (SessionStatus.ARCHIVED, SessionStatus.IDLE),
            (SessionStatus.DESTROYED, SessionStatus.ACTIVE),
            (SessionStatus.DESTROYED, SessionStatus.IDLE),
            (SessionStatus.DESTROYED, SessionStatus.ARCHIVED),
        ],
    )
    def test_invalid_transitions_raise(self, src: SessionStatus, dst: SessionStatus) -> None:
        with pytest.raises(InvalidSessionTransition) as exc_info:
            validate_session_transition("sid-bad", src, dst)
        err = exc_info.value
        assert err.session_id == "sid-bad"
        assert err.current == src
        assert err.target == dst

    def test_destroyed_is_terminal(self) -> None:
        for dst in SessionStatus:
            if dst == SessionStatus.DESTROYED:
                continue
            with pytest.raises(InvalidSessionTransition):
                validate_session_transition("sid-term", SessionStatus.DESTROYED, dst)


# ════════════════════════════════════════════════
# 2. SessionManagerImpl 状态机集成测试
# ════════════════════════════════════════════════

class TestSessionManagerStateMachine:
    """通过 SqliteSessionStore.ephemeral 验证 Manager 层状态机行为。"""

    def test_active_to_idle(self) -> None:
        mgr = _manager()
        s = mgr.create_session("u1", "cli", _config())
        assert s.status == SessionStatus.ACTIVE
        s2 = mgr.update_status(s.session_id, SessionStatus.IDLE)
        assert s2.status == SessionStatus.IDLE

    def test_active_to_archived(self) -> None:
        mgr = _manager()
        s = mgr.create_session("u1", "cli", _config())
        s2 = mgr.trigger_archive(s.session_id)
        assert s2.status == SessionStatus.ARCHIVED

    def test_idle_to_active(self) -> None:
        mgr = _manager()
        s = mgr.create_session("u1", "cli", _config())
        mgr.update_status(s.session_id, SessionStatus.IDLE)
        s3 = mgr.update_status(s.session_id, SessionStatus.ACTIVE)
        assert s3.status == SessionStatus.ACTIVE

    def test_idle_to_archived(self) -> None:
        mgr = _manager()
        s = mgr.create_session("u1", "cli", _config())
        mgr.update_status(s.session_id, SessionStatus.IDLE)
        s3 = mgr.update_status(s.session_id, SessionStatus.ARCHIVED)
        assert s3.status == SessionStatus.ARCHIVED

    def test_archived_to_active_raises(self) -> None:
        mgr = _manager()
        s = mgr.create_session("u1", "cli", _config())
        mgr.trigger_archive(s.session_id)
        with pytest.raises(InvalidSessionTransition):
            mgr.update_status(s.session_id, SessionStatus.ACTIVE)

    def test_archived_to_destroyed(self) -> None:
        mgr = _manager()
        s = mgr.create_session("u1", "cli", _config())
        mgr.trigger_archive(s.session_id)
        s3 = mgr.update_status(s.session_id, SessionStatus.DESTROYED)
        assert s3.status == SessionStatus.DESTROYED

    def test_destroyed_to_any_raises(self) -> None:
        mgr = _manager()
        s = mgr.create_session("u1", "cli", _config())
        mgr.update_status(s.session_id, SessionStatus.ARCHIVED)
        mgr.update_status(s.session_id, SessionStatus.DESTROYED)
        for target in (SessionStatus.ACTIVE, SessionStatus.IDLE, SessionStatus.ARCHIVED):
            with pytest.raises(InvalidSessionTransition):
                mgr.update_status(s.session_id, target)

    def test_update_status_nonexistent_raises_key_error(self) -> None:
        mgr = _manager()
        with pytest.raises(KeyError):
            mgr.update_status("nonexistent-id", SessionStatus.IDLE)


# ════════════════════════════════════════════════
# 3. get_or_create_session: IDLE 自动重激活
# ════════════════════════════════════════════════

class TestGetOrCreateReactivation:

    def test_idle_session_reactivated_on_get_or_create(self) -> None:
        mgr = _manager()
        cfg = _config()
        s1 = mgr.create_session("u1", "cli", cfg)
        mgr.update_status(s1.session_id, SessionStatus.IDLE)
        s2 = mgr.get_or_create_session("u1", "cli", cfg)
        assert s2.session_id == s1.session_id
        assert s2.status == SessionStatus.ACTIVE

    def test_active_session_returned_unchanged(self) -> None:
        mgr = _manager()
        cfg = _config()
        s1 = mgr.create_session("u1", "cli", cfg)
        s2 = mgr.get_or_create_session("u1", "cli", cfg)
        assert s2.session_id == s1.session_id
        assert s2.status == SessionStatus.ACTIVE

    def test_no_session_creates_new(self) -> None:
        mgr = _manager()
        cfg = _config()
        s = mgr.get_or_create_session("u1", "cli", cfg)
        assert s.status == SessionStatus.ACTIVE
        assert s.user_id == "u1"


# ════════════════════════════════════════════════
# 4. mark_idle_if_expired 集成
# ════════════════════════════════════════════════

class TestMarkIdleIfExpired:

    def test_expired_active_becomes_idle(self) -> None:
        mgr = _manager()
        cfg = _config()
        s = mgr.create_session("u1", "cli", cfg)
        future = datetime.now() + timedelta(seconds=cfg.limits.timeout_seconds + 1)
        s2 = mgr.mark_idle_if_expired(s.session_id, now=future)
        assert s2.status == SessionStatus.IDLE

    def test_not_expired_stays_active(self) -> None:
        mgr = _manager()
        cfg = _config()
        s = mgr.create_session("u1", "cli", cfg)
        s2 = mgr.mark_idle_if_expired(s.session_id, now=datetime.now())
        assert s2.status == SessionStatus.ACTIVE

    def test_idle_session_stays_idle(self) -> None:
        mgr = _manager()
        cfg = _config()
        s = mgr.create_session("u1", "cli", cfg)
        mgr.update_status(s.session_id, SessionStatus.IDLE)
        s2 = mgr.mark_idle_if_expired(s.session_id, now=datetime.now() + timedelta(hours=1))
        assert s2.status == SessionStatus.IDLE
