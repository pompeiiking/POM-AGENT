from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from core.agent_types import AgentRequest
from core.memory.orchestrator import MemoryOrchestrator
from core.resource_access import (
    RESOURCE_LONG_TERM_MEMORY,
    RESOURCE_MULTIMODAL_IMAGE_URL,
    ResourceAccessEvaluator,
)
from core.session.multimodal_user_payload import context_current_string_from_payload
from core.session.session import Message, Session
from core.types import ToolResult
from core.user_intent import Chat
from .context_isolation import (
    format_isolated_zone,
    tool_execution_source_token,
    trust_for_tool_result_source,
)
from .formatting import format_model_output_for_reply, intent_type_name, serialize_tool_output_for_current
from .interface import AssemblyModule
from .message_clip import clip_message_for_context
from .token_budget import apply_three_tier_token_budget, make_message_token_counter
from .types import Context
from modules.tools.network_policy import ToolNetworkPolicyConfig


class AssemblyModuleImpl(AssemblyModule):
    def __init__(
        self,
        memory_orchestrator: MemoryOrchestrator | None = None,
        *,
        resource_access: ResourceAccessEvaluator | None = None,
        context_isolation_enabled: bool = True,
        tool_network_policy: ToolNetworkPolicyConfig | None = None,
    ) -> None:
        self._memory = memory_orchestrator
        self._resource_access = resource_access
        self._context_isolation_enabled = bool(context_isolation_enabled)
        self._tool_network_policy = tool_network_policy

    def build_initial_context(self, session: Session, request: AgentRequest) -> Context:
        raw = _tail_messages(session.messages, limit=_assembly_tail_limit(session))
        clipped = _apply_assembly_message_budget(session, raw)
        messages = _apply_assembly_token_budget(session, clipped)
        current = context_current_string_from_payload(request.payload)
        meta = _multimodal_url_meta(self._resource_access, self._tool_network_policy)
        meta = {
            **meta,
            "phase": "user_turn",
            "user_id": request.user_id,
            "channel": request.channel,
            "session_id": session.session_id,
            "created_at": datetime.now().isoformat(),
            "intent_type": intent_type_name(request.intent),
            "context_isolation_enabled": self._context_isolation_enabled,
        }
        mem_block = _build_memory_context_block(
            self._memory,
            user_id=request.user_id,
            channel=request.channel,
            request=request,
            resource_access=self._resource_access,
        )
        if self._context_isolation_enabled and mem_block and str(mem_block).strip():
            mem_block = format_isolated_zone(
                "memory",
                str(mem_block).strip(),
                source="long_term_memory",
                trust="medium",
            )
        return Context(
            messages=messages,
            current=current,
            intent=request.intent,
            meta=meta,
            memory_context_block=mem_block,
        )

    def apply_tool_result(self, session: Session, tool_result: ToolResult) -> Context:
        raw = _tail_messages(session.messages, limit=_assembly_tail_limit(session))
        clipped = _apply_assembly_message_budget(session, raw)
        messages = _apply_assembly_token_budget(session, clipped)
        raw_current = serialize_tool_output_for_current(tool_result.name, tool_result.output)
        if self._context_isolation_enabled:
            current = format_isolated_zone(
                "tool_result",
                raw_current,
                source=tool_execution_source_token(tool_result.source),
                trust=trust_for_tool_result_source(tool_result.source),
            )
        else:
            current = raw_current
        meta = _multimodal_url_meta(self._resource_access, self._tool_network_policy)
        meta = {
            **meta,
            "phase": "post_tool",
            "session_id": session.session_id,
            "updated_at": datetime.now().isoformat(),
            "context_isolation_enabled": self._context_isolation_enabled,
            "last_tool": {
                "name": tool_result.name,
                "output": tool_result.output,
                "source": getattr(tool_result, "source", None),
            },
        }
        return Context(
            messages=messages,
            current=current,
            intent=None,
            meta=meta,
            memory_context_block=None,
        )

    def format_final_reply(self, session: Session, model_output: Any) -> str:
        _ = session
        return format_model_output_for_reply(model_output)


def _multimodal_url_meta(
    resource_access: ResourceAccessEvaluator | None,
    network_policy: ToolNetworkPolicyConfig | None,
) -> dict[str, Any]:
    gate = resource_access
    img_allow = True if gate is None else gate.is_allowed(RESOURCE_MULTIMODAL_IMAGE_URL, "read")
    np = network_policy
    guard_on = bool(np and np.http_url_guard_enabled)
    hosts = list(np.http_url_allowed_hosts) if np else []
    return {
        "multimodal_image_url_read_allowed": img_allow,
        "multimodal_http_url_guard_enabled": guard_on,
        "multimodal_http_url_allowed_hosts": hosts,
    }


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
    lim = session.config.limits
    counter = make_message_token_counter(lim.assembly_token_counter, lim.assembly_tiktoken_encoding)
    return apply_three_tier_token_budget(
        list(messages),
        lim.assembly_approx_context_tokens,
        compress_tool_max_chars=lim.assembly_compress_tool_max_chars,
        compress_early_turn_chars=lim.assembly_compress_early_turn_chars,
        count_tokens=counter,
    )


def _memory_retrieval_query(request: AgentRequest) -> str:
    intent = request.intent
    if isinstance(intent, Chat):
        return intent.text.strip()
    return str(request.payload).strip()


def _build_memory_context_block(
    orchestrator: MemoryOrchestrator | None,
    *,
    user_id: str,
    channel: str,
    request: AgentRequest,
    resource_access: ResourceAccessEvaluator | None,
) -> str | None:
    if orchestrator is None:
        return None
    if resource_access is not None and not resource_access.is_allowed(RESOURCE_LONG_TERM_MEMORY, "read"):
        return None
    q = _memory_retrieval_query(request)
    if not q:
        return None
    snippets = orchestrator.retrieve_for_context(user_id=user_id, channel=channel, query_text=q)
    if not snippets:
        return None
    lines = ["<long_term_memory>", "以下为与用户问题相关的长期记忆片段（含 memory_id 供溯源）："]
    for s in snippets:
        lines.append(f"[{s.memory_id}] score={s.score:.4f}\n{s.text}")
    lines.append("</long_term_memory>")
    return "\n".join(lines)

