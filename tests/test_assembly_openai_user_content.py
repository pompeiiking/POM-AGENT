from __future__ import annotations

from datetime import datetime

from core.session.session import Message, Part
from modules.assembly.openai_user_content import (
    apply_user_parts_preprocessing,
    openai_user_message_payload,
)
from modules.tools.network_policy import ToolNetworkPolicyConfig


def test_apply_user_parts_preprocessing_identity() -> None:
    p = [Part(type="text", content="a", metadata={})]
    assert apply_user_parts_preprocessing(p) == p
    assert apply_user_parts_preprocessing(p) is not p


def test_openai_user_payload_text_only() -> None:
    m = Message(
        message_id="1",
        role="user",
        parts=[Part(type="text", content="hello", metadata={})],
        timestamp=datetime.now(),
        loop_index=0,
    )
    assert openai_user_message_payload(m) == "hello"


def test_openai_user_payload_multimodal() -> None:
    m = Message(
        message_id="2",
        role="user",
        parts=[
            Part(type="text", content="x", metadata={}),
            Part(type="image_url", content={"url": "https://e/i.png"}, metadata={}),
        ],
        timestamp=datetime.now(),
        loop_index=0,
    )
    out = openai_user_message_payload(m)
    assert isinstance(out, list)
    assert out[0]["type"] == "text"
    assert out[1]["type"] == "image_url"


def test_preprocess_blocks_private_ip_without_guard() -> None:
    parts = [Part(type="image_url", content={"url": "https://127.0.0.1/a.png"}, metadata={})]
    out = apply_user_parts_preprocessing(
        parts,
        session_meta={"multimodal_image_url_read_allowed": True, "multimodal_http_url_guard_enabled": False},
    )
    assert out[0].type == "text"
    assert "blocked_ip_literal" in out[0].content


def test_preprocess_blocks_localhost_without_guard() -> None:
    parts = [Part(type="image_url", content={"url": "https://localhost/x.png"}, metadata={})]
    out = apply_user_parts_preprocessing(
        parts,
        session_meta={"multimodal_image_url_read_allowed": True, "multimodal_http_url_guard_enabled": False},
    )
    assert out[0].type == "text"
    assert "localhost_forbidden" in out[0].content


def test_preprocess_rejects_non_http_scheme() -> None:
    parts = [Part(type="image_url", content={"url": "ftp://example.com/a.png"}, metadata={})]
    out = apply_user_parts_preprocessing(
        parts,
        session_meta={"multimodal_image_url_read_allowed": True},
    )
    assert out[0].type == "text"
    assert "bad_scheme" in out[0].content


def test_preprocess_resource_access_denies_image() -> None:
    parts = [Part(type="image_url", content={"url": "https://example.com/a.png"}, metadata={})]
    out = apply_user_parts_preprocessing(
        parts,
        session_meta={"multimodal_image_url_read_allowed": False},
    )
    assert out[0].type == "text"
    assert "denied" in out[0].content


def test_preprocess_http_url_guard_allowlist() -> None:
    pol = ToolNetworkPolicyConfig(http_url_guard_enabled=True, http_url_allowed_hosts=("good.example",))
    meta = {
        "multimodal_image_url_read_allowed": True,
        "multimodal_http_url_guard_enabled": pol.http_url_guard_enabled,
        "multimodal_http_url_allowed_hosts": list(pol.http_url_allowed_hosts),
    }
    ok = Part(type="image_url", content={"url": "https://good.example/x.png"}, metadata={})
    bad = Part(type="image_url", content={"url": "https://evil.example/x.png"}, metadata={})
    o1 = apply_user_parts_preprocessing([ok], session_meta=meta)
    o2 = apply_user_parts_preprocessing([bad], session_meta=meta)
    assert o1[0].type == "image_url"
    assert o2[0].type == "text"
    assert "guard" in o2[0].content


def test_openai_user_payload_non_user() -> None:
    m = Message(
        message_id="3",
        role="assistant",
        parts=[Part(type="text", content="hi", metadata={})],
        timestamp=datetime.now(),
        loop_index=0,
    )
    assert openai_user_message_payload(m) is None
