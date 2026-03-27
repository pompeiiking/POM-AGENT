from __future__ import annotations

import httpx
import pytest

from core.memory.embedding_hash import HashEmbeddingProvider
from core.memory.orchestrator import MemoryOrchestrator
from core.memory.policy_config import MemoryPolicyConfig
from core.resource_access import ResourceAccessEvaluator, ResourceAccessProfile, ResourceAccessRule
from infra.sqlite_dual_memory_store import SqliteDualMemoryStore


def _policy(remote_url: str) -> MemoryPolicyConfig:
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
        remote_retrieval_url=remote_url,
        remote_timeout_seconds=3.0,
    )


def test_remote_retrieval_merges(monkeypatch: pytest.MonkeyPatch) -> None:
    mo = MemoryOrchestrator(
        store=SqliteDualMemoryStore(":memory:"),
        embedding=HashEmbeddingProvider(dim=16),
        policy=_policy("http://remote/retrieve"),
    )
    mo.add_fact("u1", "local_fact")

    def fake_post(url: str, *, json: dict, timeout: float):
        assert url == "http://remote/retrieve"
        assert json["user_id"] == "u1"
        req = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=req,
            json=[{"memory_id": "remote-1", "text": "remote_fact", "score": 0.9}],
        )

    monkeypatch.setattr("core.memory.orchestrator.httpx.post", fake_post)
    out = mo.retrieve_for_context(user_id="u1", channel=None, query_text="fact")
    mids = {s.memory_id for s in out}
    assert "remote-1" in mids


def test_remote_retrieval_blocked_by_resource_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = ResourceAccessEvaluator(
        ResourceAccessProfile(
            rules={"remote_retrieval": ResourceAccessRule(read="deny", write="deny")}
        )
    )
    mo = MemoryOrchestrator(
        store=SqliteDualMemoryStore(":memory:"),
        embedding=HashEmbeddingProvider(dim=16),
        policy=_policy("http://remote/retrieve"),
        resource_access=gate,
    )
    mo.add_fact("u1", "local_fact")

    def should_not_call(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("httpx.post should not be called when remote_retrieval is denied")

    monkeypatch.setattr("core.memory.orchestrator.httpx.post", should_not_call)
    out = mo.retrieve_for_context(user_id="u1", channel=None, query_text="fact")
    mids = {s.memory_id for s in out}
    assert "remote-1" not in mids


def test_remote_retrieval_requires_approval_emits_policy_snippet(monkeypatch: pytest.MonkeyPatch) -> None:
    gate = ResourceAccessEvaluator(
        ResourceAccessProfile(
            rules={
                "remote_retrieval": ResourceAccessRule(
                    read="allow",
                    write="deny",
                    read_requires_approval=True,
                )
            }
        )
    )
    mo = MemoryOrchestrator(
        store=SqliteDualMemoryStore(":memory:"),
        embedding=HashEmbeddingProvider(dim=16),
        policy=_policy("http://remote/retrieve"),
        resource_access=gate,
    )

    def should_not_call(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("httpx.post should not be called when remote_retrieval needs approval")

    monkeypatch.setattr("core.memory.orchestrator.httpx.post", should_not_call)
    out = mo.retrieve_for_context(user_id="u1", channel=None, query_text="fact")
    mids = {s.memory_id for s in out}
    assert "policy:remote_retrieval_approval_required" in mids
