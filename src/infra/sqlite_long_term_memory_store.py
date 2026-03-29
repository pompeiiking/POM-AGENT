from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from core.memory.content import (
    ArchiveLinkRecord,
    FactRecord,
    LongTermMemoryRecord,
    MemoryChunkRecord,
    UserPreferenceRecord,
)
from core.memory.protocol import MemorySearchHit, MemorySearchQuery, MemorySearchResult


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError


def _searchable_text(record: LongTermMemoryRecord) -> str:
    if isinstance(record, MemoryChunkRecord):
        return record.text
    if isinstance(record, UserPreferenceRecord):
        return f"{record.key}={record.value}"
    if isinstance(record, FactRecord):
        return record.statement
    if isinstance(record, ArchiveLinkRecord):
        return f"{record.summary_excerpt}\n{record.session_id}"
    raise TypeError(f"unknown record: {type(record)!r}")


def _user_id(record: LongTermMemoryRecord) -> str:
    return record.user_id


class SqliteLongTermMemoryStore:
    """
    长期记忆 SQLite 实现：统一表 + LIKE 检索（向量/BM25 可由 entrypoint 插件替换）。
    """

    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ltm_records (
                    record_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    meta_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ltm_user ON ltm_records(user_id)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ltm_user_created ON ltm_records(user_id, created_at DESC)"
            )
            self._conn.commit()

    def put(self, record: LongTermMemoryRecord) -> str:
        rid = uuid.uuid4().hex
        uid = _user_id(record)
        blob = json.dumps(asdict(record), ensure_ascii=False, default=_json_default)
        text = _searchable_text(record)
        created = datetime.now(timezone.utc).isoformat()
        kind = record.kind
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO ltm_records (record_id, kind, user_id, text, meta_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (rid, kind, uid, text, blob, created),
            )
            self._conn.commit()
        return rid

    def search(self, query: MemorySearchQuery) -> MemorySearchResult:
        needle = query.query_text.strip().lower()
        if not needle:
            return MemorySearchResult(hits=())
        uid = query.user_id
        lim = max(1, min(query.limit, 100))
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT record_id, kind, text, meta_json
                FROM ltm_records
                WHERE user_id = ? AND instr(lower(text), ?) > 0
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (uid, needle, lim),
            )
            rows = cur.fetchall()
        hits: list[MemorySearchHit] = []
        for i, row in enumerate(rows):
            meta = json.loads(row["meta_json"])
            score = 1.0 / (1.0 + float(i))
            hits.append(
                MemorySearchHit(
                    record_id=str(row["record_id"]),
                    kind=str(row["kind"]),
                    text=str(row["text"]),
                    score=score,
                    metadata=meta,
                )
            )
        return MemorySearchResult(hits=tuple(hits))

    def delete_user_data(self, user_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM ltm_records WHERE user_id = ?", (user_id,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
