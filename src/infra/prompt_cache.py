from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptCacheConfig:
    max_entries: int = 256
    ttl_seconds: float = 300.0


class PromptCache:
    def __init__(self, config: PromptCacheConfig | None = None) -> None:
        self._cfg = config or PromptCacheConfig()
        self._store: OrderedDict[str, tuple[float, str]] = OrderedDict()

    def get(self, key: str) -> str | None:
        row = self._store.get(key)
        if row is None:
            return None
        expires_at, value = row
        now = time.time()
        if expires_at < now:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: str) -> None:
        now = time.time()
        expires_at = now + max(1.0, float(self._cfg.ttl_seconds))
        self._store[key] = (expires_at, value)
        self._store.move_to_end(key)
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        max_entries = max(1, int(self._cfg.max_entries))
        while len(self._store) > max_entries:
            self._store.popitem(last=False)
