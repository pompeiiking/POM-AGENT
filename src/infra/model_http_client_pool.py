from __future__ import annotations

import atexit
import threading
from collections import OrderedDict

import httpx

_POOL_LOCK = threading.Lock()
_POOL: OrderedDict[tuple[str, float], httpx.Client] = OrderedDict()
_MAX_POOL_ENTRIES = 48


def clear_model_http_client_pool() -> None:
    """测试或进程内重置时关闭并清空池。"""
    global _POOL
    with _POOL_LOCK:
        for _k, client in _POOL.items():
            try:
                client.close()
            except Exception:
                pass
        _POOL = OrderedDict()


def _pop_oldest_unlocked() -> None:
    _k, old = _POOL.popitem(last=False)
    try:
        old.close()
    except Exception:
        pass


def get_pooled_httpx_client(*, base_url: str, timeout: float) -> httpx.Client:
    """
    按 ``(base_url, timeout)`` 复用 ``httpx.Client``，减少 TLS/连接握手开销。
    ``base_url`` 应为 scheme+host（无尾斜杠路径），与 ``model_providers`` 中一致。
    """
    key = (base_url.rstrip("/"), float(timeout))
    with _POOL_LOCK:
        client = _POOL.get(key)
        if client is not None:
            _POOL.move_to_end(key)
            return client
        client = httpx.Client(
            timeout=timeout,
            limits=httpx.Limits(max_keepalive_connections=32, max_connections=64),
        )
        _POOL[key] = client
        while len(_POOL) > _MAX_POOL_ENTRIES:
            _pop_oldest_unlocked()
        return client


def _atexit_close() -> None:
    clear_model_http_client_pool()


atexit.register(_atexit_close)
