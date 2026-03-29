from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Iterable
import uuid

from .session import (
    InvalidSessionTransition,
    Message,
    Session,
    SessionConfig,
    SessionLimits,
    SessionStats,
    SessionStatus,
    validate_session_transition,
)
from .session_store import SessionStore


# 会话管理器抽象
# 按声明顺序分三块：① 查询 ② 创建与写入 ③ 生命周期策略（后续可拆成独立层次）
class SessionManager(ABC):
    def __init__(self, store: SessionStore) -> None:
        self._store = store

    # ---------- ① 查询（只读，无副作用） ----------
    @abstractmethod
    def get_session(self, session_id: str) -> Session | None:
        """按 session_id 取会话，不存在返回 None。"""
        ...

    @abstractmethod
    def find_session_for_user(self, user_id: str, channel: str) -> Session | None:
        """按 user_id + channel 查找已有会话（如 ACTIVE/IDLE），不存在返回 None。用于 get_or_create 的「get」侧。"""
        ...

    @abstractmethod
    def list_sessions(
        self,
        user_id: str | None = None,
        channel: str | None = None,
        status: SessionStatus | None = None,
    ) -> Iterable[Session]:
        """按 user_id（及可选 channel、status）列举会话，不保证排序。"""
        ...

    # ---------- ② 创建与写入（有副作用） ----------
    @abstractmethod
    def create_session(
        self,
        user_id: str,
        channel: str,
        config: SessionConfig,
        session_id: str | None = None,
    ) -> Session:
        """仅创建新会话并写入存储。session_id 为空时由实现方生成。"""
        ...

    @abstractmethod
    def get_or_create_session(
        self,
        user_id: str,
        channel: str,
        config: SessionConfig,
    ) -> Session:
        """先按 user_id+channel 查找已有会话（get）；若无则创建（create）。返回的必为可用 Session。"""
        ...

    @abstractmethod
    def append_message(self, session_id: str, message: Message) -> Session:
        """向会话追加一条消息并更新统计（message_count / total_tokens_used / last_active_at）。"""
        ...

    @abstractmethod
    def update_status(self, session_id: str, new_status: SessionStatus) -> Session:
        """显式把会话状态设为 new_status。状态机合法性由实现方校验。"""
        ...

    # ---------- ③ 生命周期策略（基于时间/规则，可后续拆到独立策略层） ----------
    @abstractmethod
    def mark_idle_if_expired(
        self,
        session_id: str,
        now: datetime | None = None,
    ) -> Session:
        """若距上次活跃已超时，则从 ACTIVE 置为 IDLE；否则不变。超时阈值来自 config.limits 或实现策略。"""
        ...

    @abstractmethod
    def trigger_archive(self, session_id: str) -> Session:
        """将会话标记为 ARCHIVED（归档）。具体归档逻辑（写长期存储等）可由上层或实现方另处实现。"""
        ...

    @abstractmethod
    def trigger_destroy(self, session_id: str, *, physical_delete: bool = False) -> Session | None:
        """
        将会话标记为 DESTROYED（终态）。
        
        Args:
            session_id: 会话 ID
            physical_delete: 若为 True，则在标记 DESTROYED 后物理删除会话数据
        
        Returns:
            若 physical_delete=False，返回更新后的 Session；
            若 physical_delete=True，返回 None（数据已删除）。
        """
        ...

    def list_archives_for_user(self, user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """归档摘要列表（SQLite 后端有数据时非空）。"""
        return self._store.list_archives_for_user(user_id, limit=limit)

    def update_archive_llm_summary(self, session_id: str, *, status: str, llm_text: str | None = None) -> None:
        self._store.update_archive_llm_summary(session_id, status=status, llm_text=llm_text)


def _new_session_id() -> str:
    return uuid.uuid4().hex


def _active_sessions_for_user(sessions: Iterable[Session]) -> list[Session]:
    """仅保留可继续对话的会话（ACTIVE / IDLE），供 get 侧挑选。"""
    return [s for s in sessions if s.status in (SessionStatus.ACTIVE, SessionStatus.IDLE)]


def _matches_status(session: Session, status: SessionStatus | None) -> bool:
    if status is None:
        return True
    return session.status == status


class SessionManagerImpl(SessionManager):
    """
    基于 SessionStore 的会话管理器实现。
    所有会话生命周期逻辑在此完成，仅依赖 Store 抽象，便于将来替换存储后端。
    """

    def __init__(self, store: SessionStore) -> None:
        super().__init__(store)

    def get_session(self, session_id: str) -> Session | None:
        return self._store.get_session(session_id)

    def find_session_for_user(self, user_id: str, channel: str) -> Session | None:
        candidates = _active_sessions_for_user(self._store.get_sessions_by_user(user_id, channel))
        if not candidates:
            return None
        candidates.sort(key=lambda s: s.stats.last_active_at, reverse=True)
        return candidates[0]

    def list_sessions(
        self,
        user_id: str | None = None,
        channel: str | None = None,
        status: SessionStatus | None = None,
    ) -> Iterable[Session]:
        if user_id is None:
            return iter(())
        for session in self._store.get_sessions_by_user(user_id, channel):
            if _matches_status(session, status):
                yield session

    def create_session(
        self,
        user_id: str,
        channel: str,
        config: SessionConfig,
        session_id: str | None = None,
    ) -> Session:
        sid = session_id if session_id is not None else _new_session_id()
        session = Session(
            session_id=sid,
            user_id=user_id,
            channel=channel,
            config=config,
            status=SessionStatus.ACTIVE,
            stats=SessionStats(),
            messages=[],
        )
        self._store.create_session(session)
        return session

    def get_or_create_session(
        self,
        user_id: str,
        channel: str,
        config: SessionConfig,
    ) -> Session:
        existing = self.find_session_for_user(user_id, channel)
        if existing is not None:
            if existing.status == SessionStatus.IDLE:
                return self.update_status(existing.session_id, SessionStatus.ACTIVE)
            return existing
        return self.create_session(user_id, channel, config)

    def append_message(self, session_id: str, message: Message) -> Session:
        return self._store.append_message(session_id, message)

    def update_status(self, session_id: str, new_status: SessionStatus) -> Session:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"session {session_id!r} not found")
        validate_session_transition(session_id, session.status, new_status)
        return self._store.set_status(session_id, new_status)

    def mark_idle_if_expired(
        self,
        session_id: str,
        now: datetime | None = None,
    ) -> Session:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"session {session_id!r} not found")
        if session.status != SessionStatus.ACTIVE:
            return session
        t = now if now is not None else datetime.now()
        timeout_seconds = session.config.limits.timeout_seconds
        if (t - session.stats.last_active_at).total_seconds() >= timeout_seconds:
            return self.update_status(session_id, SessionStatus.IDLE)
        return session

    def trigger_archive(self, session_id: str) -> Session:
        return self.update_status(session_id, SessionStatus.ARCHIVED)

    def trigger_destroy(self, session_id: str, *, physical_delete: bool = False) -> Session | None:
        session = self.update_status(session_id, SessionStatus.DESTROYED)
        if physical_delete:
            self._store.delete_session(session_id)
            return None
        return session
