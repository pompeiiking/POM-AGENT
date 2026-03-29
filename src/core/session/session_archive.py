from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .rule_summary import build_rule_summary_for_archive, render_message_plain_text
from .session import Session


def build_dialogue_plain_for_archive(session: Session, *, max_chars: int) -> str:
    """将会话消息压成 role: text 行文本，供归档 LLM 摘要或长期记忆晋升（超长时保留尾部）。"""
    lines: list[str] = []
    for m in session.messages:
        t = render_message_plain_text(m)
        if not t:
            continue
        lines.append(f"{m.role}: {t}")
    s = "\n".join(lines)
    if len(s) <= max_chars:
        return s
    return s[-max_chars:]


def build_archive_row_dict(session: Session) -> dict[str, Any]:
    """
    归档表行（写入 `session_archives` 的 rule 摘要列；LLM 摘要由后台线程写入 llm_* 列）。
    """
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "channel": session.channel,
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "summary_text": build_rule_summary_for_archive(session),
        "message_count": session.stats.message_count,
    }
