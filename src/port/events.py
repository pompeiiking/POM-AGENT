from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

from core.types import DeviceRequest, ToolCall


@dataclass(frozen=True, slots=True)
class StreamDeltaEvent:
    kind: Literal["stream_delta"]
    fragment: str


@dataclass(frozen=True, slots=True)
class ReplyEvent:
    kind: Literal["reply"]
    text: str


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    kind: Literal["error"]
    message: str
    reason: str | None


# 占位（表征构造）：对齐架构图纸中的 emit 语义，但暂不接入流程
@dataclass(frozen=True, slots=True)
class StatusEvent:
    kind: Literal["status"]
    status: str


@dataclass(frozen=True, slots=True)
class PolicyNoticeEvent:
    kind: Literal["policy_notice"]
    policy: str
    detail: str


@dataclass(frozen=True, slots=True)
class ConfirmationEvent:
    kind: Literal["confirmation"]
    prompt: str
    confirmation_id: str
    tool_call: ToolCall


@dataclass(frozen=True, slots=True)
class DelegateEvent:
    """子代理委派：由 `SystemDelegate` / `AgentResponse.reason=delegate` 触发，网关消费后路由。"""
    kind: Literal["delegate"]
    target: str
    payload: str


@dataclass(frozen=True, slots=True)
class DeviceRequestEvent:
    kind: Literal["device_request"]
    device_request_id: str
    request: DeviceRequest


PortEvent = Union[
    StreamDeltaEvent,
    ReplyEvent,
    ErrorEvent,
    StatusEvent,
    PolicyNoticeEvent,
    ConfirmationEvent,
    DelegateEvent,
    DeviceRequestEvent,
]

