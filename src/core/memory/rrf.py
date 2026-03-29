from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping


def reciprocal_rank_fusion(
    ranked_lists: Iterable[tuple[str, list[str]]],
    *,
    k: int,
) -> list[tuple[str, float]]:
    """
    RRF：多路有序列表融合为单一分数。
    ranked_lists: (source_name, [id, ...]) 按相关度降序。
    返回 [(id, rrf_score), ...] 降序。
    """
    scores: dict[str, float] = defaultdict(float)
    for _src, ids in ranked_lists:
        for rank, mid in enumerate(ids, start=1):
            scores[mid] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def dedupe_preserve_order(ids: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i in seen:
            continue
        seen.add(i)
        out.append(i)
    return out


def ranks_from_scores(score_map: Mapping[str, float]) -> list[str]:
    return [k for k, _ in sorted(score_map.items(), key=lambda x: x[1], reverse=True)]
