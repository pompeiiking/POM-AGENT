from __future__ import annotations

from pathlib import Path

from core.memory.content import MemoryChunkRecord
from core.memory.embedding_hash import HashEmbeddingProvider
from core.memory.orchestrator import MemoryOrchestrator
from core.memory.policy_config import MemoryPolicyConfig
from core.session.message_factory import new_message
from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from infra.sqlite_dual_memory_store import SqliteDualMemoryStore


def _policy(*, enabled: bool = True, fts: bool = True, async_emb: bool = False) -> MemoryPolicyConfig:
    return MemoryPolicyConfig(
        enabled=enabled,
        retrieve_top_k=8,
        rrf_k=60,
        rerank_enabled=True,
        rerank_max_candidates=24,
        chunk_max_chars=256,
        chunk_overlap_chars=32,
        promote_on_archive=True,
        archive_chunk_max_chars=2000,
        archive_trust="medium",
        embedding_async=async_emb,
        embedding_dim=64,
        fts_enabled=fts,
        vector_max_candidates=200,
        channel_filter="any",
        dual_store_ref="builtin:dual_sqlite",
        embedding_ref="builtin:hash",
        embedding_openai=None,
    )


def test_orchestrator_ingest_retrieve_rrf(tmp_path: Path) -> None:
    db = tmp_path / "mem.db"
    store = SqliteDualMemoryStore(str(db))
    orch = MemoryOrchestrator(store, HashEmbeddingProvider(dim=64), _policy())
    orch.ingest_record(MemoryChunkRecord(user_id="u1", text="用户喜欢深烘咖啡与燕麦奶", channel="c1"))
    orch.flush_embedding_queue()
    hits = orch.retrieve_for_context(user_id="u1", channel="c1", query_text="咖啡")
    assert len(hits) >= 1
    assert any("咖啡" in h.text for h in hits)


def test_forget_tombstones(tmp_path: Path) -> None:
    db = tmp_path / "mem.db"
    store = SqliteDualMemoryStore(str(db))
    orch = MemoryOrchestrator(store, HashEmbeddingProvider(dim=64), _policy())
    orch.ingest_record(MemoryChunkRecord(user_id="u1", text="secret token alpha"))
    orch.flush_embedding_queue()
    n = orch.forget_phrase("u1", "secret")
    assert n >= 1
    hits = orch.retrieve_for_context(user_id="u1", channel=None, query_text="secret")
    assert hits == []


def test_promote_archived_session_writes_memory(tmp_path: Path) -> None:
    db = tmp_path / "mem.db"
    store = SqliteDualMemoryStore(str(db))
    orch = MemoryOrchestrator(store, HashEmbeddingProvider(dim=64), _policy())
    lim = SessionLimits(
        max_tokens=100,
        max_context_window=100,
        max_loops=3,
        timeout_seconds=10.0,
    )
    session = Session(
        session_id="s1",
        user_id="u1",
        channel="ch",
        config=SessionConfig(model="m", skills=[], security="none", limits=lim),
        status=SessionStatus.ARCHIVED,
        stats=SessionStats(),
        messages=[
            new_message(role="user", content="讨论归档与记忆", loop_index=0),
        ],
    )
    orch.promote_archived_session(session)
    orch.flush_embedding_queue()
    hits = orch.retrieve_for_context(user_id="u1", channel="ch", query_text="归档")
    assert len(hits) >= 1
