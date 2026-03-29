from __future__ import annotations

import hashlib
import struct
from typing import List


class HashEmbeddingProvider:
    """
    确定性本地嵌入：无外部 API，用于开发与测试。
    生产可换为 HTTP/OpenAI 等实现，保持 dim 与 StandardMemoryRepository 中 dims 一致。
    """

    def __init__(self, *, dim: int) -> None:
        if dim <= 0 or dim % 4 != 0:
            raise ValueError("embedding dim must be positive multiple of 4")
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        raw = text.encode("utf-8", errors="replace")
        out: List[float] = []
        block = 0
        while len(out) < self._dim:
            digest = hashlib.sha256(raw + block.to_bytes(4, "big")).digest()
            needed = self._dim - len(out)
            take = min(needed, len(digest) // 4)
            for i in range(take):
                (v,) = struct.unpack_from("f", digest, i * 4)
                out.append(float(v))
            block += 1
        return out[: self._dim]
