from __future__ import annotations

from contextlib import contextmanager

import pytest

from modules.model.config import ModelProvider
from modules.model.impl import _post_openai_chat_stream
from modules.model.openai_stream_accumulate import OpenAiChatStreamCollector


def test_collector_merges_tool_call_chunks() -> None:
    c = OpenAiChatStreamCollector()
    c.feed_sse_line(
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_1","type":"function",'
        '"function":{"name":"echo","arguments":""}}]}}]}'
    )
    c.feed_sse_line(
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"text\\":\\"hi\\"}"}}]}}]}'
    )
    msg = c.build_assistant_message()
    assert "tool_calls" in msg
    assert msg["tool_calls"][0]["function"]["name"] == "echo"
    assert "hi" in msg["tool_calls"][0]["function"]["arguments"]


def test_collector_content_and_tool_calls() -> None:
    c = OpenAiChatStreamCollector()
    c.feed_sse_line('data: {"choices":[{"delta":{"content":"hi "}}]}')
    c.feed_sse_line(
        'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"x","function":{"name":"ping","arguments":"{}"}}]}}]}'
    )
    msg = c.build_assistant_message()
    assert msg.get("content") == "hi "
    assert msg["tool_calls"][0]["function"]["name"] == "ping"


def test_post_stream_tools_path_returns_tool_call(monkeypatch: pytest.MonkeyPatch) -> None:
    deltas: list[str] = []

    class FakeStream:
        def __enter__(self) -> FakeStream:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            yield (
                b'data: {"choices":[{"delta":{"tool_calls":['
                b'{"index":0,"id":"c1","type":"function","function":{"name":"add","arguments":""}}'
                b"]}}]}"
            )
            yield b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{}"}}]}}]}'
            yield b"data: [DONE]"

    class FakeClient:
        def stream(self, method: str, url: str, headers=None, json=None):
            assert json.get("stream") is True
            return FakeStream()

    @contextmanager
    def _fake_cm(*_a: object, **_k: object):
        yield FakeClient()

    monkeypatch.setattr("modules.model.impl._chat_http_client", _fake_cm)
    prov = ModelProvider(
        id="p",
        backend="openai_compatible",
        params={"stream": True, "stream_with_tools": True},
    )
    out = _post_openai_chat_stream(
        provider=prov,
        base_url="http://x",
        url="http://x/v1/chat/completions",
        headers={},
        payload={"model": "m", "messages": [], "tools": [{"type": "function"}]},
        timeout_f=5.0,
        on_delta=deltas.append,
        tools_in_payload=True,
    )
    assert out.kind == "tool_call"
    assert out.tool_call is not None
    assert out.tool_call.name == "add"
