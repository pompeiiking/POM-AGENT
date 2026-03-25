from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from core.types import ToolCall
from modules.tools.builtin_handlers import (
    HTTP_GET_TOOL_REF,
    http_get_tool,
    make_http_get_handler,
)
from modules.tools.impl import load_tool_handler
from modules.tools.network_policy import ToolNetworkPolicyConfig


def _session() -> Session:
    lim = SessionLimits(max_tokens=10, max_context_window=10, max_loops=3, timeout_seconds=10.0)
    cfg = SessionConfig(model="stub", skills=[], security="none", limits=lim)
    return Session(
        session_id="s",
        user_id="u",
        channel="c",
        config=cfg,
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[],
    )


def test_http_get_tool_ref_loads_placeholder() -> None:
    fn = load_tool_handler(HTTP_GET_TOOL_REF)
    assert fn is http_get_tool


def test_http_get_unbound_returns_error() -> None:
    out = http_get_tool(_session(), ToolCall(name="http_get", arguments={"url": "https://a.com/"}, call_id=None))
    assert out.output.get("error") == "http_get_unbound"


def test_http_get_bad_url() -> None:
    h = make_http_get_handler(ToolNetworkPolicyConfig())
    out = h(_session(), ToolCall(name="http_get", arguments={}, call_id=None))
    assert out.output.get("error") == "http_get_bad_url"


def test_http_get_url_guard_when_enabled() -> None:
    pol = ToolNetworkPolicyConfig(http_url_guard_enabled=True, http_url_allowed_hosts=("example.com",))
    h = make_http_get_handler(pol)
    out = h(
        _session(),
        ToolCall(name="http_get", arguments={"url": "https://evil.com/"}, call_id=None),
    )
    assert out.output.get("error") == "http_get_url_guard"


def test_http_get_success_monkeypatched_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    pol = ToolNetworkPolicyConfig(http_url_guard_enabled=True, http_url_allowed_hosts=("example.com",))
    h = make_http_get_handler(pol)

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.headers = {"content-type": "text/plain; charset=utf-8"}
    fake_resp.content = b"hello world"

    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.get = MagicMock(return_value=fake_resp)

    monkeypatch.setattr("modules.tools.builtin_handlers.httpx.Client", lambda **kw: fake_client)

    out = h(
        _session(),
        ToolCall(name="http_get", arguments={"url": "https://example.com/x"}, call_id=None),
    )
    assert out.output.get("kind") == "http_get"
    assert out.output.get("status_code") == 200
    assert out.output.get("body_preview") == "hello world"
    assert out.source == "http_fetch"
    fake_client.get.assert_called_once_with("https://example.com/x")


def test_http_get_blocks_disallowed_content_type(monkeypatch: pytest.MonkeyPatch) -> None:
    pol = ToolNetworkPolicyConfig(
        http_url_guard_enabled=True,
        http_url_allowed_hosts=("example.com",),
        http_blocked_content_type_prefixes=("application/octet-stream",),
    )
    h = make_http_get_handler(pol)

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.headers = {"content-type": "application/octet-stream; charset=binary"}
    fake_resp.content = b"x"

    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.get = MagicMock(return_value=fake_resp)

    monkeypatch.setattr("modules.tools.builtin_handlers.httpx.Client", lambda **kw: fake_client)

    out = h(
        _session(),
        ToolCall(name="http_get", arguments={"url": "https://example.com/bin"}, call_id=None),
    )
    assert out.output.get("error") == "http_get_content_type_blocked"
    assert out.output.get("content_type") == "application/octet-stream"
