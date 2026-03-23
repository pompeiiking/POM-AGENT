from __future__ import annotations

from datetime import datetime

from .session import Message, Session


def append_message_inplace(session: Session, message: Message) -> None:
    """追加一条消息并更新统计（内存 / SQLite 共用，避免两处逻辑漂移）。"""
    session.messages.append(message)
    session.stats.message_count += 1
    session.stats.total_tokens_used += message.token_count
    session.stats.last_active_at = datetime.now()
