from __future__ import annotations

import os
from typing import Any

import httpx

from core.memory.embedding_openai_params import OpenAICompatibleEmbeddingParams
from core.memory.ports import EmbeddingProvider


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """
    调用 OpenAI 兼容 `/v1/embeddings`；API 密钥仅通过环境变量（名见 params.api_key_env）。
    可选注入 `http_client` 供测试（MockTransport）；生产路径为每次请求新建 Client。
    """

    def __init__(
        self,
        *,
        params: OpenAICompatibleEmbeddingParams,
        output_dim: int,
        http_client: httpx.Client | None = None,
    ) -> None:
        if output_dim <= 0:
            raise ValueError("output_dim must be positive")
        self._params = params
        self._output_dim = output_dim
        self._http_client = http_client

    @property
    def dim(self) -> int:
        return self._output_dim

    def embed(self, text: str) -> list[float]:
        key = os.environ.get(self._params.api_key_env, "").strip()
        if not key:
            raise RuntimeError(
                f"embedding: set non-empty {self._params.api_key_env!r} for OpenAI-compatible embeddings"
            )
        base = self._params.base_url.rstrip("/")
        url = f"{base}/v1/embeddings"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body: dict[str, Any] = {
            "model": self._params.model,
            "input": text,
            "dimensions": self._output_dim,
        }
        if self._http_client is not None:
            return self._post_and_parse(self._http_client, url, headers, body)
        with httpx.Client(timeout=self._params.timeout_seconds) as client:
            return self._post_and_parse(client, url, headers, body)

    def _post_and_parse(
        self,
        client: httpx.Client,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> list[float]:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        try:
            vec = data["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"embedding: unexpected API response shape: {data!r}") from e
        if not isinstance(vec, list) or not vec:
            raise RuntimeError(f"embedding: empty or invalid embedding: {vec!r}")
        out = [float(x) for x in vec]
        if len(out) != self._output_dim:
            raise RuntimeError(
                f"embedding: expected dimension {self._output_dim}, got {len(out)} "
                "(align memory_policy.embedding_dim with model output or omit dimensions on server)"
            )
        return out
