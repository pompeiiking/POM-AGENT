from __future__ import annotations

import contextvars
from collections.abc import Callable
from typing import Any

_model_stream_delta: contextvars.ContextVar[Callable[[str], None] | None] = contextvars.ContextVar(
    "model_stream_delta",
    default=None,
)


def attach_model_stream_delta(cb: Callable[[str], None] | None) -> Any:
    return _model_stream_delta.set(cb)


def reset_model_stream_delta(token: Any) -> None:
    _model_stream_delta.reset(token)


def get_model_stream_delta() -> Callable[[str], None] | None:
    return _model_stream_delta.get()
