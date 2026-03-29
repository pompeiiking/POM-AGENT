from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class StandardMemoryRow:
    memory_id: str
    kind: str
    user_id: str
    channel: str | None
    body_text: str
    trust: str
    embedding_status: str
    source_session_id: str | None
    tombstone: int
    meta_json: str


class EmbeddingProvider(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]:
        """将文本编码为定长向量（实现可替换为真实嵌入服务）。"""
        ...


class StandardMemoryRepository(Protocol):
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
        ...

    def get_row(self, memory_id: str) -> StandardMemoryRow | None:
        ...

    def set_embedding_status(self, memory_id: str, status: str) -> None:
        ...

    def tombstone_item(self, memory_id: str) -> None:
        ...

    def tombstone_by_phrase(self, user_id: str, phrase: str, *, limit: int) -> int:
        """子串匹配 body_text，批量 tombstone；返回影响行数。"""
        ...

    def fts_search(self, user_id: str, fts_query: str, *, limit: int) -> Sequence[tuple[str, int]]:
        """返回 (memory_id, rank_index) 按相关度顺序。"""
        ...

    def sync_fts_for_memory_id(self, memory_id: str) -> None:
        """插入/更新后同步 FTS 索引行。"""
        ...

    def get_preference_row(self, user_id: str, key: str) -> StandardMemoryRow | None:
        """按 user_id + key 查找非 tombstone 的 preference 行；不存在返回 None。"""
        ...

    def list_preference_rows(self, user_id: str, *, limit: int = 100) -> Sequence[StandardMemoryRow]:
        """列举 user_id 下所有非 tombstone 的 preference 行（按 created_at 降序）。"""
        ...

    def get_fact_row(self, user_id: str, statement_prefix: str) -> StandardMemoryRow | None:
        """按 user_id + body_text 前缀查找非 tombstone 的 fact 行；不存在返回 None。"""
        ...

    def list_fact_rows(self, user_id: str, *, limit: int = 100) -> Sequence[StandardMemoryRow]:
        """列举 user_id 下所有非 tombstone 的 fact 行（按 created_at 降序）。"""
        ...

    def list_active_memory_ids_for_user(self, user_id: str, *, limit: int) -> Sequence[str]:
        """列举 user_id 下非 tombstone 的 memory_id（按 created_at 降序）。"""
        ...

    def purge_tombstoned_rows(self, *, limit: int) -> int:
        """物理删除标准库中已 tombstone 的行（向量与 FTS 已在 tombstone 时清理）；返回删除条数。"""
        ...


class VectorMemoryIndex(Protocol):
    def clear_memory(self, memory_id: str) -> None:
        ...

    def insert_chunk(
        self,
        *,
        chunk_id: str,
        memory_id: str,
        user_id: str,
        chunk_text: str,
        vector: Sequence[float],
    ) -> None:
        ...

    def search_cosine(
        self,
        *,
        user_id: str,
        query_vec: Sequence[float],
        limit: int,
        max_scan: int,
    ) -> Sequence[tuple[str, str, float]]:
        """返回 (chunk_id, memory_id, cosine_score) 降序。"""
        ...


class DualMemoryStore(StandardMemoryRepository, VectorMemoryIndex, Protocol):
    """标准库 + 向量投影 + FTS 的单一后端（如 SqliteDualMemoryStore）。"""

    def row_matches_channel(self, row: StandardMemoryRow, channel: str | None, *, policy: str) -> bool:
        ...
