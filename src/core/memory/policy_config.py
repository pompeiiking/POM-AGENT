from __future__ import annotations

from dataclasses import dataclass

from .embedding_openai_params import OpenAICompatibleEmbeddingParams


@dataclass(frozen=True)
class MemoryPolicyConfig:
    enabled: bool
    retrieve_top_k: int
    rrf_k: int
    rerank_enabled: bool
    rerank_max_candidates: int
    chunk_max_chars: int
    chunk_overlap_chars: int
    promote_on_archive: bool
    archive_chunk_max_chars: int
    archive_trust: str
    embedding_async: bool
    embedding_dim: int
    fts_enabled: bool
    vector_max_candidates: int
    channel_filter: str
    dual_store_ref: str
    embedding_ref: str
    embedding_openai: OpenAICompatibleEmbeddingParams | None
