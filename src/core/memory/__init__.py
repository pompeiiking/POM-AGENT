"""长期记忆：保存内容类型与存储协议（见 docs/design/长期记忆定义.md）。"""

from .orchestrator import MemoryOrchestrator
from .policy_config import MemoryPolicyConfig
from .snippets import MemorySnippet
from .content import (
    ArchiveLinkRecord,
    FactRecord,
    LongTermMemoryRecord,
    MemoryChunkRecord,
    MemoryRecordKind,
    TrustLevel,
    UserPreferenceRecord,
)
from .protocol import (
    LongTermMemoryStore,
    MemorySearchHit,
    MemorySearchQuery,
    MemorySearchResult,
    NoopLongTermMemoryStore,
)

__all__ = [
    "MemoryOrchestrator",
    "MemoryPolicyConfig",
    "MemorySnippet",
    "ArchiveLinkRecord",
    "FactRecord",
    "LongTermMemoryRecord",
    "MemoryChunkRecord",
    "MemoryRecordKind",
    "TrustLevel",
    "UserPreferenceRecord",
    "LongTermMemoryStore",
    "MemorySearchHit",
    "MemorySearchQuery",
    "MemorySearchResult",
    "NoopLongTermMemoryStore",
]
