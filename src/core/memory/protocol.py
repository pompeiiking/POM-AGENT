from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .content import LongTermMemoryRecord


@dataclass(frozen=True)
class MemorySearchQuery:
    """长期记忆检索请求：实现侧决定向量/BM25/混合策略。"""

    user_id: str
    query_text: str
    channel: str | None = None
    limit: int = 8


@dataclass(frozen=True)
class MemorySearchHit:
    record_id: str
    kind: str
    text: str
    score: float
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class MemorySearchResult:
    hits: tuple[MemorySearchHit, ...]


class LongTermMemoryStore(Protocol):
    """
    旧版长期记忆存储接口（子串 SQLite 等）：**主装配路径不注入**。

    当前主线为 `MemoryOrchestrator` + `DualMemoryStore`（`memory_policy.yaml`）。
    本协议与 `memory_store_registry` 保留供插件、实验与测试；当 `memory_policy.enabled` 时
    `storage_profiles.memory.store_ref` 必须为 `builtin:noop`（见 `resource_validation`）。
    """

    def put(self, record: LongTermMemoryRecord) -> str:
        """写入或更新一条记录，返回稳定 record_id（由实现生成或沿用输入 id）。"""
        ...

    def search(self, query: MemorySearchQuery) -> MemorySearchResult:
        """按用户与查询文本检索；返回有序命中列表。"""
        ...

    def delete_user_data(self, user_id: str) -> None:
        """删除该用户在长期记忆中的数据（合规/注销）；默认实现可为 no-op。"""
        ...


class NoopLongTermMemoryStore:
    """未接入真实引擎时的空实现，保证主链路可启动。"""

    def put(self, record: LongTermMemoryRecord) -> str:
        _ = record
        return "noop"

    def search(self, query: MemorySearchQuery) -> MemorySearchResult:
        _ = query
        return MemorySearchResult(hits=())

    def delete_user_data(self, user_id: str) -> None:
        _ = user_id
