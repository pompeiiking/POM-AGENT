from __future__ import annotations

from pathlib import Path

from app.config_loaders.resource_access_loader import ResourceAccessSource, load_resource_access_registry
from core.agent_types import AgentRequest
from core.memory.content import MemoryChunkRecord
from core.memory.orchestrator import MemoryOrchestrator
from core.memory.policy_config import MemoryPolicyConfig
from core.resource_access import (
    RESOURCE_LONG_TERM_MEMORY,
    ResourceAccessEvaluator,
    ResourceAccessProfile,
    ResourceAccessRule,
)
from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from infra.sqlite_dual_memory_store import SqliteDualMemoryStore
from core.memory.embedding_hash import HashEmbeddingProvider
from modules.assembly.impl import AssemblyModuleImpl
from core.user_intent import Chat


def _policy() -> MemoryPolicyConfig:
    return MemoryPolicyConfig(
        enabled=True,
        retrieve_top_k=4,
        rrf_k=60,
        rerank_enabled=False,
        rerank_max_candidates=8,
        chunk_max_chars=128,
        chunk_overlap_chars=16,
        promote_on_archive=False,
        archive_chunk_max_chars=1000,
        archive_trust="medium",
        embedding_async=False,
        embedding_dim=32,
        fts_enabled=True,
        vector_max_candidates=50,
        channel_filter="any",
        dual_store_ref="builtin:dual_sqlite",
        embedding_ref="builtin:hash",
        embedding_openai=None,
    )


def test_evaluator_unknown_resource_allows() -> None:
    ev = ResourceAccessEvaluator(ResourceAccessProfile(rules={}))
    assert ev.is_allowed("anything", "read") is True


def test_assembly_skips_memory_when_read_denied(tmp_path) -> None:
    db = tmp_path / "m.db"
    store = SqliteDualMemoryStore(str(db))
    orch = MemoryOrchestrator(store, HashEmbeddingProvider(dim=32), _policy())
    orch.ingest_record(
        MemoryChunkRecord(
            user_id="u1",
            text="secret fact",
            channel="c1",
        )
    )
    orch.flush_embedding_queue()
    profile = ResourceAccessProfile(
        rules={RESOURCE_LONG_TERM_MEMORY: ResourceAccessRule(read="deny", write="allow")}
    )
    asm = AssemblyModuleImpl(memory_orchestrator=orch, resource_access=ResourceAccessEvaluator(profile))
    lim = SessionLimits(100, 100, 3, 60.0)
    session = Session(
        session_id="s1",
        user_id="u1",
        channel="c1",
        config=SessionConfig("stub", [], "none", lim),
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[],
    )
    req = AgentRequest("r1", "u1", "c1", "hello", intent=Chat(text="secret"))
    ctx = asm.build_initial_context(session, req)
    assert ctx.memory_context_block is None
    store.close()


def test_assembly_includes_memory_when_read_allowed(tmp_path) -> None:
    db = tmp_path / "m2.db"
    store = SqliteDualMemoryStore(str(db))
    orch = MemoryOrchestrator(store, HashEmbeddingProvider(dim=32), _policy())
    orch.ingest_record(MemoryChunkRecord(user_id="u1", text="coffee lover", channel="c1"))
    orch.flush_embedding_queue()
    profile = ResourceAccessProfile(
        rules={RESOURCE_LONG_TERM_MEMORY: ResourceAccessRule(read="allow", write="allow")}
    )
    asm = AssemblyModuleImpl(memory_orchestrator=orch, resource_access=ResourceAccessEvaluator(profile))
    lim = SessionLimits(100, 100, 3, 60.0)
    session = Session(
        session_id="s2",
        user_id="u1",
        channel="c1",
        config=SessionConfig("stub", [], "none", lim),
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[],
    )
    req = AgentRequest("r2", "u1", "c1", "x", intent=Chat(text="coffee"))
    ctx = asm.build_initial_context(session, req)
    assert ctx.memory_context_block is not None
    assert "coffee" in ctx.memory_context_block
    store.close()


def test_resource_access_loader_roundtrip(tmp_path) -> None:
    p = tmp_path / "ra.yaml"
    p.write_text(
        """
resource_access:
  profiles:
    default:
      resources:
        long_term_memory:
          read: deny
          write: allow
""",
        encoding="utf-8",
    )
    reg = load_resource_access_registry(ResourceAccessSource(path=Path(p)))
    ev = ResourceAccessEvaluator(reg.profiles["default"])
    assert ev.is_allowed(RESOURCE_LONG_TERM_MEMORY, "read") is False
    assert ev.is_allowed(RESOURCE_LONG_TERM_MEMORY, "write") is True
