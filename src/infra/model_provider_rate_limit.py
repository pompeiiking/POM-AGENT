"""按 provider.id 的滑动窗口调用限流（简易计量，进程内）。"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

from modules.model.config import ModelProvider
from modules.model.interface import ModelOutput


@dataclass
class _Entry:
    stamps: deque[float] = field(default_factory=deque)


_lock = threading.Lock()
_states: dict[str, _Entry] = {}


def clear_model_provider_rate_limit_state() -> None:
    with _lock:
        _states.clear()


def _parse_rate_params(provider: ModelProvider) -> tuple[int, float]:
    raw_m = provider.params.get("model_rate_max_calls_per_window")
    max_calls = 0
    if isinstance(raw_m, bool):
        max_calls = 0
    elif isinstance(raw_m, int) and raw_m > 0:
        max_calls = raw_m
    elif isinstance(raw_m, float) and raw_m == int(raw_m) and int(raw_m) > 0:
        max_calls = int(raw_m)
    elif isinstance(raw_m, str) and raw_m.strip().isdigit() and int(raw_m.strip()) > 0:
        max_calls = int(raw_m.strip())

    raw_w = provider.params.get("model_rate_window_seconds")
    window = 60.0
    if isinstance(raw_w, (int, float)):
        window = float(raw_w)
    elif isinstance(raw_w, str):
        try:
            window = float(raw_w.strip())
        except ValueError:
            window = 60.0
    if window < 1.0:
        window = 1.0
    return max_calls, window


def model_rate_precheck(provider: ModelProvider) -> ModelOutput | None:
    """
    在即将发起一次 OpenAI 兼容请求前调用：窗口内调用次数已达上限则返回错误 ModelOutput。
    通过预检时会记入本次时间戳（按「尝试次数」计量，含后续可能失败的请求）。
    """
    max_calls, window = _parse_rate_params(provider)
    if max_calls <= 0:
        return None
    pid = provider.id
    now = time.monotonic()
    cutoff = now - window
    with _lock:
        st = _states.setdefault(pid, _Entry())
        while st.stamps and st.stamps[0] < cutoff:
            st.stamps.popleft()
        if len(st.stamps) >= max_calls:
            oldest = st.stamps[0]
            retry_after = max(0.0, window - (now - oldest))
            return ModelOutput(
                kind="text",
                content=(
                    f"模型 [{pid}] 调用过于频繁：本窗口内已达 {max_calls} 次上限，约 {retry_after:.0f}s 后可重试。"
                ),
            )
        st.stamps.append(now)
    return None
