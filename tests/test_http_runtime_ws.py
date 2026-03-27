from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

from app.http_runtime import app
from port.events import StatusEvent


@dataclass
class _FakePort:
    def handle(self, input_event: Any, *, user_id: str | None = None, channel: str | None = None, emitter: Any = None) -> None:
        _ = input_event
        if emitter is not None:
            emitter.emit(StatusEvent(kind="status", status=f"ok:{user_id}:{channel}"))


def test_ws_input_roundtrip(monkeypatch) -> None:
    import app.http_runtime as rt

    monkeypatch.setattr(rt, "_HTTP_PORT", _FakePort())
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"kind": "user_message", "user_id": "u1", "channel": "c1", "text": "hi"})
        got = ws.receive_json()
    assert isinstance(got, dict)
    ev = got["events"][0]
    assert ev["kind"] == "status"
    assert ev["status"] == "ok:u1:c1"


def test_ws_input_bad_payload_type(monkeypatch) -> None:
    import app.http_runtime as rt

    monkeypatch.setattr(rt, "_HTTP_PORT", _FakePort())
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json(["bad"])
        got = ws.receive_json()
    ev = got["events"][0]
    assert ev["kind"] == "error"
    assert ev["reason"] == "validation_ws_payload_type"
