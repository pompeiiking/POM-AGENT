from __future__ import annotations

import json
import logging
import os
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from collections.abc import Callable, Iterator
from typing import Any, Mapping, Literal

import httpx

from core.model_stream_context import get_model_stream_delta
from core.session.multimodal_user_payload import message_uses_openai_multimodal_user_content
from core.session.openai_message_format import OPENAI_V1
from core.session.rule_summary import build_rule_summary_for_view, render_message_plain_text
from core.session.session import Message, Session
from core.user_intent import Chat, SystemHelp, SystemSummary, ToolAdd, ToolEcho, ToolPing, ToolTakePhoto
from modules.assembly.openai_user_content import openai_user_message_payload
from modules.assembly.context_isolation import (
    format_isolated_zone,
    tool_execution_source_token,
    trust_for_tool_result_source,
)
from modules.assembly.types import Context
from core.types import ToolCall
from .config import ModelProvider, ModelRegistry
from .interface import ModelModule, ModelOutput
from .openai_sse import text_deltas_from_sse_line
from .openai_stream_accumulate import OpenAiChatStreamCollector
from .openai_tool_parse import openai_message_to_model_output
from infra.model_http_client_pool import get_pooled_httpx_client
from infra.model_provider_circuit import model_circuit_precheck, model_circuit_record
from infra.model_provider_rate_limit import model_rate_precheck
from infra.prompt_cache import PromptCache
from .openai_failure import openai_output_suggests_failover
from .openai_provider_route import chat_completions_url, get_openai_chat_route
from .prompt_strategy_context import get_default_prompt_strategy_ref, prompt_strategy_ref_scope
from .prompt_strategy_registry import run_prompt_strategy

_log = logging.getLogger(__name__)


class ModelModuleImpl(ModelModule):
    """
    模型部实现：仅按 Context.intent 类型分发，不解析字符串。
    - intent 由 Port 边界解析并随 Request/Context 传入；
    - Chat 时根据 `ModelRegistry` 与会话 `SessionConfig.model`（provider id）选择后端；
    - `stub`：占位文本；`openai_compatible` / `deepseek`：OpenAI 兼容 Chat Completions；
    - 系统指令（SystemHelp/SystemSummary/ToolEcho/ToolTakePhoto）由本地规则处理。
    """

    def __init__(
        self,
        registry: ModelRegistry | None = None,
        *,
        provider: ModelProvider | None = None,
        skill_registry: Mapping[str, Any] | None = None,
        prompt_cache: PromptCache | None = None,
        default_prompt_strategy_ref: str = "builtin:none",
    ) -> None:
        """
        registry：完整注册表，支持按会话切换 provider。
        provider：仅用于测试或单后端注入；若与 registry 同时传入，registry 优先。
        """
        self._registry = registry
        self._single_provider = provider
        self._skill_registry = skill_registry or {}
        self._prompt_cache = prompt_cache
        self._default_prompt_strategy_ref = str(default_prompt_strategy_ref).strip() or "builtin:none"

    def run(self, session: Session, context: Any) -> ModelOutput:
        if not isinstance(context, Context):
            return ModelOutput(kind="text", content="invalid context: Context required")

        intent = context.intent
        if intent is None:
            return self._run_chat(session=session, context=context, override_text=None)

        # 按意图类型分发，无字符串判断
        if isinstance(intent, SystemHelp):
            return _make_help()
        if isinstance(intent, SystemSummary):
            return _make_summary(session=session, context=context)
        if isinstance(intent, ToolEcho):
            return _make_tool_echo(intent.text)
        if isinstance(intent, ToolPing):
            return ModelOutput(
                kind="tool_call",
                tool_call=ToolCall(name="ping", arguments={}, call_id=uuid.uuid4().hex),
            )
        if isinstance(intent, ToolAdd):
            return ModelOutput(
                kind="tool_call",
                tool_call=ToolCall(
                    name="add",
                    arguments={"a": intent.a, "b": intent.b},
                    call_id=uuid.uuid4().hex,
                ),
            )
        if isinstance(intent, ToolTakePhoto):
            return _make_tool_take_photo()
        if isinstance(intent, Chat):
            return self._run_chat(session=session, context=context, override_text=intent.text)
        return _make_text(context.current)

    def _resolve_provider(self, session: Session) -> ModelProvider | None:
        if self._registry is not None:
            key = session.config.model.strip()
            if key in self._registry.providers:
                return self._registry.providers[key]
            return self._registry.providers.get(self._registry.default_provider_id)
        if self._single_provider is not None:
            return self._single_provider
        return None

    def _run_chat(self, session: Session, context: Context, override_text: str | None) -> ModelOutput:
        """
        Chat 意图统一入口：
        - text：优先使用 override_text，其次使用 context.current；
        - 按解析到的 provider 的 backend 调用对应实现。
        """
        with prompt_strategy_ref_scope(self._default_prompt_strategy_ref):
            message_text = override_text or context.current
            provider = self._resolve_provider(session)
            tool_first_reply = _maybe_make_tool_first_reply(session=session, context=context, provider=provider)
            if tool_first_reply is not None:
                return ModelOutput(kind="text", content=tool_first_reply)
            if provider is None:
                return _make_text(message_text)

            kind = _effective_backend(provider)
            if kind == "stub":
                return _make_text(message_text)
            if kind == "openai_compatible":
                return _dispatch_chat_with_failover(
                    primary=provider,
                    registry=self._registry,
                    session=session,
                    context=context,
                    message=message_text,
                    skill_registry=self._skill_registry,
                    prompt_cache=self._prompt_cache,
                )

            return _make_text(message_text)


def _make_text(message: str) -> ModelOutput:
    return ModelOutput(kind="text", content=f"[model] 收到: {message!r}")


def _make_help() -> ModelOutput:
    content = (
        "Pompeii-Agent 模型帮助：\n"
        "- 直接输入文本：普通对话（按 model_providers.yaml + session.model 选择后端）。\n"
        "- /help：显示可用指令。\n"
        "- /summary：根据最近对话生成规则摘要（不调用外部模型）。\n"
        "- /archive：将当前活跃会话标记为已归档（SQLite 时写入 session_archives；可选 kernel.archive_llm_summary 异步 LLM 摘要写入 llm_* 列）。\n"
        "- /remember <text>：写入长期记忆（标准库 + 向量索引，受 memory_policy 约束）。\n"
        "- /forget <短语>：按短语 tombstone 匹配项。\n"
        "- /delegate <target> <payload>：发出子代理委派事件（Port emit delegate；target 须为 [a-zA-Z0-9_.-]+；可选 kernel.delegate_target_allowlist 收紧）。\n"
        "- /tool echo <text>：触发 echo 工具调用。\n"
        "- /tool take_photo：触发设备请求占位调用。\n"
        "- /tool ping：MCP 演示工具 ping（须在 mcp_servers.yaml 启用 MCP，且 kernel 白名单含 ping）。\n"
        "- /tool add <a> <b>：MCP 演示工具 add（同上，白名单含 add）。\n"
        "- 切换模型：修改 session_defaults.yaml 中 session.model 为已注册的 provider id。"
    )
    return ModelOutput(kind="text", content=content)


def _make_summary(*, session: Session, context: Context) -> ModelOutput:
    """
    基于 Context.messages（与 Assembly 视图一致）生成短摘要，不调用 LLM。
    若视图为空则回退到 session.messages 尾部。
    条数与摘录长度来自 SessionLimits（见 `core.session.rule_summary`）。
    """
    body = build_rule_summary_for_view(session, context.messages)
    return ModelOutput(kind="text", content=body)


def _make_tool_echo(text: str) -> ModelOutput:
    call = ToolCall(name="echo", arguments={"text": text}, call_id=uuid.uuid4().hex)
    return ModelOutput(kind="tool_call", tool_call=call)


def _make_tool_take_photo() -> ModelOutput:
    call = ToolCall(name="take_photo", arguments={"quality": "low"}, call_id=uuid.uuid4().hex)
    return ModelOutput(kind="tool_call", tool_call=call)


def _effective_backend(provider: ModelProvider) -> Literal["stub", "openai_compatible"]:
    """将配置中的 backend 映射为内部实现分支。"""
    b = provider.backend.strip().lower()
    if b == "stub":
        return "stub"
    if b == "openai_compatible":
        return "openai_compatible"
    return "stub"


def _dispatch_openai_compatible_chat(
    provider: ModelProvider,
    session: Session,
    context: Context,
    message: str,
    *,
    skill_registry: Mapping[str, Any] | None = None,
    prompt_cache: PromptCache | None = None,
) -> ModelOutput:
    ref = str(provider.params.get("model_backend_ref", "builtin:openai_chat")).strip() or "builtin:openai_chat"
    from modules.model.model_backend_registry import resolve_model_chat_backend

    backend = resolve_model_chat_backend(ref)
    return backend(
        provider,
        session,
        context,
        message,
        skill_registry=dict(skill_registry or {}),
        prompt_cache=prompt_cache,
    )


def _expand_provider_failover_sequence(primary: ModelProvider, registry: ModelRegistry | None) -> list[ModelProvider]:
    out: list[ModelProvider] = []
    seen: set[str] = set()

    def add(p: ModelProvider) -> None:
        if p.id in seen:
            return
        seen.add(p.id)
        out.append(p)

    add(primary)
    if registry is None:
        return out
    for fid in primary.failover_chain:
        p = registry.providers.get(fid)
        if p is not None:
            add(p)
    return out


def _dispatch_one_provider_chat(
    *,
    provider: ModelProvider,
    session: Session,
    context: Context,
    message: str,
    skill_registry: Mapping[str, Any] | None,
    prompt_cache: PromptCache | None,
) -> ModelOutput:
    kind = _effective_backend(provider)
    if kind == "stub":
        return _make_text(message)
    if kind == "openai_compatible":
        return _dispatch_openai_compatible_chat(
            provider=provider,
            session=session,
            context=context,
            message=message,
            skill_registry=skill_registry,
            prompt_cache=prompt_cache,
        )
    return _make_text(message)


def _dispatch_chat_with_failover(
    *,
    primary: ModelProvider,
    registry: ModelRegistry | None,
    session: Session,
    context: Context,
    message: str,
    skill_registry: Mapping[str, Any] | None,
    prompt_cache: PromptCache | None,
) -> ModelOutput:
    sequence = _expand_provider_failover_sequence(primary, registry)
    last_fail: ModelOutput | None = None
    for p in sequence:
        out = _dispatch_one_provider_chat(
            provider=p,
            session=session,
            context=context,
            message=message,
            skill_registry=skill_registry,
            prompt_cache=prompt_cache,
        )
        if _effective_backend(p) == "openai_compatible" and openai_output_suggests_failover(out):
            last_fail = out
            continue
        return out
    return last_fail if last_fail is not None else _make_text(message)


def _http_pool_disabled(provider: ModelProvider) -> bool:
    v = provider.params.get("http_disable_connection_pool")
    if v is True:
        return True
    if isinstance(v, str) and v.strip().lower() in ("true", "1", "yes"):
        return True
    return False


@contextmanager
def _chat_http_client(
    provider: ModelProvider,
    *,
    base_url: str,
    timeout_f: float,
) -> Iterator[httpx.Client]:
    if _http_pool_disabled(provider):
        c = httpx.Client(timeout=timeout_f)
        try:
            yield c
        finally:
            c.close()
    else:
        yield get_pooled_httpx_client(base_url=base_url, timeout=timeout_f)


def _provider_stream_enabled(provider: ModelProvider) -> bool:
    v = provider.params.get("stream")
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return False


def _provider_stream_with_tools_enabled(provider: ModelProvider) -> bool:
    """显式开启后才允许在配置了 ``params.tools`` 时仍走 SSE（依赖上游兼容流式 tool_calls）。"""
    v = provider.params.get("stream_with_tools")
    if v is True:
        return True
    if isinstance(v, str) and v.strip().lower() in ("true", "1", "yes"):
        return True
    return False


def _post_openai_chat_stream(
    *,
    provider: ModelProvider,
    base_url: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_f: float,
    on_delta: Callable[[str], None],
    tools_in_payload: bool = False,
) -> ModelOutput:
    body = {**payload, "stream": True}
    if tools_in_payload:
        collector = OpenAiChatStreamCollector()
        try:
            with _chat_http_client(provider, base_url=base_url, timeout_f=timeout_f) as client:
                with client.stream("POST", url, headers=headers, json=body) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        lt = line.decode("utf-8") if isinstance(line, bytes) else line
                        for frag in collector.feed_sse_line(lt):
                            on_delta(frag)
        except Exception as exc:
            return ModelOutput(kind="text", content=f"模型 [{provider.id}] 流式调用失败：{exc!r}")
        msg = collector.build_assistant_message()
        has_tools = isinstance(msg.get("tool_calls"), list) and bool(msg["tool_calls"])
        if not has_tools:
            full = collector.accumulated_text()
            if not full.strip():
                return ModelOutput(kind="text", content=f"模型 [{provider.id}] 流式返回为空。")
            return ModelOutput(kind="text", content=full)
        return openai_message_to_model_output(msg, provider_id=provider.id)

    acc: list[str] = []
    try:
        with _chat_http_client(provider, base_url=base_url, timeout_f=timeout_f) as client:
            with client.stream("POST", url, headers=headers, json=body) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    lt = line.decode("utf-8") if isinstance(line, bytes) else line
                    for frag in text_deltas_from_sse_line(lt):
                        acc.append(frag)
                        on_delta(frag)
    except Exception as exc:
        return ModelOutput(kind="text", content=f"模型 [{provider.id}] 流式调用失败：{exc!r}")
    full = "".join(acc)
    if not full.strip():
        return ModelOutput(kind="text", content=f"模型 [{provider.id}] 流式返回为空。")
    return ModelOutput(kind="text", content=full)


def run_openai_compatible_chat_impl(
    provider: ModelProvider,
    session: Session,
    context: Context,
    message: str,
    *,
    skill_registry: Mapping[str, Any] | None = None,
    prompt_cache: PromptCache | None = None,
) -> ModelOutput:
    """
    调用 OpenAI 兼容 Chat Completions（DeepSeek、OpenAI、多数国内兼容网关等）。
    - api_key 来自 params.api_key_env 所指环境变量；
    - 出错时返回文本错误信息，而不是抛异常。
    """
    resolved = get_openai_chat_route(provider)
    if not resolved.ok or resolved.route is None:
        return ModelOutput(kind="text", content=resolved.error_message or "模型路由解析失败。")
    route = resolved.route

    api_key = os.environ.get(route.api_key_env)
    if not api_key:
        return ModelOutput(
            kind="text",
            content=f"模型 [{provider.id}] 未配置：请在环境变量 {route.api_key_env} 中设置 API Key。",
        )

    blocked = model_circuit_precheck(provider)
    if blocked is not None:
        return blocked

    throttled = model_rate_precheck(provider)
    if throttled is not None:
        return throttled

    base_url = route.base_url
    url = chat_completions_url(route)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    extra_h = provider.params.get("extra_headers")
    if isinstance(extra_h, Mapping):
        for hk, hv in extra_h.items():
            if isinstance(hk, str) and isinstance(hv, str) and hk.strip():
                headers[hk.strip()] = hv
    max_history = int(provider.params.get("max_history", 10))
    iso = bool(context.meta.get("context_isolation_enabled", True))
    history_messages = _render_history_messages_for_model_plain(context, max_history=max_history)
    current_user_openai: str | list[dict[str, Any]] | None = None
    if session.messages and session.messages[-1].role == "user":
        last_u = session.messages[-1]
        if message_uses_openai_multimodal_user_content(last_u):
            current_user_openai = openai_user_message_payload(last_u, session_meta=context.meta)

    if isinstance(current_user_openai, list):
        history_messages = _drop_trailing_user_if_matches_current(history_messages, message)
        if iso:
            history_messages = _isolate_history_plain_messages(history_messages)
        finalized = _finalize_openai_user_message_blocks(
            [dict(x) for x in current_user_openai if isinstance(x, Mapping)],
            provider=provider,
            session=session,
            context=context,
            iso=iso,
        )
        history_messages.append({"role": "user", "content": finalized})
    else:
        # Core 在调用模型前已将本轮 user 写入 session，context.messages 末尾已含本条；
        # 若再追加会与 OpenAI 兼容 API 中「当前问」重复，损害多轮与单轮质量。
        user_input_resolved = message
        if isinstance(current_user_openai, str) and current_user_openai.strip():
            user_input_resolved = current_user_openai
        user_message_for_model = _resolve_user_message_for_model(
            provider=provider,
            session=session,
            context=context,
            user_input=user_input_resolved,
        )
        history_messages = _drop_trailing_user_if_matches_current(history_messages, message)
        if iso:
            history_messages = _isolate_history_plain_messages(history_messages)
        user_content = user_message_for_model
        if iso and str(user_content).strip():
            phase = str(context.meta.get("phase", "") or "")
            raw_u = str(user_content).strip()
            if phase == "post_tool":
                lt = context.meta.get("last_tool")
                src_raw: str | None = None
                if isinstance(lt, dict):
                    v = lt.get("source")
                    if isinstance(v, str):
                        src_raw = v
                user_content = format_isolated_zone(
                    "tool_result",
                    raw_u,
                    source=tool_execution_source_token(src_raw),
                    trust=trust_for_tool_result_source(src_raw),
                )
            else:
                user_content = format_isolated_zone(
                    "user",
                    raw_u,
                    source="user_input",
                    trust="medium",
                )
        history_messages.append({"role": "user", "content": user_content})

    system_prompt = _resolve_system_prompt(
        provider=provider,
        session=session,
        context=context,
        skill_registry=skill_registry or {},
        prompt_cache=prompt_cache,
    )

    messages_payload: list[dict[str, Any]] = []
    if isinstance(system_prompt, str) and system_prompt.strip():
        sys_body = system_prompt.strip()
        if iso:
            sys_body = format_isolated_zone(
                "system",
                sys_body,
                source="prompt_config",
                trust="high",
            )
        messages_payload.append({"role": "system", "content": sys_body})
    mem = getattr(context, "memory_context_block", None)
    if isinstance(mem, str) and mem.strip():
        messages_payload.append({"role": "system", "content": mem.strip()})
    messages_payload.extend(history_messages)

    payload: dict[str, Any] = {
        "model": route.model,
        "messages": messages_payload,
    }
    tools = provider.params.get("tools")
    if isinstance(tools, list) and tools:
        payload["tools"] = tools
    tc = provider.params.get("tool_choice")
    if tc is not None:
        payload["tool_choice"] = tc

    timeout_f = route.timeout_seconds

    delta_cb = get_model_stream_delta()
    tools_nonempty = isinstance(tools, list) and bool(tools)
    stream_tools_ok = _provider_stream_with_tools_enabled(provider)
    use_stream = (
        delta_cb is not None
        and _provider_stream_enabled(provider)
        and (not tools_nonempty or stream_tools_ok)
    )

    try:
        _log.debug("model.openai_compatible.chat provider_id=%s stream=%s", provider.id, use_stream)
        if use_stream:
            result = _post_openai_chat_stream(
                provider=provider,
                base_url=base_url,
                url=url,
                headers=headers,
                payload=payload,
                timeout_f=timeout_f,
                on_delta=delta_cb,
                tools_in_payload=tools_nonempty and stream_tools_ok,
            )
        else:
            with _chat_http_client(provider, base_url=base_url, timeout_f=timeout_f) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                result = ModelOutput(kind="text", content=f"模型 [{provider.id}] 返回结果为空。")
            else:
                first = choices[0]
                msg = first.get("message") or {}
                if not isinstance(msg, dict):
                    msg = {}
                result = openai_message_to_model_output(msg, provider_id=provider.id)
    except Exception as exc:  # 网络/解析等异常：返回错误文本，避免崩溃
        result = ModelOutput(kind="text", content=f"模型 [{provider.id}] 调用失败：{exc!r}")
    model_circuit_record(provider, result)
    return result


def _finalize_openai_user_message_blocks(
    blocks: list[dict[str, Any]],
    *,
    provider: ModelProvider,
    session: Session,
    context: Context,
    iso: bool,
) -> list[dict[str, Any]]:
    """多模态 user 块：逐段规范化文本并套关卡②（与纯文本 user 路径语义对齐）。未配置 user_prompt_profiles 合并（MVP）。"""
    phase = str(context.meta.get("phase", "") or "")
    lt = context.meta.get("last_tool")
    src_raw: str | None = None
    if isinstance(lt, dict):
        v = lt.get("source")
        if isinstance(v, str):
            src_raw = v
    out: list[dict[str, Any]] = []
    for b in blocks:
        t = str(b.get("type", "")).strip()
        if t != "text":
            out.append(dict(b))
            continue
        raw_t = b.get("text")
        text_in = raw_t if isinstance(raw_t, str) else str(raw_t)
        norm = _normalize_user_input_for_template(user_input=text_in, provider=provider)
        if iso and norm.strip():
            if phase == "post_tool":
                norm = format_isolated_zone(
                    "tool_result",
                    norm.strip(),
                    source=tool_execution_source_token(src_raw),
                    trust=trust_for_tool_result_source(src_raw),
                )
            else:
                norm = format_isolated_zone(
                    "user",
                    norm.strip(),
                    source="user_input",
                    trust="medium",
                )
        out.append({"type": "text", "text": norm})
    return out


def _drop_trailing_user_if_matches_current(
    history_messages: list[dict[str, Any]],
    current_user_text: str,
) -> list[dict[str, Any]]:
    cur = current_user_text.strip()
    if not history_messages or not cur:
        return history_messages
    last = history_messages[-1]
    if last.get("role") != "user":
        return history_messages
    content = last.get("content")
    if isinstance(content, list):
        return history_messages
    last_content = str(content).strip()
    if last_content == cur:
        return history_messages[:-1]
    return history_messages


def _render_history_messages_for_model_plain(context: Context, *, max_history: int) -> list[dict[str, Any]]:
    """
    将 Context.messages 渲染为适合 LLM 输入的 history 列表。
    - 默认：纯文本 ``content``（关卡② 由 ``_isolate_history_plain_messages`` 后补）。
    - 历史 **user** 若含 ``Part(image_url)`` 等：``content`` 为 OpenAI 块数组（与当前轮多模态一致）。
    - 末尾「当前轮」多模态 user 在渲染前剔除，避免与 ``run_openai_compatible_chat_impl`` 末尾追加重复。
    - 含 ``openai_v1`` 片段时原样展开为 assistant/tool 等元素。
    """
    history: list[dict[str, Any]] = []
    messages = list(context.messages)
    if max_history > 0 and len(messages) > max_history:
        messages = messages[-max_history:]

    if (
        messages
        and messages[-1].role == "user"
        and message_uses_openai_multimodal_user_content(messages[-1])
    ):
        messages = messages[:-1]

    for m in messages:
        for part in m.parts:
            c = part.content
            if isinstance(c, dict) and c.get("_format") == OPENAI_V1 and isinstance(c.get("message"), dict):
                history.append(dict(c["message"]))
                break
        else:
            if m.role == "user":
                u_payload = openai_user_message_payload(m, session_meta=context.meta)
                if isinstance(u_payload, list):
                    history.append({"role": "user", "content": u_payload})
                    continue
                if isinstance(u_payload, str) and u_payload.strip():
                    history.append({"role": "user", "content": u_payload})
                    continue
                continue
            text = render_message_plain_text(m)
            if not text:
                continue
            history.append(
                {
                    "role": m.role,
                    "content": text,
                }
            )
    return _sanitize_openai_history_messages(history)


def _isolate_history_plain_messages(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """对已由 `_render_history_messages_for_model_plain` 产出且已去重的 history 加关卡② 包装。"""
    out: list[dict[str, Any]] = []
    for msg in history:
        role = str(msg.get("role", "")).strip()
        content = msg.get("content")
        if isinstance(content, list) and role == "user":
            new_blocks: list[dict[str, Any]] = []
            for b in content:
                if not isinstance(b, Mapping):
                    continue
                bd = dict(b)
                t = str(bd.get("type", "")).strip()
                if t != "text":
                    new_blocks.append(bd)
                    continue
                tx = bd.get("text")
                raw = tx if isinstance(tx, str) else str(tx)
                if not raw.strip():
                    new_blocks.append(bd)
                    continue
                wrapped = format_isolated_zone(
                    "history_user",
                    raw.strip(),
                    source="session_history",
                    trust="medium",
                )
                new_blocks.append({"type": "text", "text": wrapped})
            out.append({**msg, "content": new_blocks})
            continue
        if not isinstance(content, str) or not content.strip():
            out.append(msg)
            continue
        text = content.strip()
        if role == "tool":
            text = format_isolated_zone(
                "history_tool",
                text,
                source="session_history",
                trust="low",
            )
        elif role == "user":
            text = format_isolated_zone(
                "history_user",
                text,
                source="session_history",
                trust="medium",
            )
        elif role == "assistant":
            text = format_isolated_zone(
                "history_assistant",
                text,
                source="session_history",
                trust="medium",
            )
        out.append({**msg, "content": text})
    return out


def _sanitize_openai_history_messages(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    防止裁剪后出现“孤儿 tool 消息”导致 OpenAI 兼容接口 400：
    - 保留普通 user/assistant/system
    - 对 role=tool：仅当其 tool_call_id 在已出现的 assistant.tool_calls.id 集合中时保留
    """
    seen_tool_call_ids: set[str] = set()
    sanitized: list[dict[str, Any]] = []
    for msg in history:
        role = str(msg.get("role", "")).strip()
        if role == "assistant":
            raw_calls = msg.get("tool_calls")
            if isinstance(raw_calls, list):
                for tc in raw_calls:
                    if not isinstance(tc, Mapping):
                        continue
                    tc_id = tc.get("id")
                    if isinstance(tc_id, str) and tc_id.strip():
                        seen_tool_call_ids.add(tc_id.strip())
            sanitized.append(msg)
            continue
        if role == "tool":
            tc_id = msg.get("tool_call_id")
            if not isinstance(tc_id, str) or not tc_id.strip():
                continue
            if tc_id.strip() in seen_tool_call_ids:
                sanitized.append(msg)
            continue
        sanitized.append(msg)
    return sanitized


def _resolve_system_prompt(
    *,
    provider: ModelProvider,
    session: Session,
    context: Context,
    skill_registry: Mapping[str, Any],
    prompt_cache: PromptCache | None,
) -> str | None:
    """
    提示词优先级：
    1) prompt_profiles[profile][strategy]
    2) prompt_profiles[profile]["default"]
    3) prompt_profiles["default"][strategy]
    4) prompt_profiles["default"]["default"]

    最后在合并活跃技能块（及 prompt_cache）之后执行 ``prompt_strategy_ref``（provider.params 覆盖 ContextVar 默认）。
    """
    selected_profile = (session.config.prompt_profile or "default").strip() or "default"
    selected_strategy = (session.config.prompt_strategy or "default").strip() or "default"
    profile_text = _resolve_prompt_profile_text(provider.params, selected_profile, selected_strategy)
    merged: str | None
    if profile_text is not None:
        base_prompt = _render_prompt_template(
            template=profile_text,
            provider=provider,
            session=session,
            context=context,
            selected_profile=selected_profile,
            selected_strategy=selected_strategy,
        )
        merged = _apply_active_skills_to_system_prompt(
            base_prompt=base_prompt,
            session=session,
            skill_registry=skill_registry,
            prompt_cache=prompt_cache,
            provider_id=provider.id,
            selected_profile=selected_profile,
            selected_strategy=selected_strategy,
        )
    else:
        merged = None

    ref = str(provider.params.get("prompt_strategy_ref") or "").strip() or get_default_prompt_strategy_ref()
    return run_prompt_strategy(
        ref,
        system_prompt=merged,
        provider=provider,
        session=session,
        context=context,
        skill_registry=skill_registry,
    )


def _apply_active_skills_to_system_prompt(
    *,
    base_prompt: str,
    session: Session,
    skill_registry: Mapping[str, Any],
    prompt_cache: PromptCache | None,
    provider_id: str,
    selected_profile: str,
    selected_strategy: str,
) -> str:
    skill_ids = [s.strip() for s in session.config.skills if isinstance(s, str) and s.strip()]
    if not skill_ids:
        return base_prompt
    skill_block = _render_active_skill_block(skill_ids=skill_ids, skill_registry=skill_registry)
    if not skill_block:
        return base_prompt
    merged = f"{base_prompt}\n\n<active_skills>\n{skill_block}\n</active_skills>"
    if prompt_cache is None:
        return merged
    cache_key = _make_prompt_cache_key(
        provider_id=provider_id,
        profile=selected_profile,
        strategy=selected_strategy,
        base_prompt=base_prompt,
        skill_block=skill_block,
    )
    hit = prompt_cache.get(cache_key)
    if hit is not None:
        return hit
    prompt_cache.set(cache_key, merged)
    return merged


def _render_active_skill_block(*, skill_ids: list[str], skill_registry: Mapping[str, Any]) -> str:
    chunks: list[str] = []
    for sid in skill_ids:
        spec = skill_registry.get(sid)
        if spec is None:
            continue
        enabled = bool(getattr(spec, "enabled", True))
        if not enabled:
            continue
        index = str(getattr(spec, "index", sid))
        title = str(getattr(spec, "title", sid))
        content = str(getattr(spec, "content", "")).strip()
        if not content:
            continue
        chunks.append(f"[{index}] {title}\n{content}")
    return "\n\n".join(chunks)


def _make_prompt_cache_key(*, provider_id: str, profile: str, strategy: str, base_prompt: str, skill_block: str) -> str:
    raw = f"{provider_id}|{profile}|{strategy}|{base_prompt}|{skill_block}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"system_prompt:{digest}"


def _resolve_prompt_profile_text(params: Mapping[str, Any], profile: str, strategy: str = "default") -> str | None:
    return _resolve_profile_text(params=params, root_key="prompt_profiles", profile=profile, strategy=strategy)


def _resolve_profile_text(
    *,
    params: Mapping[str, Any],
    root_key: str,
    profile: str,
    strategy: str = "default",
) -> str | None:
    node = params.get(root_key)
    if not isinstance(node, Mapping):
        return None

    def _as_text(value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _from_profile(value: Any, wanted_strategy: str) -> str | None:
        if not isinstance(value, Mapping):
            return None
        selected = _as_text(value.get(wanted_strategy))
        if selected is not None:
            return selected
        return _as_text(value.get("default"))

    resolved = _from_profile(node.get(profile), strategy)
    if resolved is not None:
        return resolved
    resolved = _from_profile(node.get("default"), strategy)
    if resolved is not None:
        return resolved
    return None


def _render_prompt_template(
    *,
    template: str,
    provider: ModelProvider,
    session: Session,
    context: Context,
    selected_profile: str,
    selected_strategy: str,
) -> str:
    return _render_prompt_template_generic(
        template=template,
        provider=provider,
        session=session,
        context=context,
        selected_profile=selected_profile,
        selected_strategy=selected_strategy,
        vars_key="prompt_vars",
        vars_env_key="prompt_vars_env",
        vars_strict_key="prompt_vars_strict",
    )


def _render_prompt_template_generic(
    *,
    template: str,
    provider: ModelProvider,
    session: Session,
    context: Context,
    selected_profile: str,
    selected_strategy: str,
    vars_key: str,
    vars_env_key: str,
    vars_strict_key: str,
    extra_vars: Mapping[str, Any] | None = None,
) -> str:
    """
    将资源模板渲染为最终 system prompt。
    变量来源（后者覆盖前者）：
    1) provider.params.prompt_vars（静态配置）
    2) provider.params.prompt_vars_env（从环境变量注入）
    3) 内建运行时变量
    """
    vars_map: dict[str, Any] = {}
    configured = provider.params.get(vars_key)
    if isinstance(configured, Mapping):
        for k, v in configured.items():
            if isinstance(k, str) and k.strip():
                vars_map[k.strip()] = v

    env_map = provider.params.get(vars_env_key)
    if isinstance(env_map, Mapping):
        for var_name, env_name in env_map.items():
            if not isinstance(var_name, str) or not var_name.strip():
                continue
            if not isinstance(env_name, str) or not env_name.strip():
                continue
            env_value = os.environ.get(env_name.strip())
            if env_value is not None:
                vars_map[var_name.strip()] = env_value

    now = datetime.now(timezone.utc)
    vars_map.update(
        {
            "provider_id": provider.id,
            "model_id": session.config.model,
            "prompt_profile": selected_profile,
            "prompt_strategy": selected_strategy,
            "channel": session.channel,
            "user_id": session.user_id,
            "today": now.strftime("%Y-%m-%d"),
            "now_utc": now.isoformat(timespec="seconds"),
            "current_message": context.current,
        }
    )
    if isinstance(extra_vars, Mapping):
        vars_map.update(extra_vars)

    strict = bool(provider.params.get(vars_strict_key, False))
    try:
        rendered = template.format_map(_PromptSafeDict(vars_map, strict=strict))
    except Exception:
        return template
    return rendered.strip() if rendered.strip() else template


def _resolve_user_message_for_model(
    *,
    provider: ModelProvider,
    session: Session,
    context: Context,
    user_input: str,
) -> str:
    """
    用户提示词模板（可选）：
    - params.user_prompt_profiles: profile -> strategy -> template
    - params.user_prompt_vars / user_prompt_vars_env / user_prompt_vars_strict
    未配置用户模板时，使用稳定化后的用户输入。
    """
    selected_profile = (session.config.prompt_profile or "default").strip() or "default"
    selected_strategy = (session.config.prompt_strategy or "default").strip() or "default"
    normalized_input = _normalize_user_input_for_template(user_input=user_input, provider=provider)
    template = _resolve_profile_text(
        params=provider.params,
        root_key="user_prompt_profiles",
        profile=selected_profile,
        strategy=selected_strategy,
    )
    if template is None:
        return normalized_input
    return _render_prompt_template_generic(
        template=template,
        provider=provider,
        session=session,
        context=context,
        selected_profile=selected_profile,
        selected_strategy=selected_strategy,
        vars_key="user_prompt_vars",
        vars_env_key="user_prompt_vars_env",
        vars_strict_key="user_prompt_vars_strict",
        extra_vars={"user_input": normalized_input, "user_input_raw": user_input},
    )


def _normalize_user_input_for_template(*, user_input: str, provider: ModelProvider) -> str:
    """
    用户输入稳定化：
    1) 统一换行与去除 NUL 字符
    2) 可选字符上限（params.user_input_max_chars）
    """
    text = str(user_input).replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    raw_limit = provider.params.get("user_input_max_chars", 0)
    limit = int(raw_limit) if isinstance(raw_limit, (int, float, str)) and str(raw_limit).strip().isdigit() else 0
    if limit <= 0 or len(text) <= limit:
        return text
    suffix = " ...(truncated)"
    if limit <= len(suffix):
        return text[:limit]
    return text[: max(0, limit - len(suffix))] + suffix


class _PromptSafeDict(dict[str, Any]):
    def __init__(self, data: Mapping[str, Any], *, strict: bool) -> None:
        super().__init__(data)
        self._strict = strict

    def __missing__(self, key: str) -> Any:
        if self._strict:
            raise KeyError(key)
        return "{" + key + "}"


_TOOL_RESULT_ZONE_BODY = re.compile(
    r"<!-- pompeii:zone-begin name=tool_result source=[a-zA-Z0-9_.-]+ trust=[a-zA-Z0-9_.-]+ -->\n"
    r"(?P<body>.*?)\n"
    r"<!-- pompeii:zone-end name=tool_result -->",
    re.DOTALL,
)


def _unwrap_tool_result_zone_for_parse(current: str) -> str:
    """若组装部对 post-tool current 套了关卡② 分区，取出内层 ``tool <name> -> …`` 供解析。"""
    m = _TOOL_RESULT_ZONE_BODY.search(current)
    return m.group("body").strip() if m else current


def _maybe_make_tool_first_reply(*, session: Session, context: Context, provider: ModelProvider | None) -> str | None:
    """
    tool_first 策略下，工具结果回流轮次优先直出工具结论，避免模型二次长解释。
    触发条件：prompt_strategy=tool_first 且 context.intent is None 且 current 形如 "tool <name> -> <payload>"
    （或同等内容被 ``tool_result`` 关卡② 分区包裹）。
    """
    if (session.config.prompt_strategy or "").strip() != "tool_first":
        return None
    if context.intent is not None:
        return None
    prefix = "tool "
    marker = " -> "
    current = _unwrap_tool_result_zone_for_parse(context.current)
    if not current.startswith(prefix) or marker not in current:
        return None
    head, payload_raw = current[len(prefix) :].split(marker, 1)
    tool_name = head.strip()
    payload_raw = payload_raw.strip()
    if not tool_name or not payload_raw:
        return None
    if not _is_tool_first_allowed(tool_name=tool_name, provider=provider, strategy=session.config.prompt_strategy):
        return None
    mode = _resolve_tool_result_render_mode(provider=provider, strategy=session.config.prompt_strategy)
    try:
        payload = json.loads(payload_raw)
    except Exception:
        payload = payload_raw
    if mode == "raw":
        return payload_raw
    result = _extract_tool_result(payload)
    rendered = _render_tool_result_short(tool_name=tool_name, result=result)
    if mode == "short_with_reason":
        return f"{rendered}\n(source: {tool_name})"
    return rendered


def _render_tool_result_short(*, tool_name: str, result: Any) -> str:
    if isinstance(result, (str, int, float, bool)):
        return str(result)
    if result is None:
        return f"{tool_name} done"
    try:
        return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
    except TypeError:
        return str(result)


def _resolve_tool_result_render_mode(
    *,
    provider: ModelProvider | None,
    strategy: str,
) -> Literal["raw", "short", "short_with_reason"]:
    default_mode: Literal["raw", "short", "short_with_reason"] = "short"
    if provider is None:
        return default_mode
    node = provider.params.get("tool_result_render")
    if isinstance(node, Mapping):
        chosen = node.get(strategy, node.get("default", default_mode))
        return _normalize_tool_result_mode(chosen, default=default_mode)
    return default_mode


def _is_tool_first_allowed(*, tool_name: str, provider: ModelProvider | None, strategy: str) -> bool:
    """
    控制 tool_first 触发范围。
    配置项：params.tool_first_tools
    - 缺省：允许所有工具
    - mapping：按 strategy 取 list[str]（含 default 回退）
    """
    if provider is None:
        return True
    node = provider.params.get("tool_first_tools")
    if node is None:
        return True

    def _contains(value: Any, name: str) -> bool:
        if not isinstance(value, list):
            return False
        names = [str(x).strip() for x in value if isinstance(x, str) and str(x).strip()]
        return name in names

    if isinstance(node, Mapping):
        selected = node.get(strategy, node.get("default"))
        return _contains(selected, tool_name)
    return False


def _normalize_tool_result_mode(value: Any, *, default: Literal["raw", "short", "short_with_reason"]) -> Literal["raw", "short", "short_with_reason"]:
    if not isinstance(value, str):
        return default
    v = value.strip().lower()
    if v in ("raw", "short", "short_with_reason"):
        return v  # type: ignore[return-value]
    return default


def _extract_tool_result(payload: Any) -> Any:
    if isinstance(payload, dict):
        structured = payload.get("structuredContent")
        if isinstance(structured, dict) and "result" in structured:
            return structured.get("result")
        if "result" in payload:
            return payload.get("result")
        if "value" in payload:
            return payload.get("value")
        if "output" in payload:
            return payload.get("output")
    return payload

