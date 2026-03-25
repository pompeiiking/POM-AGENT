"""按 provider.id 的简易熔断：连续文本形态失败后暂停调用一段时间。"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from modules.model.config import ModelProvider
from modules.model.interface import ModelOutput
from modules.model.openai_failure import openai_output_suggests_failover


@dataclass
class _Entry:
    consecutive_failures: int = 0
    open_until: float = 0.0


_lock = threading.Lock()
_states: dict[str, _Entry] = {}


def clear_model_provider_circuit_state() -> None:
    with _lock:
        _states.clear()


def _parse_circuit_params(provider: ModelProvider) -> tuple[int, float]:
    raw_t = provider.params.get("model_circuit_failure_threshold")
    threshold = 0
    if isinstance(raw_t, bool):
        threshold = 0
    elif isinstance(raw_t, int):
        threshold = raw_t
    elif isinstance(raw_t, float) and raw_t == int(raw_t) and raw_t >= 0:
        threshold = int(raw_t)
    elif isinstance(raw_t, str) and raw_t.strip().isdigit():
        threshold = int(raw_t.strip())

    raw_s = provider.params.get("model_circuit_open_seconds")
    seconds = 60.0
    if isinstance(raw_s, (int, float)):
        seconds = float(raw_s)
    elif isinstance(raw_s, str):
        try:
            seconds = float(raw_s.strip())
        except ValueError:
            seconds = 60.0
    if seconds < 1.0:
        seconds = 1.0
    return threshold, seconds


def model_circuit_precheck(provider: ModelProvider) -> ModelOutput | None:
    threshold, _seconds = _parse_circuit_params(provider)
    if threshold <= 0:
        return None
    pid = provider.id
    now = time.monotonic()
    with _lock:
        st = _states.setdefault(pid, _Entry())
        if st.open_until > now:
            remaining = st.open_until - now
            return ModelOutput(
                kind="text",
                content=(
                    f"模型 [{pid}] 熔断中：连续失败后已暂停调用，约 {remaining:.0f}s 后可重试。"
                ),
            )
        if st.open_until > 0:
            st.open_until = 0.0
    return None


def model_circuit_record(provider: ModelProvider, out: ModelOutput) -> None:
    threshold, seconds = _parse_circuit_params(provider)
    if threshold <= 0:
        return
    pid = provider.id
    failed = openai_output_suggests_failover(out)
    now = time.monotonic()
    with _lock:
        st = _states.setdefault(pid, _Entry())
        if failed:
            st.consecutive_failures += 1
            if st.consecutive_failures >= threshold:
                st.open_until = now + seconds
                st.consecutive_failures = 0
        else:
            st.consecutive_failures = 0
            st.open_until = 0.0
