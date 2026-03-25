from __future__ import annotations

from contextlib import contextmanager

import pytest

from modules.model.config import ModelProvider
from modules.model.impl import _post_openai_chat_stream, _provider_stream_enabled
from modules.model.openai_sse import text_deltas_from_sse_line


def test_text_deltas_from_sse_line() -> None:
    line = 'data: {"choices":[{"delta":{"content":"你好"}}]}'
    assert text_deltas_from_sse_line(line) == ["你好"]


def test_text_deltas_done_empty() -> None:
    assert text_deltas_from_sse_line("data: [DONE]") == []


def test_provider_stream_enabled() -> None:
    p = ModelProvider("a", "openai_compatible", {"stream": True})
    assert _provider_stream_enabled(p) is True
    p2 = ModelProvider("b", "openai_compatible", {"stream": "yes"})
    assert _provider_stream_enabled(p2) is True
    p3 = ModelProvider("c", "openai_compatible", {})
    assert _provider_stream_enabled(p3) is False


def test_post_openai_chat_stream_invokes_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: list[str] = []

    class FakeStream:
        def __enter__(self) -> FakeStream:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            yield b'data: {"choices":[{"delta":{"content":"a"}}]}'
            yield b"data: [DONE]"

    class FakeClient:
        def stream(self, method: str, url: str, headers=None, json=None):
            assert json.get("stream") is True
            return FakeStream()

    @contextmanager
    def _fake_chat_client(*_a: object, **_k: object):
        yield FakeClient()

    monkeypatch.setattr("modules.model.impl._chat_http_client", _fake_chat_client)
    prov = ModelProvider(id="p", backend="openai_compatible", params={})
    out = _post_openai_chat_stream(
        provider=prov,
        base_url="http://x",
        url="http://x/v1/chat/completions",
        headers={"Authorization": "Bearer x"},
        payload={"model": "m", "messages": [{"role": "user", "content": "hi"}]},
        timeout_f=5.0,
        on_delta=lambda s: recorded.append(s),
    )
    assert out.kind == "text"
    assert out.content == "a"
    assert recorded == ["a"]
