"""长期记忆：重索引与 tombstone 物理清理（Phase 2.3）。"""
from __future__ import annotations

from core.memory.content import MemoryChunkRecord
from core.memory.embedding_hash import HashEmbeddingProvider
from core.memory.orchestrator import MemoryOrchestrator
from core.memory.policy_config import MemoryPolicyConfig
from infra.sqlite_dual_memory_store import SqliteDualMemoryStore


def _policy(*, embedding_async: bool = False) -> MemoryPolicyConfig:
    return MemoryPolicyConfig(
        enabled=True,
        retrieve_top_k=4,
        rrf_k=60,
        rerank_enabled=False,
        rerank_max_candidates=16,
        chunk_max_chars=256,
        chunk_overlap_chars=32,
        promote_on_archive=False,
        archive_chunk_max_chars=2000,
        archive_trust="medium",
        embedding_async=embedding_async,
        embedding_dim=16,
        fts_enabled=True,
        vector_max_candidates=200,
        channel_filter="any",
        dual_store_ref="builtin:dual_sqlite",
        embedding_ref="builtin:hash",
        embedding_openai=None,
    )


def _mo(store: SqliteDualMemoryStore | None = None) -> MemoryOrchestrator:
    s = store or SqliteDualMemoryStore(":memory:")
    emb = HashEmbeddingProvider(dim=16)
    return MemoryOrchestrator(store=s, embedding=emb, policy=_policy())


class TestReindex:

    def test_reindex_memory_id_rebuilds_vectors(self) -> None:
        mo = _mo()
        mid = mo.ingest_record(
            MemoryChunkRecord(user_id="u1", text="hello world for vectors", channel=None, trust="medium")
        )
        mo.flush_embedding_queue()
        row1 = mo._store.get_row(mid)
        assert row1 is not None
        assert row1.embedding_status == "ready"
        ok = mo.reindex_memory_id(mid)
        assert ok is True
        mo.flush_embedding_queue()
        row2 = mo._store.get_row(mid)
        assert row2 is not None
        assert row2.embedding_status == "ready"

    def test_reindex_memory_id_false_for_tombstone(self) -> None:
        mo = _mo()
        mid = mo.add_fact("u1", "x")
        mo.delete_fact("u1", "x")
        assert mo.reindex_memory_id(mid) is False

    def test_reindex_user_memories_counts(self) -> None:
        mo = _mo()
        mo.add_fact("u1", "one")
        mo.add_fact("u1", "two")
        n = mo.reindex_user_memories("u1", limit=10)
        assert n == 2


class TestTombstoneGc:

    def test_purge_removes_tombstone_rows(self) -> None:
        store = SqliteDualMemoryStore(":memory:")
        mo = _mo(store)
        mid = mo.add_fact("u1", "待清理")
        assert mo._store.get_row(mid) is not None
        assert mo.delete_fact("u1", "待") is True
        row = mo._store.get_row(mid)
        assert row is not None
        assert row.tombstone == 1
        deleted = mo.purge_tombstoned_rows(limit=100)
        assert deleted == 1
        assert mo._store.get_row(mid) is None

    def test_purge_respects_limit(self) -> None:
        store = SqliteDualMemoryStore(":memory:")
        mo = _mo(store)
        mo.add_fact("u1", "a")
        mo.add_fact("u1", "b")
        mo.delete_fact("u1", "a")
        mo.delete_fact("u1", "b")
        first = mo.purge_tombstoned_rows(limit=1)
        assert first == 1
        second = mo.purge_tombstoned_rows(limit=10)
        assert second == 1
