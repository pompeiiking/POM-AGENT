from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path
from typing import Callable, cast

from core.memory.embedding_hash import HashEmbeddingProvider
from core.memory.embedding_openai_params import default_openai_compatible_embedding_params
from core.memory.policy_config import MemoryPolicyConfig
from core.memory.ports import DualMemoryStore, EmbeddingProvider
from infra.openai_compatible_embedding_provider import OpenAICompatibleEmbeddingProvider
from infra.sqlite_dual_memory_store import SqliteDualMemoryStore

# 与会话 store_ref 对称：缺省走 builtin；插件通过 entrypoint 注册（见各 resolve_* docstring）

DEFAULT_DUAL_STORE_REF = "builtin:dual_sqlite"
DEFAULT_EMBEDDING_REF = "builtin:hash"

ENTRYPOINT_GROUP_DUAL_MEMORY = "pompeii_agent.memory_dual_stores"
ENTRYPOINT_GROUP_EMBEDDING = "pompeii_agent.embedding_providers"

BUILTIN_DUAL_SQLITE = "builtin:dual_sqlite"
BUILTIN_EMBEDDING_HASH = "builtin:hash"
BUILTIN_OPENAI_COMPATIBLE_EMBEDDING = "builtin:openai_compatible"


class DualMemoryStoreRegistryError(ValueError):
    pass


class EmbeddingProviderRegistryError(ValueError):
    pass


DualMemoryStoreFactory = Callable[[Path], DualMemoryStore]
EmbeddingProviderFactory = Callable[[int, MemoryPolicyConfig | None], EmbeddingProvider]


def resolve_dual_memory_store(
    ref: str,
    *,
    memory_db_path: Path,
    entrypoint_group: str = ENTRYPOINT_GROUP_DUAL_MEMORY,
    discover_fn: Callable[[str], dict[str, DualMemoryStoreFactory]] | None = None,
) -> DualMemoryStore:
    """
    长期记忆「双库」后端热插拔（标准行 + FTS + 向量投影合一实现）。
    - builtin:dual_sqlite：infra.SqliteDualMemoryStore，签名为 factory(memory_db_path: Path) -> DualMemoryStore
    - entrypoint:<name>：同上签名
    """
    r = str(ref).strip() or DEFAULT_DUAL_STORE_REF
    if r == BUILTIN_DUAL_SQLITE:
        return SqliteDualMemoryStore(str(memory_db_path))
    if r.startswith("entrypoint:"):
        name = r[len("entrypoint:") :].strip()
        if not name:
            raise DualMemoryStoreRegistryError("dual memory store entrypoint name must be non-empty")
        registry = discover_fn(entrypoint_group) if discover_fn is not None else _discover_dual_factories(group=entrypoint_group)
        factory = registry.get(name)
        if factory is None:
            raise DualMemoryStoreRegistryError(
                f"dual memory store entrypoint {name!r} not found in group {entrypoint_group!r}"
            )
        return factory(memory_db_path)
    raise DualMemoryStoreRegistryError(
        f"dual memory store ref must be {BUILTIN_DUAL_SQLITE!r} or 'entrypoint:<name>', got {ref!r}"
    )


def resolve_embedding_provider(
    ref: str,
    *,
    embedding_dim: int,
    policy: MemoryPolicyConfig | None = None,
    entrypoint_group: str = ENTRYPOINT_GROUP_EMBEDDING,
    discover_fn: Callable[[str], dict[str, EmbeddingProviderFactory]] | None = None,
) -> EmbeddingProvider:
    """
    向量嵌入模型热插拔。
    - builtin:hash：HashEmbeddingProvider(dim=…)
    - builtin:openai_compatible：OpenAI 兼容 /v1/embeddings；参数来自 policy.embedding_openai 或内置默认；密钥仅环境变量
    - entrypoint:<name>：签名为 factory(embedding_dim: int, policy: MemoryPolicyConfig | None) -> EmbeddingProvider
    """
    r = str(ref).strip() or DEFAULT_EMBEDDING_REF
    if r == BUILTIN_EMBEDDING_HASH:
        return HashEmbeddingProvider(dim=embedding_dim)
    if r == BUILTIN_OPENAI_COMPATIBLE_EMBEDDING:
        params = (
            policy.embedding_openai
            if policy is not None and policy.embedding_openai is not None
            else default_openai_compatible_embedding_params()
        )
        return OpenAICompatibleEmbeddingProvider(params=params, output_dim=embedding_dim)
    if r.startswith("entrypoint:"):
        name = r[len("entrypoint:") :].strip()
        if not name:
            raise EmbeddingProviderRegistryError("embedding provider entrypoint name must be non-empty")
        registry = discover_fn(entrypoint_group) if discover_fn is not None else _discover_embedding_factories(group=entrypoint_group)
        factory = registry.get(name)
        if factory is None:
            raise EmbeddingProviderRegistryError(
                f"embedding provider entrypoint {name!r} not found in group {entrypoint_group!r}"
            )
        return factory(embedding_dim, policy)
    raise EmbeddingProviderRegistryError(
        f"embedding ref must be {BUILTIN_EMBEDDING_HASH!r}, {BUILTIN_OPENAI_COMPATIBLE_EMBEDDING!r}, "
        f"or 'entrypoint:<name>', got {ref!r}"
    )


def _discover_dual_factories(*, group: str) -> dict[str, DualMemoryStoreFactory]:
    eps = entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else [e for e in eps if e.group == group]
    out: dict[str, DualMemoryStoreFactory] = {}
    for ep in selected:
        ep_name = str(ep.name).strip()
        if not ep_name:
            raise DualMemoryStoreRegistryError(f"entry point in group {group!r} has empty name")
        fn = ep.load()
        if not callable(fn):
            raise DualMemoryStoreRegistryError(f"entry point {group}:{ep_name} is not callable")
        out[ep_name] = cast(DualMemoryStoreFactory, fn)
    return out


def _discover_embedding_factories(*, group: str) -> dict[str, EmbeddingProviderFactory]:
    eps = entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else [e for e in eps if e.group == group]
    out: dict[str, EmbeddingProviderFactory] = {}
    for ep in selected:
        ep_name = str(ep.name).strip()
        if not ep_name:
            raise EmbeddingProviderRegistryError(f"entry point in group {group!r} has empty name")
        fn = ep.load()
        if not callable(fn):
            raise EmbeddingProviderRegistryError(f"entry point {group}:{ep_name} is not callable")
        out[ep_name] = cast(EmbeddingProviderFactory, fn)
    return out
