from __future__ import annotations

from core.user_intent import Chat, SystemDelegate, ToolAdd, ToolPing
from port.intent_parser import parse_user_intent


def test_parse_tool_ping() -> None:
    i = parse_user_intent("/tool ping")
    assert isinstance(i, ToolPing)


def test_parse_delegate() -> None:
    i = parse_user_intent("/delegate sub_a please run")
    assert isinstance(i, SystemDelegate)
    assert i.target == "sub_a"
    assert i.payload == "please run"


def test_parse_delegate_target_only() -> None:
    i = parse_user_intent("/delegate bot_x")
    assert isinstance(i, SystemDelegate)
    assert i.target == "bot_x"
    assert i.payload == ""


def test_parse_delegate_invalid_target_falls_back_to_chat() -> None:
    i = parse_user_intent("/delegate bad!target x")
    assert isinstance(i, Chat)


def test_parse_tool_add() -> None:
    i = parse_user_intent("/tool add 2 3")
    assert isinstance(i, ToolAdd)
    assert i.a == 2 and i.b == 3
