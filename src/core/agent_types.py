from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .session.session import Session
from .types import DeviceRequest, ToolCall
from .user_intent import UserIntent


class ResponseReason(str, Enum):
    """AgentResponse 终止原因枚举（str 子类，序列化时自动退化为字符串）。"""

    OK = "ok"
    # ── loop 治理 ──
    MAX_LOOPS = "max_loops"
    MAX_TOOL_CALLS = "max_tool_calls"
    REPEATED_TOOL_CALL = "repeated_tool_call"
    UNSUPPORTED_OUTPUT_KIND = "unsupported_output_kind"
    # ── 工具策略 ──
    TOOL_POLICY_DENIED = "tool_policy_denied"
    TOOL_CALL_MISSING = "tool_call_missing"
    CONFIRMATION_REQUIRED = "confirmation_required"
    DEVICE_REQUEST = "device_request"
    # ── 安全 ──
    SECURITY_GUARD_BLOCKED_INPUT = "security_guard_blocked_input"
    SECURITY_GUARD_MODEL_BLOCKED_INPUT = "security_guard_model_blocked_input"
    SECURITY_INPUT_TOO_LONG = "security_input_too_long"
    SECURITY_RATE_LIMITED = "security_rate_limited"
    # ── 资源访问 ──
    RESOURCE_ACCESS_DENIED = "resource_access_denied"
    RESOURCE_APPROVAL_REQUIRED = "resource_approval_required"
    # ── 委派 ──
    DELEGATE = "delegate"
    DELEGATE_TARGET_DENIED = "delegate_target_denied"


@dataclass(frozen=True)
class AgentRequest:
    request_id: str
    user_id: str
    channel: str
    payload: Any
    intent: UserIntent | None = None
    # 为真且 provider 开启 stream 时，模型部可对 OpenAI 兼容接口走流式；Port 注入 delta 回调（见 model_stream_context）
    stream: bool = False


@dataclass(frozen=True)
class AgentResponse:
    request_id: str
    session: Session
    reply_text: str | None
    error: str | None = None
    reason: ResponseReason | None = None
    pending_tool_call: ToolCall | None = None
    pending_device_request: DeviceRequest | None = None
    # reason==ResponseReason.DELEGATE 时由 Port 发出 DelegateEvent（子代理路由在网关中消费）
    delegate_target: str | None = None
    delegate_payload: str | None = None

