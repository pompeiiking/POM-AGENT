from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app.memory_orchestrator_registry import DEFAULT_DUAL_STORE_REF, DEFAULT_EMBEDDING_REF

from core.memory.embedding_openai_params import OpenAICompatibleEmbeddingParams
from core.memory.policy_config import MemoryPolicyConfig

from .session_config_loader import read_config_mapping


class MemoryPolicyLoaderError(ValueError):
    pass


@dataclass(frozen=True)
class MemoryPolicySource:
    path: Path


def load_memory_policy(source: MemoryPolicySource) -> MemoryPolicyConfig:
    data = read_config_mapping(source.path)
    root = _require_mapping(data, "memory_policy")
    return MemoryPolicyConfig(
        enabled=_req_bool(root, "enabled"),
        retrieve_top_k=_req_pos_int(root, "retrieve_top_k"),
        rrf_k=_req_pos_int(root, "rrf_k"),
        rerank_enabled=_req_bool(root, "rerank_enabled"),
        rerank_max_candidates=_req_pos_int(root, "rerank_max_candidates"),
        chunk_max_chars=_req_pos_int(root, "chunk_max_chars"),
        chunk_overlap_chars=_req_nonneg_int(root, "chunk_overlap_chars"),
        promote_on_archive=_req_bool(root, "promote_on_archive"),
        archive_chunk_max_chars=_req_pos_int(root, "archive_chunk_max_chars"),
        archive_trust=_req_str(root, "archive_trust"),
        embedding_async=_req_bool(root, "embedding_async"),
        embedding_dim=_req_pos_int(root, "embedding_dim"),
        fts_enabled=_req_bool(root, "fts_enabled"),
        vector_max_candidates=_req_pos_int(root, "vector_max_candidates"),
        channel_filter=_req_str(root, "channel_filter"),
        dual_store_ref=_opt_str(root, "dual_store_ref", default=DEFAULT_DUAL_STORE_REF),
        embedding_ref=_opt_str(root, "embedding_ref", default=DEFAULT_EMBEDDING_REF),
        embedding_openai=_load_embedding_openai(root),
    )


def _require_mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    v = data.get(key)
    if not isinstance(v, Mapping):
        raise MemoryPolicyLoaderError(f"missing or invalid object: {key}")
    return v


def _req_str(parent: Mapping[str, Any], key: str) -> str:
    v = parent.get(key)
    if not isinstance(v, str) or not v.strip():
        raise MemoryPolicyLoaderError(f"memory_policy.{key} must be non-empty string")
    return v.strip()


def _req_bool(parent: Mapping[str, Any], key: str) -> bool:
    v = parent.get(key)
    if isinstance(v, bool):
        return v
    raise MemoryPolicyLoaderError(f"memory_policy.{key} must be boolean")


def _req_pos_int(parent: Mapping[str, Any], key: str) -> int:
    v = parent.get(key)
    if isinstance(v, bool) or not isinstance(v, int):
        raise MemoryPolicyLoaderError(f"memory_policy.{key} must be int")
    if v <= 0:
        raise MemoryPolicyLoaderError(f"memory_policy.{key} must be positive")
    return v


def _req_nonneg_int(parent: Mapping[str, Any], key: str) -> int:
    v = parent.get(key)
    if isinstance(v, bool) or not isinstance(v, int):
        raise MemoryPolicyLoaderError(f"memory_policy.{key} must be int")
    if v < 0:
        raise MemoryPolicyLoaderError(f"memory_policy.{key} must be non-negative")
    return v


def _opt_str(parent: Mapping[str, Any], key: str, *, default: str) -> str:
    v = parent.get(key)
    if isinstance(v, str) and v.strip():
        return v.strip()
    return default


def _opt_positive_float(parent: Mapping[str, Any], key: str, *, default: float) -> float:
    v = parent.get(key)
    if v is None:
        return default
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise MemoryPolicyLoaderError(f"memory_policy.embedding_openai.{key} must be number")
    x = float(v)
    if x <= 0:
        raise MemoryPolicyLoaderError(f"memory_policy.embedding_openai.{key} must be positive")
    return x


def _load_embedding_openai(parent: Mapping[str, Any]) -> OpenAICompatibleEmbeddingParams | None:
    node = parent.get("embedding_openai")
    if node is None:
        return None
    if not isinstance(node, Mapping):
        raise MemoryPolicyLoaderError("memory_policy.embedding_openai must be a mapping when present")
    bu = _opt_str(node, "base_url", default="https://api.openai.com").rstrip("/")
    if not bu:
        bu = "https://api.openai.com"
    return OpenAICompatibleEmbeddingParams(
        api_key_env=_opt_str(node, "api_key_env", default="OPENAI_API_KEY"),
        base_url=bu,
        model=_opt_str(node, "model", default="text-embedding-3-small"),
        timeout_seconds=_opt_positive_float(node, "timeout_seconds", default=30.0),
    )
