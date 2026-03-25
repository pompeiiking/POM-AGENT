from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpenAICompatibleEmbeddingParams:
    """OpenAI 兼容 `/v1/embeddings` 参数；密钥仅经环境变量名解析。"""

    api_key_env: str
    base_url: str
    model: str
    timeout_seconds: float


def default_openai_compatible_embedding_params() -> OpenAICompatibleEmbeddingParams:
    return OpenAICompatibleEmbeddingParams(
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com",
        model="text-embedding-3-small",
        timeout_seconds=30.0,
    )
