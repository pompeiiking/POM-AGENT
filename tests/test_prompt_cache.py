from __future__ import annotations

import time

from infra.prompt_cache import PromptCache, PromptCacheConfig


def test_prompt_cache_hit_and_miss() -> None:
    c = PromptCache(PromptCacheConfig(max_entries=2, ttl_seconds=60))
    assert c.get("k1") is None
    c.set("k1", "v1")
    assert c.get("k1") == "v1"


def test_prompt_cache_ttl_expire() -> None:
    c = PromptCache(PromptCacheConfig(max_entries=2, ttl_seconds=1))
    c.set("k1", "v1")
    time.sleep(1.05)
    assert c.get("k1") is None
