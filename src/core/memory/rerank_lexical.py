from __future__ import annotations

import re
from typing import Sequence

from .snippets import MemorySnippet


def tokenize(s: str) -> set[str]:
    return {t.lower() for t in re.split(r"\W+", s) if t}


def lexical_rerank(query: str, snippets: Sequence[MemorySnippet], *, max_output: int) -> list[MemorySnippet]:
    """轻量 rerank：查询词命中密度；不依赖外部模型。"""
    if not snippets:
        return []
    q = tokenize(query)
    if not q:
        return list(snippets[:max_output])
    scored: list[tuple[float, MemorySnippet]] = []
    for sn in snippets:
        tset = tokenize(sn.text)
        hit = len(q & tset)
        scored.append((float(hit) + sn.score * 0.01, sn))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:max_output]]
