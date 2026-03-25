from __future__ import annotations

from datetime import datetime

import pytest

from core.session.multimodal_user_payload import (
    OPENAI_USER_CONTENT_KEY,
    agent_payload_from_user_input,
    flatten_payload_for_security,
    is_multimodal_agent_payload,
    message_uses_openai_multimodal_user_content,
    new_user_message_from_agent_payload,
    openai_blocks_to_parts,
)
from core.session.session import Part
from infra.session_json_codec import _message_from_dict, _message_to_dict
from modules.assembly.types import Context
from modules.model.impl import _isolate_history_plain_messages, _render_history_messages_for_model_plain


def test_is_multimodal_agent_payload() -> None:
    assert not is_multimodal_agent_payload("hi")
    assert not is_multimodal_agent_payload({OPENAI_USER_CONTENT_KEY: []})
    assert is_multimodal_agent_payload({OPENAI_USER_CONTENT_KEY: [{"type": "text", "text": "a"}]})


def test_openai_blocks_to_parts_and_roundtrip_json() -> None:
    parts = openai_blocks_to_parts(
        [
            {"type": "text", "text": "caption"},
            {"type": "image_url", "image_url": {"url": "https://example.com/x.png"}},
        ]
    )
    assert len(parts) == 2
    assert parts[0].type == "text"
    assert parts[1].type == "image_url"
    assert parts[1].content == {"url": "https://example.com/x.png"}

    m = new_user_message_from_agent_payload(
        {OPENAI_USER_CONTENT_KEY: [{"type": "text", "text": "x"}], "text": ""},
        loop_index=0,
    )
    d = _message_to_dict(m)
    m2 = _message_from_dict(d)
    assert len(m2.parts) == 1
    assert m2.parts[0].type == "text"


def test_flatten_payload_for_security_includes_urls() -> None:
    s = flatten_payload_for_security(
        {
            OPENAI_USER_CONTENT_KEY: [{"type": "image_url", "image_url": {"url": "https://evil.test/p.png"}}],
            "text": "",
        }
    )
    assert "evil.test" in s


def test_message_uses_openai_multimodal_user_content() -> None:
    from core.session.session import Message

    plain = Message(
        message_id="1",
        role="user",
        parts=[Part(type="text", content="a")],
        timestamp=datetime.now(),
        loop_index=0,
    )
    assert not message_uses_openai_multimodal_user_content(plain)
    mm = Message(
        message_id="2",
        role="user",
        parts=[
            Part(type="text", content="a"),
            Part(type="image_url", content={"url": "https://x/u"}),
        ],
        timestamp=datetime.now(),
        loop_index=0,
    )
    assert message_uses_openai_multimodal_user_content(mm)


def test_render_history_skips_trailing_multimodal_user() -> None:
    from core.session.session import Message

    m1 = Message(
        message_id="a",
        role="user",
        parts=[Part(type="text", content="first")],
        timestamp=datetime.now(),
        loop_index=0,
    )
    m2 = Message(
        message_id="b",
        role="user",
        parts=[
            Part(type="text", content="see"),
            Part(type="image_url", content={"url": "https://example.com/i.png"}),
        ],
        timestamp=datetime.now(),
        loop_index=0,
    )
    ctx = Context(messages=[m1, m2], current="see", intent=None, meta={})
    hist = _render_history_messages_for_model_plain(ctx, max_history=10)
    assert len(hist) == 1
    assert hist[0] == {"role": "user", "content": "first"}


def test_agent_payload_from_user_input() -> None:
    assert agent_payload_from_user_input("hi", None) == "hi"
    p = agent_payload_from_user_input("", ({"type": "text", "text": "t"},))
    assert isinstance(p, dict)
    assert p[OPENAI_USER_CONTENT_KEY][0]["text"] == "t"


def test_openai_blocks_rejects_bad_type() -> None:
    with pytest.raises(ValueError):
        openai_blocks_to_parts([{"type": "video", "x": 1}])


def test_render_history_includes_earlier_multimodal_user_as_blocks() -> None:
    from core.session.session import Message

    mm_prev = Message(
        message_id="m0",
        role="user",
        parts=[
            Part(type="text", content="old"),
            Part(type="image_url", content={"url": "https://example.com/old.png"}),
        ],
        timestamp=datetime.now(),
        loop_index=0,
    )
    mm_cur = Message(
        message_id="m1",
        role="user",
        parts=[
            Part(type="text", content="new"),
            Part(type="image_url", content={"url": "https://example.com/new.png"}),
        ],
        timestamp=datetime.now(),
        loop_index=0,
    )
    ctx = Context(messages=[mm_prev, mm_cur], current="new", intent=None, meta={})
    hist = _render_history_messages_for_model_plain(ctx, max_history=10)
    assert len(hist) == 1
    assert hist[0]["role"] == "user"
    assert isinstance(hist[0]["content"], list)
    assert hist[0]["content"][0] == {"type": "text", "text": "old"}
    assert hist[0]["content"][1]["type"] == "image_url"
    assert hist[0]["content"][1]["image_url"]["url"] == "https://example.com/old.png"


def test_isolate_history_wraps_text_inside_multimodal_user_blocks() -> None:
    hist = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "hello"},
                {"type": "image_url", "image_url": {"url": "https://x/u"}},
            ],
        }
    ]
    out = _isolate_history_plain_messages(hist)
    assert "pompeii:zone-begin name=history_user" in out[0]["content"][0]["text"]
    assert out[0]["content"][1]["type"] == "image_url"
