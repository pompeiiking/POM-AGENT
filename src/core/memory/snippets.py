from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemorySnippet:
    """组装部 / 模型侧可消费的检索片段（权威正文 + 溯源）。"""

    memory_id: str
    text: str
    score: float
    source: str
