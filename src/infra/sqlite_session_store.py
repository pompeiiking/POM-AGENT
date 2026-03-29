from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable

from core.session.session import Message, Session, SessionStatus
from core.session.session_archive import build_archive_row_dict
from core.session.session_store import SessionStore
from core.session.session_store_ops import append_message_inplace

from .session_json_codec import session_from_json_dict, session_to_json_dict


class SqliteSessionStore(SessionStore):
    """
    会话存储唯一实现：SQLite（文件或 :memory:）。
    - 文件路径：重启可恢复会话；
    - `ephemeral()`：进程内 :memory:，用于测试，无独立「内存 demo 存储」实现。
    """

    def __init__(self, db_path: Path | None = None, *, ephemeral: bool = False) -> None:
        self._lock = threading.Lock()
        if ephemeral:
            self._path = Path(":memory:")
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        else:
            if db_path is None:
                raise ValueError("db_path is required when ephemeral=False")
            self._path = Path(db_path)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._init_schema()

    @classmethod
    def ephemeral(cls) -> SqliteSessionStore:
        """进程内临时库（测试 / 无需落盘场景）。"""
        return cls(ephemeral=True)

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, channel)"
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_archives (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                archived_at TEXT NOT NULL,
                summary_text TEXT NOT NULL,
                message_count INTEGER NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_archives_user ON session_archives(user_id, archived_at DESC)"
        )
        self._conn.commit()
        self._migrate_session_archives_llm_columns()

    def _migrate_session_archives_llm_columns(self) -> None:
        cur = self._conn.execute("PRAGMA table_info(session_archives)")
        cols = {str(row[1]) for row in cur.fetchall()}
        if "llm_summary_text" not in cols:
            self._conn.execute("ALTER TABLE session_archives ADD COLUMN llm_summary_text TEXT")
        if "llm_summary_status" not in cols:
            self._conn.execute("ALTER TABLE session_archives ADD COLUMN llm_summary_status TEXT")
        self._conn.commit()

    def _load_payload(self, session_id: str) -> Session | None:
        cur = self._conn.execute(
            "SELECT payload FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        data = json.loads(row[0])
        return session_from_json_dict(data)

    def _save_payload(self, session: Session) -> None:
        payload = json.dumps(session_to_json_dict(session), ensure_ascii=False, separators=(",", ":"))
        self._conn.execute(
            """
            INSERT INTO sessions (session_id, user_id, channel, payload)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                user_id = excluded.user_id,
                channel = excluded.channel,
                payload = excluded.payload
            """,
            (session.session_id, session.user_id, session.channel, payload),
        )
        self._conn.commit()

    def get_session(self, session_id: str) -> Session | None:
        with self._lock:
            return self._load_payload(session_id)

    def get_sessions_by_user(self, user_id: str, channel: str | None = None) -> Iterable[Session]:
        with self._lock:
            if channel is None:
                cur = self._conn.execute(
                    "SELECT payload FROM sessions WHERE user_id = ?",
                    (user_id,),
                )
            else:
                cur = self._conn.execute(
                    "SELECT payload FROM sessions WHERE user_id = ? AND channel = ?",
                    (user_id, channel),
                )
            for (payload,) in cur.fetchall():
                yield session_from_json_dict(json.loads(payload))

    def create_session(self, session: Session) -> Session:
        with self._lock:
            if self._load_payload(session.session_id) is not None:
                raise ValueError(f"session {session.session_id!r} already exists")
            self._save_payload(session)
            return session

    def save_session(self, session: Session) -> None:
        with self._lock:
            if self._load_payload(session.session_id) is None:
                raise KeyError(f"session {session.session_id!r} not found")
            self._save_payload(session)

    def append_message(self, session_id: str, message: Message) -> Session:
        with self._lock:
            session = self._load_payload(session_id)
            if session is None:
                raise KeyError(f"session {session_id!r} not found")
            append_message_inplace(session, message)
            self._save_payload(session)
            return session

    def set_status(self, session_id: str, status: SessionStatus) -> Session:
        with self._lock:
            session = self._load_payload(session_id)
            if session is None:
                raise KeyError(f"session {session_id!r} not found")
            session.status = status
            self._save_payload(session)
            if status == SessionStatus.ARCHIVED:
                self._upsert_archive_row(session)
            return session

    def _upsert_archive_row(self, session: Session) -> None:
        """会话进入 ARCHIVED 时写入长期表（规则摘要，非 LLM）。"""
        row = build_archive_row_dict(session)
        self._conn.execute(
            """
            INSERT INTO session_archives (session_id, user_id, channel, archived_at, summary_text, message_count)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                user_id = excluded.user_id,
                channel = excluded.channel,
                archived_at = excluded.archived_at,
                summary_text = excluded.summary_text,
                message_count = excluded.message_count
            """,
            (
                row["session_id"],
                row["user_id"],
                row["channel"],
                row["archived_at"],
                row["summary_text"],
                row["message_count"],
            ),
        )
        self._conn.commit()

    def update_archive_llm_summary(self, session_id: str, *, status: str, llm_text: str | None = None) -> None:
        with self._lock:
            if llm_text is None:
                self._conn.execute(
                    "UPDATE session_archives SET llm_summary_status = ? WHERE session_id = ?",
                    (status, session_id),
                )
            else:
                self._conn.execute(
                    """
                    UPDATE session_archives
                    SET llm_summary_status = ?, llm_summary_text = ?
                    WHERE session_id = ?
                    """,
                    (status, llm_text, session_id),
                )
            self._conn.commit()

    def list_archives_for_user(self, user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """按用户列出归档摘要（新在前），供后续 HTTP/检索接入。"""
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT session_id, channel, archived_at, summary_text, message_count,
                       llm_summary_text, llm_summary_status
                FROM session_archives
                WHERE user_id = ?
                ORDER BY archived_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = cur.fetchall()
        return [
            {
                "session_id": r[0],
                "channel": r[1],
                "archived_at": r[2],
                "summary_text": r[3],
                "message_count": r[4],
                "llm_summary_text": r[5],
                "llm_summary_status": r[6],
            }
            for r in rows
        ]

    def delete_session(self, session_id: str) -> bool:
        """
        物理删除会话（DESTROYED 状态后的最终清理）。
        同时删除 sessions 表和 session_archives 表中的记录。
        """
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            deleted_sessions = cur.rowcount > 0
            self._conn.execute(
                "DELETE FROM session_archives WHERE session_id = ?",
                (session_id,),
            )
            self._conn.commit()
            return deleted_sessions
