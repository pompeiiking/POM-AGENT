from __future__ import annotations

from core.session.session import Session, SessionConfig, SessionLimits, SessionStats, SessionStatus
from infra.session_json_codec import session_from_json_dict, session_to_json_dict


def test_session_limits_roundtrip_includes_assembly_message_max_chars() -> None:
    lim = SessionLimits(
        max_tokens=1,
        max_context_window=1,
        max_loops=1,
        timeout_seconds=1.0,
        assembly_message_max_chars=9999,
        assembly_approx_context_tokens=5000,
    )
    cfg = SessionConfig(
        model="m",
        skills=[],
        security="none",
        limits=lim,
        prompt_profile="strict",
        prompt_strategy="tool_first",
    )
    s = Session(
        session_id="a",
        user_id="u",
        channel="c",
        config=cfg,
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[],
    )
    d = session_to_json_dict(s)
    assert d["config"]["limits"]["assembly_message_max_chars"] == 9999
    assert d["config"]["limits"]["assembly_approx_context_tokens"] == 5000
    s2 = session_from_json_dict(d)
    assert s2.config.limits.assembly_message_max_chars == 9999
    assert s2.config.limits.assembly_approx_context_tokens == 5000
    assert s2.config.limits.assembly_token_counter == "heuristic"
    assert s2.config.limits.assembly_tiktoken_encoding == "cl100k_base"
    assert s2.config.prompt_profile == "strict"
    assert s2.config.prompt_strategy == "tool_first"


def test_session_limits_roundtrip_token_counter_explicit() -> None:
    lim = SessionLimits(
        max_tokens=1,
        max_context_window=1,
        max_loops=1,
        timeout_seconds=1.0,
        assembly_token_counter="tiktoken",
        assembly_tiktoken_encoding="o200k_base",
    )
    cfg = SessionConfig(model="m", skills=[], security="none", limits=lim)
    s = Session(
        session_id="b",
        user_id="u",
        channel="c",
        config=cfg,
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[],
    )
    d = session_to_json_dict(s)
    assert d["config"]["limits"]["assembly_token_counter"] == "tiktoken"
    assert d["config"]["limits"]["assembly_tiktoken_encoding"] == "o200k_base"
    s2 = session_from_json_dict(d)
    assert s2.config.limits.assembly_token_counter == "tiktoken"
    assert s2.config.limits.assembly_tiktoken_encoding == "o200k_base"
