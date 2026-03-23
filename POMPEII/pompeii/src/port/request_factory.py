from __future__ import annotations

from typing import Callable
from uuid import uuid4

from core import AgentRequest
from .input_events import UserMessageInput
from .intent_parser import parse_user_intent

RequestFactory = Callable[[UserMessageInput], AgentRequest]


def cli_request_factory(*, user_id: str = "cli-user", channel: str = "cli") -> RequestFactory:
    """
    CLI 的 raw -> AgentRequest 适配策略；在边界解析 UserIntent，下游只消费 intent。
    单进程 CLI 会话固定 request_id，便于对照日志。
    """

    def _factory(input_event: UserMessageInput) -> AgentRequest:
        intent = parse_user_intent(input_event.text)
        return AgentRequest(
            request_id="cli-1",
            user_id=user_id,
            channel=channel,
            payload=input_event.text,
            intent=intent,
        )

    return _factory


def session_request_factory(*, user_id: str, channel: str) -> RequestFactory:
    """
    带会话分区（user_id + channel）的入站消息：与 CLI 相同 intent 解析，
    每条 `UserMessageInput` 使用独立 `request_id`（HTTP/多连接场景便于追踪与排错）。
    """

    def _factory(input_event: UserMessageInput) -> AgentRequest:
        intent = parse_user_intent(input_event.text)
        return AgentRequest(
            request_id=str(uuid4()),
            user_id=user_id,
            channel=channel,
            payload=input_event.text,
            intent=intent,
        )

    return _factory


def http_request_factory(*, user_id: str = "http-user", channel: str = "http") -> RequestFactory:
    """
    HTTP JSON 入站（与 `session_request_factory` 等价默认参数）。
    Web 框架侧已解析 body；此处仅负责 intent 与 AgentRequest 字段。
    """

    return session_request_factory(user_id=user_id, channel=channel)


def ws_request_factory(*, user_id: str = "ws-user", channel: str = "ws") -> RequestFactory:
    """
    WebSocket 入站（预留）：语义同 HTTP，默认 channel 为 `ws`。
    """

    return session_request_factory(user_id=user_id, channel=channel)

