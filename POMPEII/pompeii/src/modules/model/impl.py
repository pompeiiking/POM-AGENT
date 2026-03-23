from __future__ import annotations

import os
import uuid
from typing import Any, Literal

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
    history_messages = _drop_trailing_user_if_matches_current(history_messages, message)
    history_messages.append({"role": "user", "content": message})

    system_prompt = provider.params.get("system_prompt")

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
    return history

