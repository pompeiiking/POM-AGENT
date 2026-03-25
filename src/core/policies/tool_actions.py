from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from core.agent_types import AgentResponse
from core.policies.output_handlers import OutputStep
from core.session.message_factory import new_message
from core.session.openai_message_format import assistant_content_openai_v1, ensure_tool_call_id, tool_content_openai_v1
from core.session.session import Session
from core.session.session_manager import SessionManager
from core.types import DeviceRequest, ToolCall, ToolResult
from modules.assembly.interface import AssemblyModule
from modules.tools.interface import ToolModule


@dataclass(frozen=True)
class ToolContext:
    request_id: str
    session: Session
    context: Any
    tool_call: ToolCall


@dataclass(frozen=True)
class ToolDeps:
    session_manager: SessionManager
    assembly: AssemblyModule
    tools: ToolModule
    sanitize_tool_result: Callable[[Session, ToolResult], ToolResult] | None = None


def step_error(*, request_id: str, session: Session, context: Any, error: str, reason: str) -> OutputStep:
    return OutputStep(
        response=AgentResponse(
            request_id=request_id,
            session=session,
            reply_text=None,
            error=error,
            reason=reason,
        ),
        context=context,
    )


def step_device_request(
    *,
    deps: ToolDeps,
    tc: ToolContext,
    device_request: DeviceRequest,
) -> OutputStep:
    tc_tool = ensure_tool_call_id(tc.tool_call)
    deps.session_manager.append_message(
        tc.session.session_id,
        new_message(role="assistant", content=assistant_content_openai_v1(tc_tool), loop_index=0),
    )
    deps.session_manager.append_message(
        tc.session.session_id,
        new_message(
            role="tool",
            content=tool_content_openai_v1(
                tool_call_id=tc_tool.call_id or "",
                payload={
                    "tool_call": {"name": tc_tool.name, "arguments": dict(tc_tool.arguments)},
                    "device_request": {
                        "device": device_request.device,
                        "command": device_request.command,
                        "parameters": dict(device_request.parameters),
                    },
                },
            ),
            loop_index=0,
        ),
    )
    return OutputStep(
        response=AgentResponse(
            request_id=tc.request_id,
            session=tc.session,
            reply_text=None,
            error=None,
            reason="device_request",
            pending_tool_call=tc_tool,
            pending_device_request=device_request,
        ),
        context=tc.context,
    )


def step_execute_tool(*, deps: ToolDeps, tc: ToolContext) -> OutputStep:
    tc_tool = ensure_tool_call_id(tc.tool_call)
    deps.session_manager.append_message(
        tc.session.session_id,
        new_message(role="assistant", content=assistant_content_openai_v1(tc_tool), loop_index=0),
    )
    tool_result = deps.tools.execute(tc.session, tc_tool)
    if deps.sanitize_tool_result is not None:
        tool_result = deps.sanitize_tool_result(tc.session, tool_result)
    deps.session_manager.append_message(
        tc.session.session_id,
        new_message(
            role="tool",
            content=tool_content_openai_v1(
                tool_call_id=tc_tool.call_id or "",
                payload={"name": tool_result.name, "output": tool_result.output},
            ),
            loop_index=0,
        ),
    )
    return OutputStep(response=None, context=deps.assembly.apply_tool_result(tc.session, tool_result))

