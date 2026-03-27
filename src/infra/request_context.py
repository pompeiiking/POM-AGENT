"""
请求级上下文（contextvars）：供日志与横切观测关联同一次 Port→Core 调用。

在 ``GenericAgentPort.handle`` 各分支进入内核前绑定，``finally`` 中复位。
"""
from __future__ import annotations

from contextvars import ContextVar, Token

_request_id: ContextVar[str | None] = ContextVar("pompeii_request_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("pompeii_user_id", default=None)
_channel: ContextVar[str | None] = ContextVar("pompeii_channel", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def get_user_id() -> str | None:
    return _user_id.get()


def get_channel() -> str | None:
    return _channel.get()


def bind_request_context(*, request_id: str, user_id: str, channel: str) -> tuple[Token, Token, Token]:
    """返回三个 Token，须成对传入 ``reset_request_context``。"""
    return (
        _request_id.set(request_id),
        _user_id.set(user_id),
        _channel.set(channel),
    )


def reset_request_context(tokens: tuple[Token, Token, Token]) -> None:
    _request_id.reset(tokens[0])
    _user_id.reset(tokens[1])
    _channel.reset(tokens[2])
