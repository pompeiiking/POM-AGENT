from __future__ import annotations

from core.session.message_factory import new_message
from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from infra.sqlite_session_store import SqliteSessionStore


def _cfg() -> SessionConfig:
    lim = SessionLimits(
        max_tokens=100,
        max_context_window=100,
        max_loops=10,
        timeout_seconds=60.0,
    )
    return SessionConfig(model="m", skills=[], security="none", limits=lim)


def test_sqlite_ephemeral_list_archives_after_archive() -> None:
    store = SqliteSessionStore.ephemeral()
    sess = Session(
        session_id="sid1",
        user_id="u1",
        channel="cli",
        config=_cfg(),
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[new_message(role="user", content="hello", loop_index=0)],
    )
    store.create_session(sess)
    store.set_status("sid1", SessionStatus.ARCHIVED)
    rows = store.list_archives_for_user("u1", limit=10)
    assert len(rows) == 1
    assert rows[0]["session_id"] == "sid1"
    assert rows[0]["channel"] == "cli"
    assert "概要" in rows[0]["summary_text"] or "对话" in rows[0]["summary_text"]
