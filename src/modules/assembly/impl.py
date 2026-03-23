from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from core.agent_types import AgentRequest
from core.session.session import Message, Session
from core.types import ToolResult
from .formatting import format_model_output_for_reply, intent_type_name, serialize_tool_output_for_current
from .interface import AssemblyModule
from .message_clip import clip_message_for_context
from .token_budget import trim_messages_to_approx_token_budget
from .types import Context


class AssemblyModuleImpl(AssemblyModule):
    def build_initial_context(self, session: Session, request: AgentRequest) -> Context:
        raw = _tail_messages(session.messages, limit=_assembly_tail_limit(session))
        clipped = _apply_assembly_message_budget(session, raw)
        messages = _apply_assembly_token_budget(session, clipped)
        current = str(request.payload)
        meta = {
            "phase": "user_turn",
            "user_id": request.user_id,
            "channel": request.channel,
            "session_id": session.session_id,
            "created_at": datetime.now().isoformat(),
            "intent_type": intent_type_name(request.intent),
        }
        return Context(messages=messages, current=current, intent=request.intent, meta=meta)

    def apply_tool_result(self, session: Session, tool_result: ToolResult) -> Context:
        raw = _tail_messages(session.messages, limit=_assembly_tail_limit(session))
        clipped = _apply_assembly_message_budget(session, raw)
        messages = _apply_assembly_token_budget(session, clipped)
        current = serialize_tool_output_for_current(tool_result.name, tool_result.output)
        meta = {
            "phase": "post_tool",
            "session_id": session.session_id,
            "updated_at": datetime.now().isoformat(),
            "last_tool": {
                "name": tool_result.name,
                "output": tool_result.output,
            },
        }
        return Context(messages=messages, current=current, intent=None, meta=meta)

    def format_final_reply(self, session: Session, model_output: Any) -> str:
        _ = session
        return format_model_output_for_reply(model_output)


def _assembly_tail_limit(session: Session) -> int:
    n = session.config.limits.assembly_tail_messages
    return max(1, min(200, n))


def _tail_messages(messages: Sequence[Message], *, limit: int) -> Sequence[Message]:
    if len(messages) <= limit:
        return list(messages)
    return list(messages[-limit:])


def _apply_assembly_message_budget(session: Session, messages: Sequence[Message]) -> Sequence[Message]:
    cap = session.config.limits.assembly_message_max_chars
    if cap <= 0:
        return list(messages)
    return [clip_message_for_context(m, cap) for m in messages]


def _apply_assembly_token_budget(session: Session, messages: Sequence[Message]) -> Sequence[Message]:
    budget = session.config.limits.assembly_approx_context_tokens
    return trim_messages_to_approx_token_budget(list(messages), budget)

