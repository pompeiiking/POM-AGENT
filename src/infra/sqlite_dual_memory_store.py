from __future__ import annotations

import math
import sqlite3
import struct
from datetime import datetime, timezone
from threading import Lock
from typing import Sequence

from core.memory.ports import StandardMemoryRow


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pack_vector(vec: Sequence[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack_vector(blob: bytes, dims: int) -> list[float]:
    return list(struct.unpack(f"{dims}f", blob))


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = 0.0
    sa = 0.0
    sb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        sa += x * x
        sb += y * y
    if sa <= 0.0 or sb <= 0.0:
        return 0.0
    return dot / (math.sqrt(sa) * math.sqrt(sb))


class SqliteDualMemoryStore:
    """
    长期记忆双库：标准表 + FTS5 + 向量表（同 SQLite 文件）。
    实现 StandardMemoryRepository 与 VectorMemoryIndex 职责（单类内聚，事务边界清晰）。
    """

    def __init__(self, db_path: str) -> None:
        self._path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = Lock()
        self._init_schema()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_items (
                    memory_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    channel TEXT,
                    body_text TEXT NOT NULL,
                    trust TEXT NOT NULL,
                    embedding_status TEXT NOT NULL,
                    source_session_id TEXT,
                    tombstone INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    meta_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_mem_items_user ON memory_items(user_id, tombstone, created_at DESC);

                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    memory_id UNINDEXED,
                    body_text,
                    tokenize = 'unicode61'
                );

                CREATE TABLE IF NOT EXISTS memory_vectors (
                    chunk_id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    chunk_text TEXT NOT NULL,
                    dims INTEGER NOT NULL,
                    vector BLOB NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memvec_user ON memory_vectors(user_id);
                CREATE INDEX IF NOT EXISTS idx_memvec_mid ON memory_vectors(memory_id);
                """
            )
            self._conn.commit()

    def insert_item(
        self,
        *,
        memory_id: str,
        kind: str,
        user_id: str,
        channel: str | None,
        body_text: str,
        trust: str,
        embedding_status: str,
        source_session_id: str | None,
        meta_json: str,
    ) -> None:
        now = _utc_now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO memory_items (
                    memory_id, kind, user_id, channel, body_text, trust, embedding_status,
                    source_session_id, tombstone, created_at, updated_at, meta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (
                    memory_id,
                    kind,
                    user_id,
                    channel,
                    body_text,
                    trust,
                    embedding_status,
                    source_session_id,
                    now,
                    now,
                    meta_json,
                ),
            )
            self._conn.commit()

    def get_row(self, memory_id: str) -> StandardMemoryRow | None:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT memory_id, kind, user_id, channel, body_text, trust, embedding_status,
                       source_session_id, tombstone, meta_json
                FROM memory_items WHERE memory_id = ?
                """,
                (memory_id,),
            )
            r = cur.fetchone()
        if r is None:
            return None
        return StandardMemoryRow(
            memory_id=str(r["memory_id"]),
            kind=str(r["kind"]),
            user_id=str(r["user_id"]),
            channel=str(r["channel"]) if r["channel"] is not None else None,
            body_text=str(r["body_text"]),
            trust=str(r["trust"]),
            embedding_status=str(r["embedding_status"]),
            source_session_id=str(r["source_session_id"]) if r["source_session_id"] is not None else None,
            tombstone=int(r["tombstone"]),
            meta_json=str(r["meta_json"]),
        )

    def set_embedding_status(self, memory_id: str, status: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE memory_items SET embedding_status = ?, updated_at = ? WHERE memory_id = ?",
                (status, _utc_now_iso(), memory_id),
            )
            self._conn.commit()

    def tombstone_item(self, memory_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE memory_items SET tombstone = 1, updated_at = ? WHERE memory_id = ?",
                (_utc_now_iso(), memory_id),
            )
            self._conn.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
            self._conn.execute("DELETE FROM memory_vectors WHERE memory_id = ?", (memory_id,))
            self._conn.commit()

    def tombstone_by_phrase(self, user_id: str, phrase: str, *, limit: int) -> int:
        if not phrase.strip():
            return 0
        like = f"%{phrase.strip()}%"
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT memory_id FROM memory_items
                WHERE user_id = ? AND tombstone = 0 AND body_text LIKE ?
                LIMIT ?
                """,
                (user_id, like, limit),
            )
            ids = [str(r[0]) for r in cur.fetchall()]
            for mid in ids:
                self._conn.execute(
                    "UPDATE memory_items SET tombstone = 1, updated_at = ? WHERE memory_id = ?",
                    (_utc_now_iso(), mid),
                )
                self._conn.execute("DELETE FROM memory_fts WHERE memory_id = ?", (mid,))
                self._conn.execute("DELETE FROM memory_vectors WHERE memory_id = ?", (mid,))
            self._conn.commit()
        return len(ids)

    def sync_fts_for_memory_id(self, memory_id: str) -> None:
        with self._lock:
            cur = self._conn.execute(
                "SELECT body_text FROM memory_items WHERE memory_id = ? AND tombstone = 0",
                (memory_id,),
            )
            row = cur.fetchone()
            self._conn.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))
            if row is not None:
                self._conn.execute(
                    "INSERT INTO memory_fts (memory_id, body_text) VALUES (?, ?)",
                    (memory_id, str(row["body_text"])),
                )
            self._conn.commit()

    def fts_search(self, user_id: str, fts_query: str, *, limit: int) -> list[tuple[str, int]]:
        if not fts_query.strip():
            return []
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT memory_fts.memory_id
                FROM memory_fts
                INNER JOIN memory_items m ON m.memory_id = memory_fts.memory_id
                WHERE memory_fts MATCH ? AND m.user_id = ? AND m.tombstone = 0
                LIMIT ?
                """,
                (fts_query, user_id, limit),
            )
            rows = cur.fetchall()
        out: list[tuple[str, int]] = []
        for rank, r in enumerate(rows):
            out.append((str(r["memory_id"]), rank))
        return out

    def clear_memory(self, memory_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM memory_vectors WHERE memory_id = ?", (memory_id,))
            self._conn.commit()

    def insert_chunk(
        self,
        *,
        chunk_id: str,
        memory_id: str,
        user_id: str,
        chunk_text: str,
        vector: Sequence[float],
    ) -> None:
        blob = _pack_vector(vector)
        dims = len(vector)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO memory_vectors (chunk_id, memory_id, user_id, chunk_text, dims, vector)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chunk_id, memory_id, user_id, chunk_text, dims, blob),
            )
            self._conn.commit()

    def search_cosine(
        self,
        *,
        user_id: str,
        query_vec: Sequence[float],
        limit: int,
        max_scan: int,
    ) -> list[tuple[str, str, float]]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT chunk_id, memory_id, dims, vector
                FROM memory_vectors
                WHERE user_id = ?
                LIMIT ?
                """,
                (user_id, max_scan),
            )
            rows = cur.fetchall()
        scored: list[tuple[str, str, float]] = []
        for r in rows:
            dims = int(r["dims"])
            vec = _unpack_vector(bytes(r["vector"]), dims)
            s = _cosine(query_vec, vec)
            scored.append((str(r["chunk_id"]), str(r["memory_id"]), s))
        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[:limit]

    def list_active_memory_ids_for_user(self, user_id: str, *, limit: int) -> list[str]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT memory_id FROM memory_items
                WHERE user_id = ? AND tombstone = 0
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            return [str(r[0]) for r in cur.fetchall()]

    def purge_tombstoned_rows(self, *, limit: int) -> int:
        if limit <= 0:
            return 0
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT memory_id FROM memory_items
                WHERE tombstone = 1
                LIMIT ?
                """,
                (limit,),
            )
            ids = [str(r[0]) for r in cur.fetchall()]
            for mid in ids:
                self._conn.execute("DELETE FROM memory_items WHERE memory_id = ?", (mid,))
            self._conn.commit()
        return len(ids)

    def get_preference_row(self, user_id: str, key: str) -> StandardMemoryRow | None:
        body_prefix = f"{key}="
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT memory_id, kind, user_id, channel, body_text, trust, embedding_status,
                       source_session_id, tombstone, meta_json
                FROM memory_items
                WHERE user_id = ? AND kind = 'preference' AND tombstone = 0
                      AND body_text LIKE ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (user_id, body_prefix + "%"),
            )
            r = cur.fetchone()
        if r is None:
            return None
        return StandardMemoryRow(
            memory_id=str(r["memory_id"]),
            kind=str(r["kind"]),
            user_id=str(r["user_id"]),
            channel=str(r["channel"]) if r["channel"] is not None else None,
            body_text=str(r["body_text"]),
            trust=str(r["trust"]),
            embedding_status=str(r["embedding_status"]),
            source_session_id=str(r["source_session_id"]) if r["source_session_id"] is not None else None,
            tombstone=int(r["tombstone"]),
            meta_json=str(r["meta_json"]),
        )

    def list_preference_rows(self, user_id: str, *, limit: int = 100) -> list[StandardMemoryRow]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT memory_id, kind, user_id, channel, body_text, trust, embedding_status,
                       source_session_id, tombstone, meta_json
                FROM memory_items
                WHERE user_id = ? AND kind = 'preference' AND tombstone = 0
                ORDER BY created_at DESC LIMIT ?
                """,
                (user_id, limit),
            )
            rows = cur.fetchall()
        return [
            StandardMemoryRow(
                memory_id=str(r["memory_id"]),
                kind=str(r["kind"]),
                user_id=str(r["user_id"]),
                channel=str(r["channel"]) if r["channel"] is not None else None,
                body_text=str(r["body_text"]),
                trust=str(r["trust"]),
                embedding_status=str(r["embedding_status"]),
                source_session_id=str(r["source_session_id"]) if r["source_session_id"] is not None else None,
                tombstone=int(r["tombstone"]),
                meta_json=str(r["meta_json"]),
            )
            for r in rows
        ]

    def get_fact_row(self, user_id: str, statement_prefix: str) -> StandardMemoryRow | None:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT memory_id, kind, user_id, channel, body_text, trust, embedding_status,
                       source_session_id, tombstone, meta_json
                FROM memory_items
                WHERE user_id = ? AND kind = 'fact' AND tombstone = 0
                      AND body_text LIKE ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (user_id, statement_prefix + "%"),
            )
            r = cur.fetchone()
        if r is None:
            return None
        return StandardMemoryRow(
            memory_id=str(r["memory_id"]),
            kind=str(r["kind"]),
            user_id=str(r["user_id"]),
            channel=str(r["channel"]) if r["channel"] is not None else None,
            body_text=str(r["body_text"]),
            trust=str(r["trust"]),
            embedding_status=str(r["embedding_status"]),
            source_session_id=str(r["source_session_id"]) if r["source_session_id"] is not None else None,
            tombstone=int(r["tombstone"]),
            meta_json=str(r["meta_json"]),
        )

    def list_fact_rows(self, user_id: str, *, limit: int = 100) -> list[StandardMemoryRow]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT memory_id, kind, user_id, channel, body_text, trust, embedding_status,
                       source_session_id, tombstone, meta_json
                FROM memory_items
                WHERE user_id = ? AND kind = 'fact' AND tombstone = 0
                ORDER BY created_at DESC LIMIT ?
                """,
                (user_id, limit),
            )
            rows = cur.fetchall()
        return [
            StandardMemoryRow(
                memory_id=str(r["memory_id"]),
                kind=str(r["kind"]),
                user_id=str(r["user_id"]),
                channel=str(r["channel"]) if r["channel"] is not None else None,
                body_text=str(r["body_text"]),
                trust=str(r["trust"]),
                embedding_status=str(r["embedding_status"]),
                source_session_id=str(r["source_session_id"]) if r["source_session_id"] is not None else None,
                tombstone=int(r["tombstone"]),
                meta_json=str(r["meta_json"]),
            )
            for r in rows
        ]

    def row_matches_channel(self, row: StandardMemoryRow, channel: str | None, *, policy: str) -> bool:
        if policy != "match_or_global":
            return True
        if row.channel is None or row.channel == "":
            return True
        return channel is not None and row.channel == channel
