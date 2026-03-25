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
