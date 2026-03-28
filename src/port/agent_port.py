from __future__ import annotations

# ============================================================
# port/agent_port.py
#
# 目标：把“外部交互”与“内核编排”隔离在 AgentPort 边界两侧。
# - runtime：驱动循环、选择 mode
# - port：raw -> AgentRequest、core.handle、AgentResponse -> PortEvent、emit 输出
# - core：会话 + loop 编排（不关心 CLI/HTTP/WS）
# ============================================================

from abc import ABC, abstractmethod
import threading
from threading import local
from typing import Callable, Iterable, Protocol
import sys
import sqlite3
import pickle
from pathlib import Path

from dataclasses import dataclass
from uuid import uuid4

import infra.logging_config  # noqa: F401 — LogRecord 注入 request_id / user_id / channel
from infra.request_context import bind_request_context, reset_request_context

from core import AgentCore, AgentRequest, AgentResponse, ResponseReason
from core.types import DeviceRequest, ToolCall, ToolResult
from .request_factory import RequestFactory, cli_request_factory, session_request_factory
from .events import (
    ConfirmationEvent,
    DelegateEvent,
    DeviceRequestEvent,
    ErrorEvent,
    PolicyNoticeEvent,
    PortEvent,
    ReplyEvent,
    StatusEvent,
    StreamDeltaEvent,
)
from .input_events import DeviceResultInput, PortInput, SystemCommandInput, UserMessageInput
import json


# HTTP 等场景：每次请求使用独立 Emitter，通过 thread-local 注入，避免为待确认状态新建 Port 实例
_emitter_ctx = local()


# ============================================================
# Ⅰ. Port 抽象：对外边界（图纸中的 AgentPort）
# ============================================================
class AgentPort(ABC):
    """
    Agent 对外边界抽象。

    职责：
    - 接收外部原始输入（HTTP / CLI / WS 等）
    - 转换为 AgentRequest
    - 调用 AgentCore.handle
    - 将 AgentResponse 转为端口事件（PortEvent）并 emit 到外部
    """

    @abstractmethod
    def handle(self, input_event: PortInput) -> None:
        ...


# ============================================================
# Ⅱ. 交互模式：只负责“如何读输入/如何退出”
# 说明：输出交给 PortEmitter（emit 体系），mode 不再负责 deliver。
# ============================================================
class InteractionMode(ABC):
    """
    交互模式抽象（CLI / HTTP / WS / ...）
    仅负责输入与退出规则，不关心装配与配置来源。
    """

    @abstractmethod
    def receive(self) -> str | None:
        ...

    @abstractmethod
    def should_exit(self, line: str) -> bool:
        ...


class CliMode(InteractionMode):
    """
    CLI 输入模式：
    - receive(): 从 stdin 读取一行（EOF 返回 None）
    - should_exit(): 决定退出指令
    """

    def receive(self) -> str | None:
        sys.stdout.write("you> ")
        sys.stdout.flush()
        line = sys.stdin.readline()
        if line == "":
            return None
        return line.rstrip("\n")

    def should_exit(self, line: str) -> bool:
        return line.strip().lower() in {"exit", "quit"}


# HttpMode 仅用于类型标识，不实现 stdin 循环 — HTTP 运行时已在 app/http_runtime.py 落地
class HttpMode(InteractionMode):
    """
    HTTP 由 Web 框架按请求驱动，不经过 `receive()` / `should_exit()` 循环。
    请使用 `app.http_runtime` 或自建 FastAPI/Starlette 路由，调用
    `GenericAgentPort.handle(..., user_id=..., channel=..., emitter=HttpEmitter())`。
    """

    def receive(self) -> str | None:
        raise NotImplementedError(
            "HttpMode does not use stdin; use HTTP handlers that call GenericAgentPort.handle()"
        )

    def should_exit(self, line: str) -> bool:
        raise NotImplementedError(
            "HttpMode does not use stdin; use HTTP handlers that call GenericAgentPort.handle()"
        )


# WsMode 仅用于类型标识，不实现 stdin 循环 — WS 运行时已在 app/http_runtime.py 的 WS /ws 端点落地
class WsMode(InteractionMode):
    """
    WebSocket 由连接/消息回调驱动；WS 服务端已在 `app/http_runtime.py` 的 `WS /ws` 端点实现，
    收包后调用 `GenericAgentPort.handle()`。
    """

    def receive(self) -> str | None:
        raise NotImplementedError(
            "WsMode does not use stdin; use WS handlers that call GenericAgentPort.handle()"
        )

    def should_exit(self, line: str) -> bool:
        raise NotImplementedError(
            "WsMode does not use stdin; use WS handlers that call GenericAgentPort.handle()"
        )


# ============================================================
# Ⅲ. Emitter：把 PortEvent 发射到外部（CLI/HTTP/WS）
# ============================================================
class PortEmitter(Protocol):
    def emit(self, event: PortEvent) -> None: ...


class CliEmitter:
    """
    CLI 输出实现：把事件渲染到 stdout。
    - 使用 dispatch map（event.kind -> handler）减少分支散落
    """

    def emit(self, event: PortEvent) -> None:
        handler = _cli_event_handlers().get(event.kind)
        render = handler if handler is not None else _render_unknown_event
        render(event)


# ============================================================
# Ⅳ. GenericAgentPort：端口适配器（raw -> request -> core -> events -> emit）
# ============================================================
class GenericAgentPort(AgentPort):
    """
    通用 Port，将交互模式与核心解耦：
    - mode: 注入不同交互模式（CLI/HTTP/WS）
    - core: 由装配层注入（配置来源也由装配层决定）
    """

    def __init__(
        self,
        mode: InteractionMode,
        core: AgentCore,
        request_factory: RequestFactory,
        emitter: PortEmitter,
        pending_state_sqlite_path: Path | None = None,
    ) -> None:
        self._mode = mode
        self._core = core
        self._request_factory = request_factory
        self._emitter = emitter
        self._pending_confirmation: dict[tuple[str, str], _PendingConfirmation] = {}
        self._pending_device_request: dict[tuple[str, str], _PendingDeviceRequest] = {}
        self._state_lock = threading.Lock()
        self._pending_db: sqlite3.Connection | None = None
        if pending_state_sqlite_path is not None:
            pending_state_sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self._pending_db = sqlite3.connect(str(pending_state_sqlite_path), check_same_thread=False)
            self._pending_db.execute(
                """
                CREATE TABLE IF NOT EXISTS port_pending_state (
                  kind TEXT NOT NULL,
                  user_id TEXT NOT NULL,
                  channel TEXT NOT NULL,
                  blob BLOB NOT NULL,
                  PRIMARY KEY(kind, user_id, channel)
                )
                """
            )
            self._pending_db.commit()

    def handle(
        self,
        input_event: PortInput,
        *,
        user_id: str | None = None,
        channel: str | None = None,
        emitter: PortEmitter | None = None,
    ) -> None:
        """
        user_id/channel：HTTP 等多连接场景下与 Session 一致，用于分区待确认/设备状态。
        emitter：若传入，本 handle 周期内 emit 使用该实例（如 HttpEmitter），否则用构造时 emitter（CLI）。
        """
        uid = "cli-user" if user_id is None else user_id
        ch = "cli" if channel is None else channel
        key = (uid, ch)
        if user_id is None and channel is None:
            rf = self._request_factory
        else:
            rf = session_request_factory(user_id=uid, channel=ch)

        if emitter is not None:
            _emitter_ctx.current = emitter
        try:
            pending = self._pending_confirmation_pop(key)
            if pending is not None:
                self._handle_confirmation_input(pending, input_event)
                return

            device_pending = self._pending_device_request_pop(key)
            if device_pending is not None:
                self._handle_device_result_input(device_pending, input_event)
                return

            user_message = _require_user_message(input_event)
            if user_message is None:
                tok = bind_request_context(request_id=str(uuid4()), user_id=uid, channel=ch)
                try:
                    for event in _invalid_input_events(input_event):
                        self.emit(event)
                finally:
                    reset_request_context(tok)
                return

            request = rf(user_message)
            tok = bind_request_context(
                request_id=request.request_id,
                user_id=request.user_id,
                channel=request.channel,
            )
            try:
                stream_cb = self._stream_delta_callback() if request.stream else None
                response = self._core.handle(request, stream_delta=stream_cb)
                self._handle_core_response(request, response)
            finally:
                reset_request_context(tok)
        finally:
            if emitter is not None:
                try:
                    delattr(_emitter_ctx, "current")
                except AttributeError:
                    pass

    def emit(self, event: PortEvent) -> None:
        target = getattr(_emitter_ctx, "current", None)
        if target is not None:
            target.emit(event)
            return
        self._emitter.emit(event)

    def _stream_delta_callback(self) -> Callable[[str], None]:
        def _cb(fragment: str) -> None:
            if fragment:
                self.emit(StreamDeltaEvent(kind="stream_delta", fragment=fragment))

        return _cb

    def _handle_core_response(self, request: AgentRequest, response: AgentResponse) -> None:
        sess_key = (request.user_id, request.channel)
        pending = _confirmation_pending(request, response)
        if pending is not None:
            self._pending_confirmation_put(sess_key, pending)
            self.emit(
                ConfirmationEvent(
                    kind="confirmation",
                    prompt=pending.prompt,
                    confirmation_id=pending.confirmation_id,
                    tool_call=pending.tool_call,
                )
            )
            return

        device_pending = _device_request_pending(request, response)
        if device_pending is not None:
            self._pending_device_request_put(sess_key, device_pending)
            self.emit(
                DeviceRequestEvent(
                    kind="device_request",
                    device_request_id=device_pending.device_request_id,
                    request=device_pending.device_request,
                )
            )
            return

        if response.reason == "delegate" and response.delegate_target:
            self.emit(
                DelegateEvent(
                    kind="delegate",
                    target=response.delegate_target,
                    payload=response.delegate_payload or "",
                )
            )

        for event in _response_to_events(response):
            self.emit(event)

    def _handle_confirmation_input(self, pending: _PendingConfirmation, input_event: PortInput) -> None:
        req = pending.request
        tok = bind_request_context(request_id=req.request_id, user_id=req.user_id, channel=req.channel)
        try:
            command = _as_system_command(input_event)
            parsed = _parse_confirmation_command(command)
            decision = _confirmation_decision(parsed, expected_id=pending.confirmation_id)
            action = _confirmation_actions(self).get(decision)
            run = action if action is not None else _confirmation_actions(self)["deny"]
            run(pending)
        finally:
            reset_request_context(tok)

    def _confirm_and_run(self, pending: _PendingConfirmation) -> None:
        self.emit(StatusEvent(kind="status", status="confirmation: approved"))
        stream_cb = self._stream_delta_callback() if pending.request.stream else None
        response = self._core.handle_confirmation_approved(
            pending.request, pending.tool_call, stream_delta=stream_cb
        )
        for event in _response_to_events(response):
            self.emit(event)

    def _deny(self, pending: _PendingConfirmation) -> None:
        self.emit(StatusEvent(kind="status", status="confirmation: denied"))

    def _handle_device_result_input(self, pending: _PendingDeviceRequest, input_event: PortInput) -> None:
        req = pending.request
        tok = bind_request_context(request_id=req.request_id, user_id=req.user_id, channel=req.channel)
        try:
            device_result = _require_device_result(input_event)
            if device_result is None:
                for event in _invalid_input_events(input_event):
                    self.emit(event)
                return

            parsed = _parse_device_result_json(device_result.payload)
            decision = _device_result_decision(parsed, expected_id=pending.device_request_id)
            action = _device_result_actions(self).get(decision)
            run = action if action is not None else _device_result_actions(self)["reject"]
            run(pending, parsed)
        finally:
            reset_request_context(tok)

    def _accept_device_result(self, pending: _PendingDeviceRequest, parsed: "_ParsedDeviceResult") -> None:
        self.emit(StatusEvent(kind="status", status="device_result: accepted"))
        tool_result = ToolResult(name=pending.tool_call.name, output=parsed.output, source="device")
        stream_cb = self._stream_delta_callback() if pending.request.stream else None
        response = self._core.handle_device_result(
            pending.request,
            tool_result=tool_result,
            tool_call_id=pending.tool_call.call_id,
            stream_delta=stream_cb,
        )
        for event in _response_to_events(response):
            self.emit(event)

    def _reject_device_result(self, pending: _PendingDeviceRequest, parsed: "_ParsedDeviceResult") -> None:
        self.emit(StatusEvent(kind="status", status="device_result: rejected"))
        self.emit(ErrorEvent(kind="error", message="invalid device_result", reason="device_result_invalid"))

    def _pending_confirmation_put(self, key: tuple[str, str], pending: "_PendingConfirmation") -> None:
        if self._pending_db is None:
            with self._state_lock:
                self._pending_confirmation[key] = pending
            return
        user_id, channel = key
        blob = sqlite3.Binary(pickle.dumps(pending))
        with self._state_lock:
            self._pending_db.execute(
                "INSERT OR REPLACE INTO port_pending_state(kind,user_id,channel,blob) VALUES(?,?,?,?)",
                ("confirmation", user_id, channel, blob),
            )
            self._pending_db.commit()

    def _pending_confirmation_pop(self, key: tuple[str, str]) -> "_PendingConfirmation | None":
        if self._pending_db is None:
            with self._state_lock:
                return self._pending_confirmation.pop(key, None)
        user_id, channel = key
        with self._state_lock:
            cur = self._pending_db.execute(
                "SELECT blob FROM port_pending_state WHERE kind=? AND user_id=? AND channel=?",
                ("confirmation", user_id, channel),
            )
            row = cur.fetchone()
            self._pending_db.execute(
                "DELETE FROM port_pending_state WHERE kind=? AND user_id=? AND channel=?",
                ("confirmation", user_id, channel),
            )
            self._pending_db.commit()
        if row is None:
            return None
        return pickle.loads(bytes(row[0]))

    def _pending_device_request_put(self, key: tuple[str, str], pending: "_PendingDeviceRequest") -> None:
        if self._pending_db is None:
            with self._state_lock:
                self._pending_device_request[key] = pending
            return
        user_id, channel = key
        blob = sqlite3.Binary(pickle.dumps(pending))
        with self._state_lock:
            self._pending_db.execute(
                "INSERT OR REPLACE INTO port_pending_state(kind,user_id,channel,blob) VALUES(?,?,?,?)",
                ("device", user_id, channel, blob),
            )
            self._pending_db.commit()

    def _pending_device_request_pop(self, key: tuple[str, str]) -> "_PendingDeviceRequest | None":
        if self._pending_db is None:
            with self._state_lock:
                return self._pending_device_request.pop(key, None)
        user_id, channel = key
        with self._state_lock:
            cur = self._pending_db.execute(
                "SELECT blob FROM port_pending_state WHERE kind=? AND user_id=? AND channel=?",
                ("device", user_id, channel),
            )
            row = cur.fetchone()
            self._pending_db.execute(
                "DELETE FROM port_pending_state WHERE kind=? AND user_id=? AND channel=?",
                ("device", user_id, channel),
            )
            self._pending_db.commit()
        if row is None:
            return None
        return pickle.loads(bytes(row[0]))


# ============================================================
# Ⅳ-a. 确认状态机（端口层维护）
# ============================================================
@dataclass(frozen=True, slots=True)
class _PendingConfirmation:
    request: AgentRequest
    prompt: str
    confirmation_id: str
    tool_call: ToolCall


@dataclass(frozen=True, slots=True)
class _PendingDeviceRequest:
    request: AgentRequest
    device_request_id: str
    device_request: DeviceRequest
    tool_call: ToolCall


def _device_request_pending(request: AgentRequest, response: AgentResponse) -> _PendingDeviceRequest | None:
    needs = response.reason == "device_request" and response.pending_device_request is not None and response.pending_tool_call is not None
    actions = {
        True: lambda: _PendingDeviceRequest(
            request=request,
            device_request_id=uuid4().hex,
            device_request=response.pending_device_request,
            tool_call=response.pending_tool_call,
        ),
        False: lambda: None,
    }
    return actions[needs]()


def _confirmation_pending(request: AgentRequest, response: AgentResponse) -> _PendingConfirmation | None:
    needs = response.reason == "confirmation_required"
    actions = {
        True: lambda: _PendingConfirmation(
            request=request,
            prompt="tool confirmation required",
            confirmation_id=uuid4().hex,
            tool_call=response.pending_tool_call,
        ),
        False: lambda: None,
    }
    return actions[needs]()

@dataclass(frozen=True, slots=True)
class _ParsedConfirmation:
    confirmation_id: str | None
    decision: str


def _parse_confirmation_command(raw: str) -> _ParsedConfirmation:
    stripped = raw.strip()
    if stripped.lower() == "yes":
        return _ParsedConfirmation(confirmation_id=None, decision="approve")
    if stripped.lower() == "no":
        return _ParsedConfirmation(confirmation_id=None, decision="deny")

    # 支持：/confirm <id> yes|no
    parts = stripped.split()
    if len(parts) == 3 and parts[0].lower() == "/confirm":
        return _ParsedConfirmation(confirmation_id=parts[1], decision=parts[2].lower())
    return _ParsedConfirmation(confirmation_id=None, decision="deny")


def _confirmation_decision(parsed: _ParsedConfirmation, *, expected_id: str) -> str:
    id_ok = parsed.confirmation_id is None or parsed.confirmation_id == expected_id
    actions = {
        True: lambda: "approve" if parsed.decision == "yes" or parsed.decision == "approve" else "deny",
        False: lambda: "deny",
    }
    return actions[id_ok]()


def _confirmation_actions(port: GenericAgentPort):
    return {
        "approve": port._confirm_and_run,
        "deny": port._deny,
    }


def _require_user_message(input_event: PortInput) -> UserMessageInput | None:
    if isinstance(input_event, UserMessageInput):
        return input_event
    return None


def _require_device_result(input_event: PortInput) -> DeviceResultInput | None:
    if isinstance(input_event, DeviceResultInput):
        return input_event
    return None


@dataclass(frozen=True, slots=True)
class _ParsedDeviceResult:
    device_request_id: str | None
    output: Any


def _parse_device_result_json(raw: str) -> _ParsedDeviceResult:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _ParsedDeviceResult(device_request_id=None, output={"raw": raw})
    if not isinstance(data, dict):
        return _ParsedDeviceResult(device_request_id=None, output={"data": data})
    return _ParsedDeviceResult(
        device_request_id=str(data.get("device_request_id")) if data.get("device_request_id") is not None else None,
        output=data.get("output"),
    )


def _device_result_decision(parsed: _ParsedDeviceResult, *, expected_id: str) -> str:
    id_ok = parsed.device_request_id == expected_id
    actions = {
        True: lambda: "accept",
        False: lambda: "reject",
    }
    return actions[id_ok]()


def _device_result_actions(port: GenericAgentPort):
    return {
        "accept": port._accept_device_result,
        "reject": port._reject_device_result,
    }


def _invalid_input_events(input_event: PortInput) -> Iterable[PortEvent]:
    label = type(input_event).__name__
    return (
        StatusEvent(kind="status", status=f"input_rejected: expected user_message, got {label}"),
        ErrorEvent(kind="error", message="invalid input kind for this port", reason="invalid_input_kind"),
    )


def _as_system_command(input_event: PortInput) -> str:
    if isinstance(input_event, SystemCommandInput):
        return input_event.text
    if isinstance(input_event, UserMessageInput):
        return input_event.text
    return ""


# ============================================================
# Ⅴ. AgentResponse -> PortEvent：把“内核返回”翻译成“端口事件”
# reply/error 为主路径；确认、设备请求、delegate 等在专用分支或扩展 builder 中落地。
# ============================================================
EventHandler = Callable[[PortEvent], None]


def _response_to_events(response: AgentResponse) -> Iterable[PortEvent]:
    key = _response_kind(response)
    builder = _response_event_builders().get(key)
    build = builder if builder is not None else _build_unknown_events
    return build(response)


def _response_kind(response: AgentResponse) -> str:
    return "error" if response.error is not None else "reply"


def _response_event_builders() -> dict[str, Callable[[AgentResponse], Iterable[PortEvent]]]:
    return {
        "reply": _build_reply_events,
        "error": _build_error_events,
    }


def _build_reply_events(response: AgentResponse) -> Iterable[PortEvent]:
    text = response.reply_text if response.reply_text is not None else ""
    if response.reason == ResponseReason.RESOURCE_APPROVAL_REQUIRED:
        return (
            PolicyNoticeEvent(
                kind="policy_notice",
                policy="resource_access",
                detail="operation requires approval",
            ),
            ReplyEvent(kind="reply", text=text),
        )
    return (ReplyEvent(kind="reply", text=text),)


def _build_error_events(response: AgentResponse) -> Iterable[PortEvent]:
    reason = response.reason
    message = response.error if response.error is not None else "unknown error"

    builder = _error_reason_event_builders().get(reason)
    build = builder if builder is not None else _build_plain_error_events
    return build(message=message, reason=reason)


def _error_reason_event_builders() -> dict[ResponseReason | None, Callable[..., Iterable[PortEvent]]]:
    return {
        ResponseReason.MAX_TOOL_CALLS: _build_max_tool_calls_events,
        ResponseReason.MAX_LOOPS: _build_max_loops_events,
        ResponseReason.REPEATED_TOOL_CALL: _build_repeated_tool_call_events,
        ResponseReason.UNSUPPORTED_OUTPUT_KIND: _build_unsupported_output_events,
        None: _build_plain_error_events,
    }


def _build_plain_error_events(*, message: str, reason: str | None) -> Iterable[PortEvent]:
    return (ErrorEvent(kind="error", message=message, reason=reason),)


def _build_max_tool_calls_events(*, message: str, reason: str | None) -> Iterable[PortEvent]:
    return (
        StatusEvent(kind="status", status="run_terminated: max_tool_calls_per_run exceeded"),
        ErrorEvent(kind="error", message=message, reason=reason),
    )


def _build_max_loops_events(*, message: str, reason: str | None) -> Iterable[PortEvent]:
    return (
        StatusEvent(kind="status", status="run_terminated: max_loops exceeded"),
        ErrorEvent(kind="error", message=message, reason=reason),
    )


def _build_repeated_tool_call_events(*, message: str, reason: str | None) -> Iterable[PortEvent]:
    return (
        StatusEvent(kind="status", status="run_terminated: repeated identical tool_call"),
        ErrorEvent(kind="error", message=message, reason=reason),
    )


def _build_unsupported_output_events(*, message: str, reason: str | None) -> Iterable[PortEvent]:
    return (
        StatusEvent(kind="status", status="run_terminated: unsupported model output kind"),
        ErrorEvent(kind="error", message=message, reason=reason),
    )


def _build_unknown_events(response: AgentResponse) -> Iterable[PortEvent]:
    return (ErrorEvent(kind="error", message="unknown response", reason=None),)


# ============================================================
# Ⅵ. CLI 事件渲染：PortEvent -> stdout
# ============================================================
def _cli_event_handlers() -> dict[str, EventHandler]:
    return {
        "reply": _render_reply_event,
        "error": _render_error_event,
        "status": _render_status_event,
        "policy_notice": _render_policy_notice_event,
        "confirmation": _render_confirmation_event,
        "delegate": _render_delegate_event,
        "device_request": _render_device_request_event,
    }


def _render_reply_event(event: PortEvent) -> None:
    if isinstance(event, ReplyEvent):
        sys.stdout.write(f"{event.text}\n")
        return
    _render_unknown_event(event)


def _render_error_event(event: PortEvent) -> None:
    if isinstance(event, ErrorEvent):
        sys.stdout.write(f"[ERROR] {event.message} (reason={event.reason})\n")
        return
    _render_unknown_event(event)


def _render_status_event(event: PortEvent) -> None:
    if isinstance(event, StatusEvent):
        sys.stdout.write(f"[STATUS] {event.status}\n")
        return
    _render_unknown_event(event)


def _render_policy_notice_event(event: PortEvent) -> None:
    if isinstance(event, PolicyNoticeEvent):
        sys.stdout.write(f"[POLICY] {event.policy}: {event.detail}\n")
        return
    _render_unknown_event(event)


def _render_confirmation_event(event: PortEvent) -> None:
    if isinstance(event, ConfirmationEvent):
        args = dict(event.tool_call.arguments)
        sys.stdout.write(f"[CONFIRMATION] {event.prompt}\n")
        sys.stdout.write(f"[CONFIRMATION] id={event.confirmation_id}\n")
        sys.stdout.write(f"[CONFIRMATION] tool={event.tool_call.name} args={args}\n")
        sys.stdout.write("[CONFIRMATION] 输入 yes/no，或使用：/confirm <id> yes|no\n")
        return
    _render_unknown_event(event)


def _render_delegate_event(event: PortEvent) -> None:
    if isinstance(event, DelegateEvent):
        payload = event.payload.replace("\n", "\\n")
        if len(payload) > 200:
            payload = payload[:200] + "…"
        sys.stdout.write(f"[DELEGATE] target={event.target!r} payload={payload!r}\n")
        return
    _render_unknown_event(event)


def _render_device_request_event(event: PortEvent) -> None:
    if isinstance(event, DeviceRequestEvent):
        sys.stdout.write("[DEVICE_REQUEST] 请在外部完成设备操作并回传\n")
        sys.stdout.write(f"[DEVICE_REQUEST] id={event.device_request_id}\n")
        sys.stdout.write(
            f"[DEVICE_REQUEST] device={event.request.device} command={event.request.command} params={dict(event.request.parameters)}\n"
        )
        sys.stdout.write(
            "[DEVICE_REQUEST] 回传格式：/device_result {\"device_request_id\":\"<id>\",\"output\":{...}}\n"
        )
        return
    _render_unknown_event(event)


def _render_unknown_event(event: PortEvent) -> None:
    sys.stdout.write("[ERROR] unknown event\n")

