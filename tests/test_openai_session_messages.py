from __future__ import annotations

from core.session.openai_message_format import assistant_content_openai_v1, ensure_tool_call_id, tool_content_openai_v1
from core.types import ToolCall


def test_assistant_and_tool_roundtrip_shape() -> None:
    tc = ToolCall(name="echo", arguments={"text": "x"}, call_id="cid1")
    a = assistant_content_openai_v1(tc)
    assert a["_format"] == "openai_v1"
    assert a["message"]["tool_calls"][0]["id"] == "cid1"
    t = tool_content_openai_v1(tool_call_id="cid1", payload={"ok": True})
    assert t["message"]["role"] == "tool"
    assert t["message"]["tool_call_id"] == "cid1"


def test_ensure_tool_call_id_generates() -> None:
    tc = ToolCall(name="a", arguments={})
    u = ensure_tool_call_id(tc)
    assert u.call_id and len(u.call_id) >= 8
