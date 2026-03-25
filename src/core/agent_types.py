from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .session.session import Session
from .types import DeviceRequest, ToolCall
from .user_intent import UserIntent


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
    reason: str | None = None
    pending_tool_call: ToolCall | None = None
    pending_device_request: DeviceRequest | None = None
    # reason=="delegate" 时由 Port 发出 DelegateEvent（子代理路由在网关中消费）
    delegate_target: str | None = None
    delegate_payload: str | None = None

