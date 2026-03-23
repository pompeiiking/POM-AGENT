from __future__ import annotations

from core.user_intent import ToolAdd, ToolPing
from port.intent_parser import parse_user_intent


def test_parse_tool_ping() -> None:
    i = parse_user_intent("/tool ping")
    assert isinstance(i, ToolPing)


def test_parse_tool_add() -> None:
    i = parse_user_intent("/tool add 2 3")
    assert isinstance(i, ToolAdd)
    assert i.a == 2 and i.b == 3
