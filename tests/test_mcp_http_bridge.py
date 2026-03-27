from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from core.types import ToolCall
from infra.mcp_config_loader import McpHttpServerEntry
from infra.mcp_http_bridge import McpHttpBridge


def _session() -> Session:
    lim = SessionLimits(max_tokens=100, max_context_window=100, max_loops=3, timeout_seconds=60.0)
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


def test_mcp_http_bridge_success(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = McpHttpServerEntry(id="h1", base_url="http://mcp.local", timeout_seconds=5.0)
    bridge = McpHttpBridge(entry)
    fake_resp = MagicMock()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.json = MagicMock(return_value={"output": {"ok": True}})
    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.post = MagicMock(return_value=fake_resp)
    monkeypatch.setattr("infra.mcp_http_bridge.httpx.Client", lambda **kw: fake_client)
    out = bridge.try_call(_session(), ToolCall(name="ping", arguments={}))
    assert out is not None
    assert out.output == {"ok": True}
    assert out.source == "mcp"


def test_mcp_http_bridge_error(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = McpHttpServerEntry(id="h1", base_url="http://mcp.local", timeout_seconds=5.0)
    bridge = McpHttpBridge(entry)
    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.post = MagicMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr("infra.mcp_http_bridge.httpx.Client", lambda **kw: fake_client)
    out = bridge.try_call(_session(), ToolCall(name="ping", arguments={}))
    assert out is not None
    assert isinstance(out.output, dict) and out.output.get("mcp_error") is True


def test_mcp_http_bridge_stream_result(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = McpHttpServerEntry(
        id="h1",
        base_url="http://mcp.local",
        timeout_seconds=5.0,
        stream_enabled=True,
        stream_endpoint_path="/tools/call/stream",
    )
    bridge = McpHttpBridge(entry)

    stream_resp = MagicMock()
    stream_resp.raise_for_status = MagicMock()
    stream_resp.iter_lines = MagicMock(
        return_value=[
            'data: {"type":"delta","delta":"hel"}',
            'data: {"type":"delta","delta":"lo"}',
            "data: [DONE]",
        ]
    )

    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)

    class _CM:
        def __enter__(self):
            return stream_resp

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_client.stream = MagicMock(return_value=_CM())
    monkeypatch.setattr("infra.mcp_http_bridge.httpx.Client", lambda **kw: fake_client)
    out = bridge.try_call(_session(), ToolCall(name="ping", arguments={}))
    assert out is not None
    assert out.output == {"text": "hello"}


def test_mcp_http_bridge_stream_result_object(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = McpHttpServerEntry(id="h1", base_url="http://mcp.local", timeout_seconds=5.0, stream_enabled=True)
    bridge = McpHttpBridge(entry)
    stream_resp = MagicMock()
    stream_resp.raise_for_status = MagicMock()
    stream_resp.iter_lines = MagicMock(return_value=['data: {"type":"result","output":{"ok":true}}', "data: [DONE]"])

    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)

    class _CM:
        def __enter__(self):
            return stream_resp

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_client.stream = MagicMock(return_value=_CM())
    monkeypatch.setattr("infra.mcp_http_bridge.httpx.Client", lambda **kw: fake_client)
    out = bridge.try_call(_session(), ToolCall(name="ping", arguments={}))
    assert out is not None
    assert out.output == {"ok": True}


def test_mcp_http_bridge_stream_custom_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = McpHttpServerEntry(
        id="h1",
        base_url="http://mcp.local",
        timeout_seconds=5.0,
        stream_enabled=True,
        sse_event_type_key="event",
        sse_delta_key="chunk",
        sse_text_key="txt",
        sse_output_key="result",
        sse_result_event_value="done",
    )
    bridge = McpHttpBridge(entry)
    stream_resp = MagicMock()
    stream_resp.raise_for_status = MagicMock()
    stream_resp.iter_lines = MagicMock(
        return_value=[
            'data: {"event":"delta","chunk":"ab"}',
            'data: {"event":"delta","txt":"cd"}',
            'data: {"event":"done","result":{"ok":true}}',
            "data: [DONE]",
        ]
    )
    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)

    class _CM:
        def __enter__(self):
            return stream_resp

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_client.stream = MagicMock(return_value=_CM())
    monkeypatch.setattr("infra.mcp_http_bridge.httpx.Client", lambda **kw: fake_client)
    out = bridge.try_call(_session(), ToolCall(name="ping", arguments={}))
    assert out is not None
    assert out.output == {"ok": True}
