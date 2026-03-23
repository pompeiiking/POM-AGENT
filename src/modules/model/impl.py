from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Literal

import httpx

from core.session.openai_message_format import OPENAI_V1
from core.session.rule_summary import build_rule_summary_for_view, render_message_plain_text
from core.session.session import Message, Session
from core.user_intent import Chat, SystemHelp, SystemSummary, ToolAdd, ToolEcho, ToolPing, ToolTakePhoto
from modules.assembly.types import Context
from core.types import ToolCall
from .config import ModelProvider, ModelRegistry
from .interface import ModelModule, ModelOutput
from .openai_tool_parse import openai_message_to_model_output


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
    ) -> None:
        """
        registry：完整注册表，支持按会话切换 provider。
        provider：仅用于测试或单后端注入；若与 registry 同时传入，registry 优先。
        """
        self._registry = registry
        self._single_provider = provider

    def run(self, session: Session, context: Any) -> ModelOutput:
        if not isinstance(context, Context):
            return _run_legacy(context)

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
            return _run_openai_compatible_chat(provider=provider, session=session, context=context, message=message_text)

        return _make_text(message_text)


def _run_legacy(context: Any) -> ModelOutput:
    """非 Context 入参时的兼容路径（如测试或旧调用）。"""
    if isinstance(context, dict):
        message = context.get("current") or context.get("message") or ""
    else:
        message = str(context)
    return _make_text(str(message) if message else "")


def _make_text(message: str) -> ModelOutput:
    return ModelOutput(kind="text", content=f"[model] 收到: {message!r}")


def _make_help() -> ModelOutput:
    content = (
        "Pompeii-Agent 模型帮助：\n"
        "- 直接输入文本：普通对话（按 model_providers.yaml + session.model 选择后端）。\n"
        "- /help：显示可用指令。\n"
        "- /summary：根据最近对话生成规则摘要（不调用外部模型）。\n"
        "- /archive：将当前活跃会话标记为已归档（SQLite 时写入 session_archives；无活跃会话时提示）。\n"
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
    """将配置中的 backend 归一为内部实现分支。"""
    b = provider.backend.strip().lower()
    if b == "stub":
        return "stub"
    if b in ("openai_compatible", "deepseek"):
        return "openai_compatible"
    return "stub"


def _api_key_env_name(provider: ModelProvider) -> str | None:
    raw = provider.params.get("api_key_env")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if provider.backend.strip().lower() == "deepseek":
        return "DEEPSEEK_API_KEY"
    return None


def _run_openai_compatible_chat(provider: ModelProvider, session: Session, context: Context, message: str) -> ModelOutput:
    """
    调用 OpenAI 兼容 Chat Completions（DeepSeek、OpenAI、多数国内兼容网关等）。
    - api_key 来自 params.api_key_env 所指环境变量；legacy backend `deepseek` 默认 DEEPSEEK_API_KEY；
    - 出错时返回文本错误信息，而不是抛异常。
    """
    _ = session
    env_name = _api_key_env_name(provider)
    if not env_name:
        return ModelOutput(
            kind="text",
            content=(
                f"模型 [{provider.id}] 未配置 api_key_env：请在 model_providers.yaml 的 params 中设置 "
                "api_key_env（环境变量名），并在运行环境中导出对应 API Key。"
            ),
        )

    api_key = os.environ.get(env_name)
    if not api_key:
        return ModelOutput(
            kind="text",
            content=f"模型 [{provider.id}] 未配置：请在环境变量 {env_name} 中设置 API Key。",
        )

    default_base = "https://api.deepseek.com" if provider.backend.strip().lower() == "deepseek" else "https://api.openai.com"
    base_url = str(provider.params.get("base_url", default_base)).rstrip("/")
    url = f"{base_url}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    max_history = int(provider.params.get("max_history", 10))
    history_messages = _render_history_messages_for_model(context, max_history=max_history)
    # Core 在调用模型前已将本轮 user 写入 session，context.messages 末尾已含本条；
    # 若再追加会与 OpenAI 兼容 API 中「当前问」重复，损害多轮与单轮质量。
    user_message_for_model = _resolve_user_message_for_model(
        provider=provider,
        session=session,
        context=context,
        user_input=message,
    )
    history_messages = _drop_trailing_user_if_matches_current(history_messages, message)
    history_messages.append({"role": "user", "content": user_message_for_model})

    system_prompt = _resolve_system_prompt(provider=provider, session=session, context=context)

    messages_payload: list[dict[str, str]] = []
    if isinstance(system_prompt, str) and system_prompt.strip():
        messages_payload.append({"role": "system", "content": system_prompt})
    messages_payload.extend(history_messages)

    default_model = "deepseek-chat" if provider.backend.strip().lower() == "deepseek" else "gpt-4o-mini"
    payload: dict[str, Any] = {
        "model": provider.params.get("model", default_model),
        "messages": messages_payload,
    }
    tools = provider.params.get("tools")
    if isinstance(tools, list) and tools:
        payload["tools"] = tools
    tc = provider.params.get("tool_choice")
    if tc is not None:
        payload["tool_choice"] = tc

    timeout = provider.params.get("timeout", 30.0)
    timeout_f = float(timeout) if isinstance(timeout, (int, float)) else 30.0

    try:
        with httpx.Client(timeout=timeout_f) as client:
            resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return ModelOutput(kind="text", content=f"模型 [{provider.id}] 返回结果为空。")
        first = choices[0]
        msg = first.get("message") or {}
        if not isinstance(msg, dict):
            msg = {}
        return openai_message_to_model_output(msg, provider_id=provider.id)
    except Exception as exc:  # 网络/解析等异常：返回错误文本，避免崩溃
        return ModelOutput(kind="text", content=f"模型 [{provider.id}] 调用失败：{exc!r}")


def _drop_trailing_user_if_matches_current(
    history_messages: list[dict[str, str]],
    current_user_text: str,
) -> list[dict[str, str]]:
    cur = current_user_text.strip()
    if not history_messages or not cur:
        return history_messages
    last = history_messages[-1]
    if last.get("role") != "user":
        return history_messages
    last_content = str(last.get("content", "")).strip()
    if last_content == cur:
        return history_messages[:-1]
    return history_messages


def _render_history_messages_for_model(context: Context, *, max_history: int) -> list[dict[str, Any]]:
    """
    将 Context.messages 渲染为适合 LLM 输入的 history 列表。
    含 `openai_v1` 结构化片段时原样展开为 OpenAI `messages` 元素（assistant+tool_calls / tool）。
    """
    history: list[dict[str, Any]] = []
    messages = list(context.messages)
    if max_history > 0 and len(messages) > max_history:
        messages = messages[-max_history:]

    for m in messages:
        for part in m.parts:
            c = part.content
            if isinstance(c, dict) and c.get("_format") == OPENAI_V1 and isinstance(c.get("message"), dict):
                history.append(dict(c["message"]))
                break
        else:
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


def _resolve_system_prompt(*, provider: ModelProvider, session: Session, context: Context) -> str | None:
    """
    提示词优先级：
    1) prompt_profiles[profile][strategy]
    2) prompt_profiles[profile]["default"]
    3) prompt_profiles["default"][strategy]
    4) prompt_profiles["default"]["default"]
    5) legacy prompt_profiles["..."] = "text"（兼容旧格式）
    6) provider.params.system_prompt（兼容旧配置）
    """
    selected_profile = (session.config.prompt_profile or "default").strip() or "default"
    selected_strategy = (session.config.prompt_strategy or "default").strip() or "default"
    profile_text = _resolve_prompt_profile_text(provider.params, selected_profile, selected_strategy)
    if profile_text is not None:
        return _render_prompt_template(
            template=profile_text,
            provider=provider,
            session=session,
            context=context,
            selected_profile=selected_profile,
            selected_strategy=selected_strategy,
        )
    raw = provider.params.get("system_prompt")
    if isinstance(raw, str) and raw.strip():
        return _render_prompt_template(
            template=raw.strip(),
            provider=provider,
            session=session,
            context=context,
            selected_profile=selected_profile,
            selected_strategy=selected_strategy,
        )
    return None


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
        # 兼容旧格式：prompt_profiles.<profile> = "..."
        text = _as_text(value)
        if text is not None:
            return text
        if isinstance(value, Mapping):
            # 新格式：prompt_profiles.<profile>.<strategy> = "..."
            selected = _as_text(value.get(wanted_strategy))
            if selected is not None:
                return selected
            return _as_text(value.get("default"))
        return None

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
    未配置时保留原始用户输入，保证兼容。
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


def _maybe_make_tool_first_reply(*, session: Session, context: Context, provider: ModelProvider | None) -> str | None:
    """
    tool_first 策略下，工具结果回流轮次优先直出工具结论，避免模型二次长解释。
    触发条件：prompt_strategy=tool_first 且 context.intent is None 且 current 形如 "tool <name> -> <payload>"。
    """
    if (session.config.prompt_strategy or "").strip() != "tool_first":
        return None
    if context.intent is not None:
        return None
    prefix = "tool "
    marker = " -> "
    current = context.current
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
    # 兼容旧/简写格式：tool_result_render: "short"
    if isinstance(node, str):
        return _normalize_tool_result_mode(node, default=default_mode)
    # 新格式：tool_result_render: { default: "...", tool_first: "..." }
    if isinstance(node, Mapping):
        chosen = node.get(strategy, node.get("default", default_mode))
        return _normalize_tool_result_mode(chosen, default=default_mode)
    return default_mode


def _is_tool_first_allowed(*, tool_name: str, provider: ModelProvider | None, strategy: str) -> bool:
    """
    控制 tool_first 触发范围。
    配置项：params.tool_first_tools
    - 缺省：允许所有工具
    - list[str]：白名单
    - mapping：按 strategy 取 list[str]（含 default 回退）
    """
    if provider is None:
        return True
    node = provider.params.get("tool_first_tools")
    if node is None:
        return True

    def _contains(value: Any, name: str) -> bool:
        if not isinstance(value, list):
            return True
        names = [str(x).strip() for x in value if isinstance(x, str) and str(x).strip()]
        return name in names

    if isinstance(node, list):
        return _contains(node, tool_name)
    if isinstance(node, Mapping):
        selected = node.get(strategy, node.get("default"))
        return _contains(selected, tool_name)
    return True


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

