from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .rule_summary import build_rule_summary_for_archive
from .session import Session


def build_archive_row_dict(session: Session) -> dict[str, Any]:
    """
    归档表行（写入 `session_archives`；规则摘要，不含 LLM 异步摘要）。
    """
    return {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "channel": session.channel,
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "summary_text": build_rule_summary_for_archive(session),
        "message_count": session.stats.message_count,
    }
