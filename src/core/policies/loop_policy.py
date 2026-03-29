from __future__ import annotations

import json
from dataclasses import dataclass

from core.agent_types import AgentResponse, ResponseReason
from core.kernel_config import KernelConfig
from core.session.session import Session
from core.types import ToolCall


@dataclass(frozen=True)
class LoopGovernance:
    max_loops: int
    max_tool_calls_per_run: int


def build_loop_governance(*, session: Session, kernel_config: KernelConfig) -> LoopGovernance:
    max_loops = min(session.config.limits.max_loops, kernel_config.core_max_loops)
    return LoopGovernance(
        max_loops=max_loops,
        max_tool_calls_per_run=kernel_config.max_tool_calls_per_run,
    )


def next_tool_calls(*, current: int, output_kind: str) -> int:
    bump = 1 if output_kind == "tool_call" else 0
    return current + bump


def tool_call_budget_decision(
    *,
    tool_calls: int,
    max_tool_calls: int,
    request_id: str,
    session: Session,
) -> AgentResponse | None:
    exceeded = tool_calls > max_tool_calls
    actions = {
        True: lambda: AgentResponse(
            request_id=request_id,
            session=session,
            reply_text=None,
            error="max tool calls exceeded",
            reason=ResponseReason.MAX_TOOL_CALLS,
        ),
        False: lambda: None,
    }
    return actions[exceeded]()


def max_loops_exceeded_response(*, request_id: str, session: Session) -> AgentResponse:
    return AgentResponse(
        request_id=request_id,
        session=session,
        reply_text=None,
        error="max loops exceeded",
        reason=ResponseReason.MAX_LOOPS,
    )


def tool_call_fingerprint(tool_call: ToolCall) -> str:
    """与参数 JSON 键序无关的稳定指纹，用于检测连续重复 tool_call（架构 ver0.4 §8.1）。"""
    payload = {"name": str(tool_call.name).strip(), "arguments": dict(tool_call.arguments)}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def repeated_tool_call_response(*, request_id: str, session: Session) -> AgentResponse:
    return AgentResponse(
        request_id=request_id,
        session=session,
        reply_text=None,
        error="检测到连续相同的 tool_call（名称与参数一致），已终止循环以防死循环",
        reason=ResponseReason.REPEATED_TOOL_CALL,
    )

