from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Mapping

TrustLevel = Literal["low", "medium", "high"]

MemoryRecordKind = Literal["chunk", "preference", "fact", "archive_link"]


@dataclass(frozen=True)
class MemoryChunkRecord:
    """
    检索主单元：参与向量/BM25/混合检索的文本块。
    多模态进入长期记忆前须先规范为 text（或摘要）。
    """

    kind: Literal["chunk"] = "chunk"
    user_id: str = ""
    text: str = ""
    channel: str | None = None
    source_session_id: str | None = None
    source_message_id: str | None = None
    trust: TrustLevel = "medium"
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(frozen=True)
class UserPreferenceRecord:
    """跨会话稳定偏好（键值/短文本），可按 user_id 单独读取。"""

    kind: Literal["preference"] = "preference"
    user_id: str = ""
    key: str = ""
    value: str = ""
    updated_at: datetime | None = None


@dataclass(frozen=True)
class FactRecord:
    """抽取事实：便于冲突检测与高置信注入。"""

    kind: Literal["fact"] = "fact"
    user_id: str = ""
    statement: str = ""
    confidence: float = 0.0
    evidence_ref: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArchiveLinkRecord:
    """指向已归档会话的索引项，避免重复存储全量 messages。"""

    kind: Literal["archive_link"] = "archive_link"
    user_id: str = ""
    session_id: str = ""
    archived_at: datetime | None = None
    summary_excerpt: str = ""


LongTermMemoryRecord = MemoryChunkRecord | UserPreferenceRecord | FactRecord | ArchiveLinkRecord
