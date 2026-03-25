from __future__ import annotations

from pathlib import Path

import pytest

from app.memory_orchestrator_registry import (
    BUILTIN_DUAL_SQLITE,
    BUILTIN_EMBEDDING_HASH,
    BUILTIN_OPENAI_COMPATIBLE_EMBEDDING,
    DualMemoryStoreRegistryError,
    EmbeddingProviderRegistryError,
    resolve_dual_memory_store,
    resolve_embedding_provider,
)
from core.memory.embedding_openai_params import OpenAICompatibleEmbeddingParams
from core.memory.policy_config import MemoryPolicyConfig
from infra.sqlite_dual_memory_store import SqliteDualMemoryStore


def test_resolve_builtin_dual_sqlite(tmp_path: Path) -> None:
    p = tmp_path / "m.db"
    store = resolve_dual_memory_store(BUILTIN_DUAL_SQLITE, memory_db_path=p)
    assert isinstance(store, SqliteDualMemoryStore)
    store.close()


def test_resolve_builtin_hash_embedding() -> None:
    emb = resolve_embedding_provider(BUILTIN_EMBEDDING_HASH, embedding_dim=64)
    assert emb.dim == 64
    assert len(emb.embed("hi")) == 64


def test_resolve_dual_entrypoint_custom(tmp_path: Path) -> None:
    p = tmp_path / "x.db"

    def factory(path: Path) -> SqliteDualMemoryStore:
        return SqliteDualMemoryStore(str(path))

    store = resolve_dual_memory_store(
        "entrypoint:custom",
        memory_db_path=p,
        discover_fn=lambda _g: {"custom": factory},
    )
    assert isinstance(store, SqliteDualMemoryStore)
    store.close()


def test_resolve_embedding_entrypoint_custom() -> None:
    from core.memory.embedding_hash import HashEmbeddingProvider

    def factory(dim: int, policy: MemoryPolicyConfig | None) -> HashEmbeddingProvider:
        _ = policy
        return HashEmbeddingProvider(dim=dim)

    emb = resolve_embedding_provider(
        "entrypoint:custom_emb",
        embedding_dim=32,
        discover_fn=lambda _g: {"custom_emb": factory},
    )
    assert emb.dim == 32


def test_resolve_builtin_openai_compatible_uses_policy_params() -> None:
    import os

    import httpx

    from infra.openai_compatible_embedding_provider import OpenAICompatibleEmbeddingProvider

    def handler(request: httpx.Request) -> httpx.Response:
        b = request.read().decode()
        assert "dimensions" in b and "64" in b
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.25] * 64}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    params = OpenAICompatibleEmbeddingParams(
        api_key_env="TEST_EMBED_KEY",
        base_url="https://embed.test",
        model="m",
        timeout_seconds=5.0,
    )
    policy = MemoryPolicyConfig(
        enabled=True,
        retrieve_top_k=6,
        rrf_k=60,
        rerank_enabled=False,
        rerank_max_candidates=8,
        chunk_max_chars=128,
        chunk_overlap_chars=8,
        promote_on_archive=False,
        archive_chunk_max_chars=1000,
        archive_trust="low",
        embedding_async=False,
        embedding_dim=64,
        fts_enabled=True,
        vector_max_candidates=50,
        channel_filter="any",
        dual_store_ref="builtin:dual_sqlite",
        embedding_ref=BUILTIN_OPENAI_COMPATIBLE_EMBEDDING,
        embedding_openai=params,
    )
    os.environ["TEST_EMBED_KEY"] = "sk-test"
    try:
        emb = resolve_embedding_provider(
            BUILTIN_OPENAI_COMPATIBLE_EMBEDDING,
            embedding_dim=64,
            policy=policy,
        )
        assert isinstance(emb, OpenAICompatibleEmbeddingProvider)
        injected = OpenAICompatibleEmbeddingProvider(
            params=params,
            output_dim=64,
            http_client=client,
        )
        v = injected.embed("hello")
        assert len(v) == 64
    finally:
        os.environ.pop("TEST_EMBED_KEY", None)


def test_resolve_dual_missing_entrypoint_raises(tmp_path: Path) -> None:
    with pytest.raises(DualMemoryStoreRegistryError):
        resolve_dual_memory_store("entrypoint:nope", memory_db_path=tmp_path / "a.db", discover_fn=lambda _g: {})


def test_resolve_embedding_missing_entrypoint_raises() -> None:
    with pytest.raises(EmbeddingProviderRegistryError):
        resolve_embedding_provider("entrypoint:nope", embedding_dim=64, discover_fn=lambda _g: {})


def test_empty_ref_uses_default_dual(tmp_path: Path) -> None:
    store = resolve_dual_memory_store("", memory_db_path=tmp_path / "d.db")
    assert isinstance(store, SqliteDualMemoryStore)
    store.close()
