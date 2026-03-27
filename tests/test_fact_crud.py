"""Fact CRUD：Orchestrator 层 + /fact 命令端到端测试。"""
from __future__ import annotations

from core.memory.orchestrator import MemoryOrchestrator
from core.memory.policy_config import MemoryPolicyConfig
from core.user_intent import SystemFact
from port.intent_parser import parse_user_intent
from infra.sqlite_dual_memory_store import SqliteDualMemoryStore
from core.memory.embedding_hash import HashEmbeddingProvider


def _policy() -> MemoryPolicyConfig:
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
        embedding_async=False,
        embedding_dim=16,
        fts_enabled=True,
        vector_max_candidates=200,
        channel_filter="any",
        dual_store_ref="builtin:dual_sqlite",
        embedding_ref="builtin:hash",
        embedding_openai=None,
    )


def _orchestrator() -> MemoryOrchestrator:
    store = SqliteDualMemoryStore(":memory:")
    emb = HashEmbeddingProvider(dim=16)
    return MemoryOrchestrator(store=store, embedding=emb, policy=_policy())


# ════════════════════════════════════════════════
# 1. Intent Parser: /fact 命令
# ════════════════════════════════════════════════

class TestFactIntentParser:

    def test_add(self) -> None:
        intent = parse_user_intent("/fact add 地球是圆的")
        assert isinstance(intent, SystemFact)
        assert intent.action == "add"
        assert intent.statement == "地球是圆的"

    def test_get(self) -> None:
        intent = parse_user_intent("/fact get 地球")
        assert isinstance(intent, SystemFact)
        assert intent.action == "get"
        assert intent.statement == "地球"

    def test_list(self) -> None:
        intent = parse_user_intent("/fact list")
        assert isinstance(intent, SystemFact)
        assert intent.action == "list"

    def test_delete(self) -> None:
        intent = parse_user_intent("/fact delete 地球")
        assert isinstance(intent, SystemFact)
        assert intent.action == "delete"
        assert intent.statement == "地球"

    def test_invalid_falls_through_to_chat(self) -> None:
        from core.user_intent import Chat
        intent = parse_user_intent("/fact")
        assert isinstance(intent, Chat)


# ════════════════════════════════════════════════
# 2. Orchestrator: Fact CRUD
# ════════════════════════════════════════════════

class TestFactOrchestrator:

    def test_add_and_get(self) -> None:
        mo = _orchestrator()
        mo.add_fact("u1", "太阳从东边升起")
        assert mo.get_fact("u1", "太阳") == "太阳从东边升起"

    def test_get_nonexistent(self) -> None:
        mo = _orchestrator()
        assert mo.get_fact("u1", "不存在") is None

    def test_prefix_match_latest(self) -> None:
        mo = _orchestrator()
        mo.add_fact("u1", "版本 v1")
        mo.add_fact("u1", "版本 v2 更新")
        got = mo.get_fact("u1", "版本")
        assert got == "版本 v2 更新"

    def test_list_facts(self) -> None:
        mo = _orchestrator()
        mo.add_fact("u1", "a")
        mo.add_fact("u1", "b")
        facts = mo.list_facts("u1")
        assert set(facts) == {"a", "b"}

    def test_list_empty(self) -> None:
        mo = _orchestrator()
        assert mo.list_facts("u1") == []

    def test_delete(self) -> None:
        mo = _orchestrator()
        mo.add_fact("u1", "可删事实")
        assert mo.delete_fact("u1", "可删") is True
        assert mo.get_fact("u1", "可删") is None

    def test_delete_nonexistent(self) -> None:
        mo = _orchestrator()
        assert mo.delete_fact("u1", "nope") is False

    def test_user_isolation(self) -> None:
        mo = _orchestrator()
        mo.add_fact("u1", "仅 u1")
        mo.add_fact("u2", "仅 u2")
        assert mo.get_fact("u1", "仅") == "仅 u1"
        assert mo.get_fact("u2", "仅") == "仅 u2"
