from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable

from .session import Message, Session, SessionStatus


# 会话存储抽象：实现类仅保留 `infra/SqliteSessionStore`（文件或 ephemeral :memory:），不再维护独立内存 dict 实现。
class SessionStore(ABC):
    @abstractmethod
    def get_session(self, session_id: str) -> Session | None:
        ...

    @abstractmethod
    def get_sessions_by_user(self, user_id: str, channel: str | None = None) -> Iterable[Session]:
        ...

    @abstractmethod
    def create_session(self, session: Session) -> Session:
        ...

    @abstractmethod
    def save_session(self, session: Session) -> None:
        ...

    @abstractmethod
    def append_message(self, session_id: str, message: Message) -> Session:
        ...

    @abstractmethod
    def set_status(self, session_id: str, status: SessionStatus) -> Session:
        ...

    def list_archives_for_user(self, user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """长期归档摘要列表；SQLite 实现覆盖，其余默认空。"""
        return []

    def update_archive_llm_summary(self, session_id: str, *, status: str, llm_text: str | None = None) -> None:
        """归档 LLM 摘要状态；SQLite 实现写入 session_archives.llm_* 列。"""
        return

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """
        物理删除会话（DESTROYED 状态后的最终清理）。
        返回 True 表示删除成功，False 表示会话不存在。
        """
        ...
