from __future__ import annotations

from core.session.session import Part, Message, Session, SessionStatus, SessionStats
from core.session.session import SessionConfig, SessionLimits
from modules.assembly.types import Context
from modules.model.config import ModelProvider
from modules.model.impl import (
    _maybe_make_tool_first_reply,
    _resolve_user_message_for_model,
    _render_prompt_template,
    _resolve_prompt_profile_text,
    _sanitize_openai_history_messages,
)


def _limits() -> SessionLimits:
    return SessionLimits(
        max_tokens=1,
        max_context_window=1,
        max_loops=1,
        timeout_seconds=1.0,
    )


def test_resolve_prompt_profile_text_prefers_selected_profile() -> None:
    params = {
        "prompt_profiles": {
            "default": {"default": "default prompt"},
            "strict": {"default": "strict prompt"},
        }
    }
    assert _resolve_prompt_profile_text(params, "strict") == "strict prompt"


def test_resolve_prompt_profile_text_falls_back_to_default() -> None:
    params = {"prompt_profiles": {"default": {"default": "default prompt"}}}
    assert _resolve_prompt_profile_text(params, "unknown") == "default prompt"


def test_session_config_accepts_prompt_profile() -> None:
    cfg = SessionConfig(
        model="stub",
        skills=[],
        security="none",
        limits=_limits(),
        prompt_profile="strict",
        prompt_strategy="tool_first",
    )
    assert cfg.prompt_profile == "strict"
    assert cfg.prompt_strategy == "tool_first"


def test_resolve_prompt_profile_text_prefers_strategy_inside_profile() -> None:
    params = {
        "prompt_profiles": {
            "default": {"default": "default prompt"},
            "strict": {"default": "strict default", "tool_first": "strict tool-first"},
        }
    }
    assert _resolve_prompt_profile_text(params, "strict", "tool_first") == "strict tool-first"


def test_resolve_prompt_profile_text_supports_legacy_string_profile() -> None:
    params = {"prompt_profiles": {"default": "legacy default"}}
    assert _resolve_prompt_profile_text(params, "default", "concise") == "legacy default"


def _session_for_strategy(strategy: str) -> Session:
    return Session(
        session_id="s1",
        user_id="u1",
        channel="http",
        config=SessionConfig(
            model="stub",
            skills=[],
            security="none",
            limits=_limits(),
            prompt_profile="strict",
            prompt_strategy=strategy,
        ),
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[],
    )


def test_tool_first_reply_extracts_structured_result() -> None:
    session = _session_for_strategy("tool_first")
    provider = ModelProvider(
        id="deepseek",
        backend="openai_compatible",
        params={"tool_result_render": {"default": "short", "tool_first": "short"}},
    )
    context = Context(
        messages=[Message(message_id="m1", role="tool", parts=[Part(type="text", content="x")])],
        current='tool add -> {"structuredContent":{"result":5},"isError":false}',
        intent=None,
        meta={},
    )
    assert _maybe_make_tool_first_reply(session=session, context=context, provider=provider) == "5"


def test_tool_first_reply_disabled_for_default_strategy() -> None:
    session = _session_for_strategy("default")
    provider = ModelProvider(id="deepseek", backend="openai_compatible", params={})
    context = Context(messages=[], current='tool ping -> {"result":"pong"}', intent=None, meta={})
    assert _maybe_make_tool_first_reply(session=session, context=context, provider=provider) is None


def test_tool_first_reply_can_render_raw_payload() -> None:
    session = _session_for_strategy("tool_first")
    provider = ModelProvider(
        id="deepseek",
        backend="openai_compatible",
        params={"tool_result_render": {"tool_first": "raw"}},
    )
    current = 'tool add -> {"structuredContent":{"result":5},"isError":false}'
    context = Context(messages=[], current=current, intent=None, meta={})
    assert _maybe_make_tool_first_reply(session=session, context=context, provider=provider) == '{"structuredContent":{"result":5},"isError":false}'


def test_tool_first_reply_can_render_short_with_reason() -> None:
    session = _session_for_strategy("tool_first")
    provider = ModelProvider(
        id="deepseek",
        backend="openai_compatible",
        params={"tool_result_render": {"tool_first": "short_with_reason"}},
    )
    context = Context(messages=[], current='tool ping -> {"result":"pong"}', intent=None, meta={})
    assert _maybe_make_tool_first_reply(session=session, context=context, provider=provider) == "pong\n(source: ping)"


def test_tool_first_reply_respects_tool_whitelist() -> None:
    session = _session_for_strategy("tool_first")
    provider = ModelProvider(
        id="deepseek",
        backend="openai_compatible",
        params={
            "tool_first_tools": {"default": ["ping", "add"]},
            "tool_result_render": {"tool_first": "short"},
        },
    )
    blocked = Context(messages=[], current='tool echo -> {"result":"hi"}', intent=None, meta={})
    allowed = Context(messages=[], current='tool ping -> {"result":"pong"}', intent=None, meta={})
    assert _maybe_make_tool_first_reply(session=session, context=blocked, provider=provider) is None
    assert _maybe_make_tool_first_reply(session=session, context=allowed, provider=provider) == "pong"


def test_render_prompt_template_supports_config_vars_and_runtime_vars() -> None:
    session = _session_for_strategy("tool_first")
    provider = ModelProvider(
        id="deepseek",
        backend="openai_compatible",
        params={"prompt_vars": {"team": "pompeii"}},
    )
    context = Context(messages=[], current="hello", intent=None, meta={})
    template = "team={team}, strategy={prompt_strategy}, profile={prompt_profile}, provider={provider_id}"
    rendered = _render_prompt_template(
        template=template,
        provider=provider,
        session=session,
        context=context,
        selected_profile="strict",
        selected_strategy="tool_first",
    )
    assert "team=pompeii" in rendered
    assert "strategy=tool_first" in rendered
    assert "profile=strict" in rendered
    assert "provider=deepseek" in rendered


def test_render_prompt_template_keeps_placeholder_when_non_strict() -> None:
    session = _session_for_strategy("default")
    provider = ModelProvider(id="deepseek", backend="openai_compatible", params={})
    context = Context(messages=[], current="hello", intent=None, meta={})
    rendered = _render_prompt_template(
        template="x={unknown_var}",
        provider=provider,
        session=session,
        context=context,
        selected_profile="default",
        selected_strategy="default",
    )
    assert rendered == "x={unknown_var}"


def test_render_prompt_template_fallback_to_original_when_strict_missing() -> None:
    session = _session_for_strategy("default")
    provider = ModelProvider(
        id="deepseek",
        backend="openai_compatible",
        params={"prompt_vars_strict": True},
    )
    context = Context(messages=[], current="hello", intent=None, meta={})
    rendered = _render_prompt_template(
        template="x={unknown_var}",
        provider=provider,
        session=session,
        context=context,
        selected_profile="default",
        selected_strategy="default",
    )
    assert rendered == "x={unknown_var}"


def test_sanitize_openai_history_drops_orphan_tool_message() -> None:
    history = [
        {"role": "user", "content": "u1"},
        {"role": "tool", "tool_call_id": "tc_missing", "content": "{\"result\":1}"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "tc_ok",
                    "type": "function",
                    "function": {"name": "ping", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "tc_ok", "content": "{\"result\":\"pong\"}"},
    ]
    got = _sanitize_openai_history_messages(history)
    assert len(got) == 3
    assert got[0]["role"] == "user"
    assert got[1]["role"] == "assistant"
    assert got[2]["role"] == "tool"
    assert got[2]["tool_call_id"] == "tc_ok"


def test_resolve_user_message_for_model_uses_user_template() -> None:
    session = _session_for_strategy("tool_first")
    provider = ModelProvider(
        id="deepseek",
        backend="openai_compatible",
        params={
            "user_prompt_profiles": {
                "strict": {
                    "tool_first": "<user_request>{user_input}</user_request>\n<channel>{channel}</channel>"
                }
            }
        },
    )
    context = Context(messages=[], current="你好", intent=None, meta={})
    got = _resolve_user_message_for_model(provider=provider, session=session, context=context, user_input="你好")
    assert "<user_request>你好</user_request>" in got
    assert "<channel>http</channel>" in got


def test_resolve_user_message_for_model_fallback_to_raw_input() -> None:
    session = _session_for_strategy("default")
    provider = ModelProvider(id="deepseek", backend="openai_compatible", params={})
    context = Context(messages=[], current="abc", intent=None, meta={})
    got = _resolve_user_message_for_model(provider=provider, session=session, context=context, user_input="abc")
    assert got == "abc"


def test_resolve_user_message_for_model_normalizes_newlines_and_nul() -> None:
    session = _session_for_strategy("default")
    provider = ModelProvider(id="deepseek", backend="openai_compatible", params={})
    context = Context(messages=[], current="x", intent=None, meta={})
    got = _resolve_user_message_for_model(
        provider=provider,
        session=session,
        context=context,
        user_input="a\r\nb\rc\x00d",
    )
    assert got == "a\nb\ncd"


def test_resolve_user_message_for_model_truncates_when_limit_configured() -> None:
    session = _session_for_strategy("default")
    provider = ModelProvider(
        id="deepseek",
        backend="openai_compatible",
        params={"user_input_max_chars": 20},
    )
    context = Context(messages=[], current="x", intent=None, meta={})
    got = _resolve_user_message_for_model(
        provider=provider,
        session=session,
        context=context,
        user_input="abcdefghijklmnopqrstuvwxyz",
    )
    assert got.endswith("...(truncated)")
    assert len(got) <= 20
