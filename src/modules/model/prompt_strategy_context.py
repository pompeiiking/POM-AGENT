"""Chat 路径默认的 ``prompt_strategy_ref``（由 ``ModelModuleImpl`` 在 _run_chat 入口注入）。"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator

_DEFAULT_REF = ContextVar[str]("default_prompt_strategy_ref", default="builtin:none")


def get_default_prompt_strategy_ref() -> str:
    return _DEFAULT_REF.get()


@contextmanager
def prompt_strategy_ref_scope(ref: str) -> Iterator[None]:
    token: Token = _DEFAULT_REF.set(str(ref).strip() or "builtin:none")
    try:
        yield
    finally:
        _DEFAULT_REF.reset(token)
