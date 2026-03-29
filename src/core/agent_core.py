from __future__ import annotations

import json
import logging
import threading
import uuid

import infra.logging_config  # noqa: F401 — LogRecord 注入 request_id / user_id / channel
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, Literal, Mapping, Protocol
from .session.session import Session, SessionConfig
from .session.session_manager import SessionManager
from .agent_types import AgentRequest, AgentResponse, ResponseReason
from .session.message_factory import new_message
from .session.multimodal_user_payload import flatten_payload_for_security, new_user_message_from_agent_payload
from .session.openai_message_format import tool_content_openai_v1
from .memory.content import MemoryChunkRecord
from .memory.orchestrator import MemoryOrchestrator
from .user_intent import SystemArchive, SystemDelegate, SystemFact, SystemForget, SystemPreference, SystemRemember
from modules.assembly.interface import AssemblyModule
from modules.model.interface import ModelModule, ModelOutput
from modules.tools.interface import ToolModule
from .archive_llm_summary import ArchiveLlmSummaryBinding
from .kernel_config import KernelConfig
from .model_stream_context import attach_model_stream_delta, reset_model_stream_delta
from .resource_access import RESOURCE_LONG_TERM_MEMORY, ResourceAccessEvaluator
from .session.session_archive import build_dialogue_plain_for_archive
from .types import ToolCall, ToolResult
from .policies import (
    OutputStep,
    build_loop_governance,
    build_output_handlers,
    decide_tool_policy,
    max_loops_exceeded_response,
    next_tool_calls,
    repeated_tool_call_response,
    resolve_handler,
    tool_call_budget_decision,
    tool_call_fingerprint,
)
from .policies.loop_policy import LoopGovernance
from .policies.tool_policy import ToolPolicyDecision
from .policies.tool_actions import ToolContext, ToolDeps, step_device_request, step_error, step_execute_tool

_log = logging.getLogger(__name__)

_GUARD_BLOCK_PATTERNS: tuple[str, ...] = (
    "ignore previous instructions",
    "system prompt",
    "developer message",
    "<script",
    "rm -rf",
    "drop table",
)

class GuardEvaluator(Protocol):
    def __call__(self, text: str) -> bool: ...


GuardModelShouldBlock = Callable[[str], bool]

ToolPolicyDecideFn = Callable[..., ToolPolicyDecision]
LoopGovernanceFn = Callable[[Session, KernelConfig], LoopGovernance]


class AgentCore(ABC):
    """
    核心部抽象（微内核入口）。

    职责：
    - 接收 AgentPort 规范化后的请求（AgentRequest）
    - 管理会话生命周期（依赖 SessionManager）
    - 在组装部 / 模型部 / 工具部之间进行 Loop 级路由
    - 控制循环终止条件与高层容错（见架构文档 8.x）
    """

    def __init__(
        self,
        session_manager: SessionManager,
        assembly: AssemblyModule,
        model: ModelModule,
        tools: ToolModule,
    ) -> None:
        self._session_manager = session_manager
        self._assembly = assembly
        self._model = model
        self._tools = tools

    @abstractmethod
    def handle(
        self,
        request: AgentRequest,
        *,
        stream_delta: Callable[[str], None] | None = None,
    ) -> AgentResponse:
        """
        Agent 核心主入口。

        典型流程（简化版）：
        1. 通过 SessionManager 查找/创建会话
        2. 调用组装部构建初始 Context Window
        3. 进入 Loop（受 max_loops / token 预算 等约束）：
           - 调模型部 run()，得到 ModelOutput(kind=\"text\" 或 \"tool_call\")
           - 若输出是 tool_call：执行安全检查 → 调用 ToolModule.execute() → 回到组装部 apply_tool_result() → 继续下一轮
           - 若输出是文本：调用组装部 format_final_reply(session, ModelOutput) → 结束（reason=\"ok\"）
           - 若触发终止条件（循环上限/预算超限/错误）：构造对应的 error + reason → 结束
        4. 返回 AgentResponse（reply_text 或 error）
        """
        ...

    @abstractmethod
    def handle_confirmation_approved(
        self,
        request: AgentRequest,
        tool_call: ToolCall,
        *,
        stream_delta: Callable[[str], None] | None = None,
    ) -> AgentResponse:
        """
        用户已批准待确认工具：
        - 不重复追加本轮 user 消息，不再次调用模型生成 tool_call
        - 直接按 `tool_call` 走策略与执行（等同 bypass 确认门）
        """
        ...

    @abstractmethod
    def handle_device_result(
        self,
        request: AgentRequest,
        *,
        tool_result: ToolResult,
        tool_call_id: str | None = None,
        stream_delta: Callable[[str], None] | None = None,
    ) -> AgentResponse:
        """
        设备结果入口：
        - Port 收到 device_result 后调用
        - Core 将结果回注到上下文并继续 loop
        - tool_call_id：与先前 assistant.tool_calls[].id 对齐（由 Port 传入 pending.tool_call.call_id）
        """
        ...


ConfigProvider = Callable[[str, str], SessionConfig]


def _tool_output_rule_scan_text(output: Any) -> str:
    """
    关卡④-c：截断、注入子串、guard_block 共用的文本视图。
    结构化输出优先 JSON，便于匹配仅出现在双引号形态下的片段（与组装部序列化工具结果一致）。
    """
    if isinstance(output, (dict, list)):
        try:
            return json.dumps(output, ensure_ascii=False, default=str)
        except TypeError:
            return str(output)
    return str(output)


class AgentCoreImpl(AgentCore):
    """
    简化版 AgentCore 实现：
    - 一轮或多轮 Loop（仅区分 text / tool_call）
    - 不实现安全门和复杂错误分类，只演示主数据流
    """

    def __init__(
        self,
        session_manager: SessionManager,
        assembly: AssemblyModule,
        model: ModelModule,
        tools: ToolModule,
        config_provider: ConfigProvider,
        kernel_config: KernelConfig,
        security_policies: Mapping[str, Any] | None = None,
        guard_evaluator: GuardEvaluator | None = None,
        guard_model_should_block: GuardModelShouldBlock | None = None,
        memory_orchestrator: MemoryOrchestrator | None = None,
        archive_llm: ArchiveLlmSummaryBinding | None = None,
        resource_access: ResourceAccessEvaluator | None = None,
        tool_policy_decide: ToolPolicyDecideFn | None = None,
        loop_governance_fn: LoopGovernanceFn | None = None,
    ) -> None:
        super().__init__(session_manager, assembly, model, tools)
        self._config_provider = config_provider
        self._kernel_config = kernel_config
        self._security_policies = security_policies or {}
        self._guard_evaluator = guard_evaluator
        self._guard_model_should_block = guard_model_should_block
        self._memory_orchestrator = memory_orchestrator
        self._archive_llm = archive_llm
        self._resource_access = resource_access
        self._tool_policy_decide: ToolPolicyDecideFn = (
            tool_policy_decide if tool_policy_decide is not None else decide_tool_policy
        )
        self._loop_governance_fn = loop_governance_fn

    def handle(
        self,
        request: AgentRequest,
        *,
        stream_delta: Callable[[str], None] | None = None,
    ) -> AgentResponse:
        token = attach_model_stream_delta(stream_delta)
        try:
            return self._handle(request, bypass_tool_confirmation=False)
        finally:
            reset_model_stream_delta(token)

    def handle_confirmation_approved(
        self,
        request: AgentRequest,
        tool_call: ToolCall,
        *,
        stream_delta: Callable[[str], None] | None = None,
    ) -> AgentResponse:
        token = attach_model_stream_delta(stream_delta)
        try:
            config = self._config_provider(request.user_id, request.channel)
            session = self._session_manager.get_or_create_session(
                user_id=request.user_id,
                channel=request.channel,
                config=config,
            )
            context = self._assembly.build_initial_context(session, request)
            step = self._handle_tool_call_with_policy(
                request.request_id,
                session,
                context,
                ModelOutput(kind="tool_call", tool_call=tool_call),
                bypass_tool_confirmation=True,
            )
            if step.response is not None:
                return step.response
            return self._run_loop(
                request.request_id,
                session,
                step.context,
                bypass_tool_confirmation=True,
            )
        finally:
            reset_model_stream_delta(token)

    def list_archives_for_user(self, user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._session_manager.list_archives_for_user(user_id, limit=limit)

    def handle_device_result(
        self,
        request: AgentRequest,
        *,
        tool_result: ToolResult,
        tool_call_id: str | None = None,
        stream_delta: Callable[[str], None] | None = None,
    ) -> AgentResponse:
        token = attach_model_stream_delta(stream_delta)
        try:
            config = self._config_provider(request.user_id, request.channel)
            session = self._session_manager.get_or_create_session(
                user_id=request.user_id,
                channel=request.channel,
                config=config,
            )
            safe_tool_result = self._sanitize_tool_result_for_guard(session=session, tool_result=tool_result)
            context = self._assembly.apply_tool_result(session, safe_tool_result)
            tid = tool_call_id or uuid.uuid4().hex
            self._session_manager.append_message(
                session.session_id,
                new_message(
                    role="tool",
                    content=tool_content_openai_v1(
                        tool_call_id=tid,
                        payload={"name": safe_tool_result.name, "output": safe_tool_result.output},
                    ),
                    loop_index=0,
                ),
            )
            return self._run_loop(
                request_id=request.request_id,
                session=session,
                context=context,
                bypass_tool_confirmation=True,
            )
        finally:
            reset_model_stream_delta(token)

    def _handle(self, request: AgentRequest, *, bypass_tool_confirmation: bool) -> AgentResponse:
        _log.debug(
            "core._handle intent=%s",
            type(request.intent).__name__ if request.intent is not None else "none",
        )
        if isinstance(request.intent, SystemArchive):
            return self._handle_archive_command(request)
        if isinstance(request.intent, SystemRemember):
            return self._handle_remember_command(request)
        if isinstance(request.intent, SystemForget):
            return self._handle_forget_command(request)
        if isinstance(request.intent, SystemPreference):
            return self._handle_preference_command(request)
        if isinstance(request.intent, SystemFact):
            return self._handle_fact_command(request)
        if isinstance(request.intent, SystemDelegate):
            return self._handle_delegate_command(request)
        # 1. 获取会话配置并查找/创建 Session
        config = self._config_provider(request.user_id, request.channel)
        session = self._session_manager.get_or_create_session(
            user_id=request.user_id,
            channel=request.channel,
            config=config,
        )
        blocked = self._enforce_security_policy(
            request_id=request.request_id,
            session=session,
            payload=flatten_payload_for_security(request.payload),
        )
        if blocked is not None:
            return blocked
        self._session_manager.append_message(
            session.session_id,
            new_user_message_from_agent_payload(request.payload, loop_index=0),
        )

        # 2. 首次组装上下文
        context = self._assembly.build_initial_context(session, request)

        # 3. Loop：模型推理 -> (text / tool_call)
        return self._run_loop(
            request_id=request.request_id,
            session=session,
            context=context,
            bypass_tool_confirmation=bypass_tool_confirmation,
        )

    def _handle_archive_command(self, request: AgentRequest) -> AgentResponse:
        config = self._config_provider(request.user_id, request.channel)
        session = self._session_manager.find_session_for_user(request.user_id, request.channel)
        if session is None:
            session = self._session_manager.get_or_create_session(
                user_id=request.user_id,
                channel=request.channel,
                config=config,
            )
            return AgentResponse(
                request_id=request.request_id,
                session=session,
                reply_text="没有可归档的活跃会话。",
                error=None,
                reason=ResponseReason.OK,
            )
        self._session_manager.append_message(
            session.session_id,
            new_message(role="user", content="/archive", loop_index=0),
        )
        session = self._session_manager.trigger_archive(session.session_id)
        if self._memory_orchestrator is not None and self._memory_orchestrator.policy.promote_on_archive:
            if self._resource_access is None or self._resource_access.is_allowed(RESOURCE_LONG_TERM_MEMORY, "write"):
                self._memory_orchestrator.promote_archived_session(session)
        self._schedule_archive_llm_summary(session)
        return AgentResponse(
            request_id=request.request_id,
            session=session,
            reply_text="会话已归档。",
            error=None,
            reason=ResponseReason.OK,
        )

    def _schedule_archive_llm_summary(self, session: Session) -> None:
        b = self._archive_llm
        if b is None:
            return
        sid = session.session_id
        dialogue = build_dialogue_plain_for_archive(session, max_chars=b.max_dialogue_chars)
        self._session_manager.update_archive_llm_summary(sid, status="pending", llm_text=None)
        threading.Thread(
            target=self._run_archive_llm_worker,
            args=(sid, dialogue),
            daemon=True,
        ).start()

    def _run_archive_llm_worker(self, session_id: str, dialogue_plain: str) -> None:
        b = self._archive_llm
        if b is None:
            return
        try:
            if not dialogue_plain.strip():
                self._session_manager.update_archive_llm_summary(session_id, status="skipped", llm_text=None)
                return
            text = b.summarize(
                provider_id=b.provider_id,
                dialogue_plain=dialogue_plain,
                max_output_chars=b.max_output_chars,
                system_prompt=b.system_prompt,
            )
            self._session_manager.update_archive_llm_summary(session_id, status="done", llm_text=text)
        except Exception:
            self._session_manager.update_archive_llm_summary(session_id, status="failed", llm_text=None)

    def _handle_remember_command(self, request: AgentRequest) -> AgentResponse:
        if not isinstance(request.intent, SystemRemember):
            raise TypeError("expected SystemRemember")
        config = self._config_provider(request.user_id, request.channel)
        session = self._session_manager.get_or_create_session(
            user_id=request.user_id,
            channel=request.channel,
            config=config,
        )
        if self._memory_orchestrator is None:
            return AgentResponse(
                request_id=request.request_id,
                session=session,
                reply_text="长期记忆未启用（memory_policy.enabled=false 或未加载）。",
                error=None,
                reason=ResponseReason.OK,
            )
        if self._resource_access is not None and not self._resource_access.is_allowed(RESOURCE_LONG_TERM_MEMORY, "write"):
            return AgentResponse(
                request_id=request.request_id,
                session=session,
                reply_text="当前资源策略禁止写入长期记忆。",
                error=None,
                reason=ResponseReason.RESOURCE_ACCESS_DENIED,
            )
        if self._resource_access is not None and self._resource_access.requires_approval(RESOURCE_LONG_TERM_MEMORY, "write"):
            return AgentResponse(
                request_id=request.request_id,
                session=session,
                reply_text="当前资源策略要求审批后方可写入长期记忆。",
                error=None,
                reason=ResponseReason.RESOURCE_APPROVAL_REQUIRED,
            )
        blocked = self._enforce_security_policy(
            request_id=request.request_id,
            session=session,
            payload=request.intent.text,
        )
        if blocked is not None:
            return blocked
        self._session_manager.append_message(
            session.session_id,
            new_message(role="user", content=str(request.payload), loop_index=0),
        )
        self._memory_orchestrator.ingest_record(
            MemoryChunkRecord(
                user_id=request.user_id,
                text=request.intent.text,
                channel=request.channel,
                trust="high",
                source_session_id=session.session_id,
            )
        )
        session = self._session_manager.get_session(session.session_id) or session
        return AgentResponse(
            request_id=request.request_id,
            session=session,
            reply_text="已写入长期记忆。",
            error=None,
            reason=ResponseReason.OK,
        )

    def _handle_forget_command(self, request: AgentRequest) -> AgentResponse:
        if not isinstance(request.intent, SystemForget):
            raise TypeError("expected SystemForget")
        config = self._config_provider(request.user_id, request.channel)
        session = self._session_manager.get_or_create_session(
            user_id=request.user_id,
            channel=request.channel,
            config=config,
        )
        if self._memory_orchestrator is None:
            return AgentResponse(
                request_id=request.request_id,
                session=session,
                reply_text="长期记忆未启用（memory_policy.enabled=false 或未加载）。",
                error=None,
                reason=ResponseReason.OK,
            )
        if self._resource_access is not None and not self._resource_access.is_allowed(RESOURCE_LONG_TERM_MEMORY, "write"):
            return AgentResponse(
                request_id=request.request_id,
                session=session,
                reply_text="当前资源策略禁止修改长期记忆（遗忘）。",
                error=None,
                reason=ResponseReason.RESOURCE_ACCESS_DENIED,
            )
        if self._resource_access is not None and self._resource_access.requires_approval(RESOURCE_LONG_TERM_MEMORY, "write"):
            return AgentResponse(
                request_id=request.request_id,
                session=session,
                reply_text="当前资源策略要求审批后方可修改长期记忆（遗忘）。",
                error=None,
                reason=ResponseReason.RESOURCE_APPROVAL_REQUIRED,
            )
        blocked = self._enforce_security_policy(
            request_id=request.request_id,
            session=session,
            payload=request.intent.phrase,
        )
        if blocked is not None:
            return blocked
        self._session_manager.append_message(
            session.session_id,
            new_message(role="user", content=str(request.payload), loop_index=0),
        )
        n = self._memory_orchestrator.forget_phrase(request.user_id, request.intent.phrase)
        session = self._session_manager.get_session(session.session_id) or session
        return AgentResponse(
            request_id=request.request_id,
            session=session,
            reply_text=f"已按短语处理长期记忆 {n} 条。",
            error=None,
            reason=ResponseReason.OK,
        )

    def _handle_preference_command(self, request: AgentRequest) -> AgentResponse:
        if not isinstance(request.intent, SystemPreference):
            raise TypeError("expected SystemPreference")
        config = self._config_provider(request.user_id, request.channel)
        session = self._session_manager.get_or_create_session(
            user_id=request.user_id,
            channel=request.channel,
            config=config,
        )
        if self._memory_orchestrator is None:
            return AgentResponse(
                request_id=request.request_id,
                session=session,
                reply_text="长期记忆未启用（memory_policy.enabled=false 或未加载）。",
                error=None,
                reason=ResponseReason.OK,
            )
        if self._resource_access is not None and not self._resource_access.is_allowed(RESOURCE_LONG_TERM_MEMORY, "write"):
            if request.intent.action in ("set", "delete"):
                return AgentResponse(
                    request_id=request.request_id,
                    session=session,
                    reply_text="当前资源策略禁止写入长期记忆。",
                    error=None,
                    reason=ResponseReason.RESOURCE_ACCESS_DENIED,
                )
        if self._resource_access is not None and request.intent.action in ("set", "delete"):
            if self._resource_access.requires_approval(RESOURCE_LONG_TERM_MEMORY, "write"):
                return AgentResponse(
                    request_id=request.request_id,
                    session=session,
                    reply_text="当前资源策略要求审批后方可写入长期记忆。",
                    error=None,
                    reason=ResponseReason.RESOURCE_APPROVAL_REQUIRED,
                )
        if self._resource_access is not None and not self._resource_access.is_allowed(RESOURCE_LONG_TERM_MEMORY, "read"):
            if request.intent.action in ("get", "list"):
                return AgentResponse(
                    request_id=request.request_id,
                    session=session,
                    reply_text="当前资源策略禁止读取长期记忆。",
                    error=None,
                    reason=ResponseReason.RESOURCE_ACCESS_DENIED,
                )
        if self._resource_access is not None and request.intent.action in ("get", "list"):
            if self._resource_access.requires_approval(RESOURCE_LONG_TERM_MEMORY, "read"):
                return AgentResponse(
                    request_id=request.request_id,
                    session=session,
                    reply_text="当前资源策略要求审批后方可读取长期记忆。",
                    error=None,
                    reason=ResponseReason.RESOURCE_APPROVAL_REQUIRED,
                )
        self._session_manager.append_message(
            session.session_id,
            new_message(role="user", content=str(request.payload), loop_index=0),
        )
        mo = self._memory_orchestrator
        intent = request.intent
        if intent.action == "set":
            mo.set_preference(request.user_id, intent.key, intent.value)
            reply = f"偏好已设置：{intent.key}={intent.value}"
        elif intent.action == "get":
            val = mo.get_preference(request.user_id, intent.key)
            reply = f"{intent.key}={val}" if val is not None else f"未找到偏好 {intent.key!r}。"
        elif intent.action == "list":
            prefs = mo.list_preferences(request.user_id)
            if prefs:
                lines = [f"  {k}={v}" for k, v in prefs]
                reply = "当前偏好：\n" + "\n".join(lines)
            else:
                reply = "暂无偏好记录。"
        elif intent.action == "delete":
            deleted = mo.delete_preference(request.user_id, intent.key)
            reply = f"已删除偏好 {intent.key!r}。" if deleted else f"未找到偏好 {intent.key!r}。"
        else:
            reply = f"未知 preference 操作：{intent.action!r}。支持 set/get/list/delete。"
        session = self._session_manager.get_session(session.session_id) or session
        return AgentResponse(
            request_id=request.request_id,
            session=session,
            reply_text=reply,
            error=None,
            reason=ResponseReason.OK,
        )

    def _handle_fact_command(self, request: AgentRequest) -> AgentResponse:
        if not isinstance(request.intent, SystemFact):
            raise TypeError("expected SystemFact")
        config = self._config_provider(request.user_id, request.channel)
        session = self._session_manager.get_or_create_session(
            user_id=request.user_id,
            channel=request.channel,
            config=config,
        )
        if self._memory_orchestrator is None:
            return AgentResponse(
                request_id=request.request_id,
                session=session,
                reply_text="长期记忆未启用（memory_policy.enabled=false 或未加载）。",
                error=None,
                reason=ResponseReason.OK,
            )
        if self._resource_access is not None and not self._resource_access.is_allowed(RESOURCE_LONG_TERM_MEMORY, "write"):
            if request.intent.action in ("add", "delete"):
                return AgentResponse(
                    request_id=request.request_id,
                    session=session,
                    reply_text="当前资源策略禁止写入长期记忆。",
                    error=None,
                    reason=ResponseReason.RESOURCE_ACCESS_DENIED,
                )
        if self._resource_access is not None and request.intent.action in ("add", "delete"):
            if self._resource_access.requires_approval(RESOURCE_LONG_TERM_MEMORY, "write"):
                return AgentResponse(
                    request_id=request.request_id,
                    session=session,
                    reply_text="当前资源策略要求审批后方可写入长期记忆。",
                    error=None,
                    reason=ResponseReason.RESOURCE_APPROVAL_REQUIRED,
                )
        if self._resource_access is not None and not self._resource_access.is_allowed(RESOURCE_LONG_TERM_MEMORY, "read"):
            if request.intent.action in ("get", "list"):
                return AgentResponse(
                    request_id=request.request_id,
                    session=session,
                    reply_text="当前资源策略禁止读取长期记忆。",
                    error=None,
                    reason=ResponseReason.RESOURCE_ACCESS_DENIED,
                )
        if self._resource_access is not None and request.intent.action in ("get", "list"):
            if self._resource_access.requires_approval(RESOURCE_LONG_TERM_MEMORY, "read"):
                return AgentResponse(
                    request_id=request.request_id,
                    session=session,
                    reply_text="当前资源策略要求审批后方可读取长期记忆。",
                    error=None,
                    reason=ResponseReason.RESOURCE_APPROVAL_REQUIRED,
                )
        self._session_manager.append_message(
            session.session_id,
            new_message(role="user", content=str(request.payload), loop_index=0),
        )
        mo = self._memory_orchestrator
        intent = request.intent
        if intent.action == "add":
            mo.add_fact(request.user_id, intent.statement)
            reply = f"事实已记录：{intent.statement}"
        elif intent.action == "get":
            val = mo.get_fact(request.user_id, intent.statement)
            reply = val if val is not None else f"未找到匹配事实 {intent.statement!r}。"
        elif intent.action == "list":
            facts = mo.list_facts(request.user_id)
            if facts:
                lines = [f"  - {s}" for s in facts]
                reply = "已记录事实：\n" + "\n".join(lines)
            else:
                reply = "暂无事实记录。"
        elif intent.action == "delete":
            deleted = mo.delete_fact(request.user_id, intent.statement)
            reply = f"已删除事实 {intent.statement!r}。" if deleted else f"未找到匹配事实 {intent.statement!r}。"
        else:
            reply = f"未知 fact 操作：{intent.action!r}。支持 add/get/list/delete。"
        session = self._session_manager.get_session(session.session_id) or session
        return AgentResponse(
            request_id=request.request_id,
            session=session,
            reply_text=reply,
            error=None,
            reason=ResponseReason.OK,
        )

    def _handle_delegate_command(self, request: AgentRequest) -> AgentResponse:
        if not isinstance(request.intent, SystemDelegate):
            raise TypeError("expected SystemDelegate")
        config = self._config_provider(request.user_id, request.channel)
        session = self._session_manager.get_or_create_session(
            user_id=request.user_id,
            channel=request.channel,
            config=config,
        )
        blocked = self._enforce_security_policy(
            request_id=request.request_id,
            session=session,
            payload=flatten_payload_for_security(request.payload),
        )
        if blocked is not None:
            return blocked
        allow = self._kernel_config.delegate_target_allowlist
        if allow and request.intent.target not in allow:
            return AgentResponse(
                request_id=request.request_id,
                session=session,
                reply_text=None,
                error="delegate target 不在 kernel.delegate_target_allowlist 中",
                reason=ResponseReason.DELEGATE_TARGET_DENIED,
            )
        self._session_manager.append_message(
            session.session_id,
            new_message(role="user", content=str(request.payload), loop_index=0),
        )
        session = self._session_manager.get_session(session.session_id) or session
        return AgentResponse(
            request_id=request.request_id,
            session=session,
            reply_text="已发出 delegate 事件，子代理路由由网关/适配层消费 PortEvent。",
            error=None,
            reason=ResponseReason.DELEGATE,
            delegate_target=request.intent.target,
            delegate_payload=request.intent.payload,
        )

    def _resolve_loop_governance(self, session: Session) -> LoopGovernance:
        if self._loop_governance_fn is not None:
            return self._loop_governance_fn(session, self._kernel_config)
        return build_loop_governance(session=session, kernel_config=self._kernel_config)

    def _run_loop(
        self,
        request_id: str,
        session: Session,
        context: Any,
        *,
        bypass_tool_confirmation: bool,
    ) -> AgentResponse:
        governance = self._resolve_loop_governance(session)
        tool_calls = 0
        last_tool_fp: str | None = None
        repeat_streak = 0
        handlers = build_output_handlers(
            on_text=self._build_text_response,
            on_tool_call=lambda rid, s, ctx, out: self._handle_tool_call_with_policy(
                rid,
                s,
                ctx,
                out,
                bypass_tool_confirmation=bypass_tool_confirmation,
            ),
        )

        def unsupported_step(request_id: str, session: Session, output: ModelOutput) -> OutputStep:
            return OutputStep(
                response=AgentResponse(
                    request_id=request_id,
                    session=session,
                    reply_text=None,
                    error=f"unsupported model output kind: {output.kind!r}",
                    reason=ResponseReason.UNSUPPORTED_OUTPUT_KIND,
                ),
                context=context,
            )

        for _ in range(governance.max_loops):
            output = self._model.run(session, context)
            if output.kind == "text":
                last_tool_fp = None
                repeat_streak = 0
            elif output.kind == "tool_call":
                if output.tool_call is None:
                    last_tool_fp = None
                    repeat_streak = 0
                else:
                    fp = tool_call_fingerprint(output.tool_call)
                    if fp == last_tool_fp:
                        repeat_streak += 1
                    else:
                        repeat_streak = 1
                        last_tool_fp = fp
                    if repeat_streak >= 2:
                        return repeated_tool_call_response(request_id=request_id, session=session)
            else:
                last_tool_fp = None
                repeat_streak = 0

            handler = resolve_handler(handlers=handlers, kind=output.kind, on_unsupported=unsupported_step)

            tool_calls = next_tool_calls(current=tool_calls, output_kind=output.kind)
            budget_decision = tool_call_budget_decision(
                tool_calls=tool_calls,
                max_tool_calls=governance.max_tool_calls_per_run,
                request_id=request_id,
                session=session,
            )
            budget_step = OutputStep(response=budget_decision, context=context)

            step = handler(request_id, session, context, output)
            first = {True: budget_step, False: step}[budget_step.response is not None]
            if first.response is not None:
                return first.response
            context = first.context

        return max_loops_exceeded_response(request_id=request_id, session=session)

    def _build_text_response(self, request_id: str, session: Session, output: ModelOutput) -> AgentResponse:
        reply_text = self._assembly.format_final_reply(session, output)
        self._session_manager.append_message(
            session.session_id,
            new_message(role="assistant", content=reply_text, loop_index=0),
        )
        return AgentResponse(
            request_id=request_id,
            session=session,
            reply_text=reply_text,
            error=None,
            reason=ResponseReason.OK,
        )

    def _enforce_security_policy(self, *, request_id: str, session: Session, payload: Any) -> AgentResponse | None:
        policy = self._get_security_policy(session)
        if policy is None:
            return None
        policy_id = str(getattr(policy, "id", "unknown"))
        message_text = str(payload)
        if bool(getattr(policy, "guard_enabled", False)):
            if self._guard_model_should_block is not None:
                try:
                    if self._guard_model_should_block(message_text):
                        return AgentResponse(
                            request_id=request_id,
                            session=session,
                            reply_text=None,
                            error=f"input blocked by guard model for policy {policy_id!r}",
                            reason=ResponseReason.SECURITY_GUARD_MODEL_BLOCKED_INPUT,
                        )
                except Exception:
                    pass
        if bool(getattr(policy, "guard_enabled", False)) and self._contains_guard_pattern(message_text, policy=policy):
            return AgentResponse(
                request_id=request_id,
                session=session,
                reply_text=None,
                error=f"input blocked by guard policy {policy_id!r}",
                reason=ResponseReason.SECURITY_GUARD_BLOCKED_INPUT,
            )
        input_max_chars = int(getattr(policy, "input_max_chars", 0))
        if input_max_chars > 0 and len(message_text) > input_max_chars:
            return AgentResponse(
                request_id=request_id,
                session=session,
                reply_text=None,
                error=f"input exceeds max chars for security policy {policy_id!r}",
                reason=ResponseReason.SECURITY_INPUT_TOO_LONG,
            )
        max_rpm = int(getattr(policy, "max_requests_per_minute", 0))
        if max_rpm > 0:
            now = datetime.now()
            recent_user_msgs = sum(
                1
                for msg in session.messages
                if msg.role == "user" and now - msg.timestamp <= timedelta(minutes=1)
            )
            if recent_user_msgs >= max_rpm:
                return AgentResponse(
                    request_id=request_id,
                    session=session,
                    reply_text=None,
                    error=f"request rate exceeded for security policy {policy_id!r}",
                    reason=ResponseReason.SECURITY_RATE_LIMITED,
                )
        return None

    def _get_security_policy(self, session: Session) -> Any | None:
        policy_id = session.config.security if isinstance(session.config.security, str) else None
        if not policy_id:
            return None
        return self._security_policies.get(policy_id)

    def _should_force_confirmation_by_risk(self, *, session: Session, tool_name: str) -> bool:
        policy = self._get_security_policy(session)
        if policy is None:
            return False
        rank = {"low": 1, "medium": 2, "high": 3}
        default_risk = str(getattr(policy, "default_tool_risk_level", "low")).strip().lower()
        overrides = getattr(policy, "tool_risk_overrides", {})
        if not isinstance(overrides, Mapping):
            overrides = {}
        tool_risk = str(overrides.get(tool_name, default_risk)).strip().lower()
        threshold = str(getattr(policy, "tool_confirmation_level", "high")).strip().lower()
        return rank.get(tool_risk, 0) >= rank.get(threshold, 4)

    def _effective_tool_output_max_chars(self, policy: Any, tool_result: ToolResult) -> int:
        tool_name = str(tool_result.name).strip()
        ch_over = getattr(policy, "tool_output_max_chars_overrides", {})
        if isinstance(ch_over, Mapping) and tool_name in ch_over:
            base = int(ch_over[tool_name])
        else:
            base = int(getattr(policy, "tool_output_max_chars", 0))

        by_trust = getattr(policy, "tool_output_max_chars_by_trust", {})
        if not isinstance(by_trust, Mapping) or not by_trust:
            return base

        src = getattr(tool_result, "source", None)
        if src == "mcp":
            level = str(getattr(policy, "mcp_tool_output_trust", "low")).strip().lower()
        elif src == "device":
            level = str(getattr(policy, "device_tool_output_trust", "low")).strip().lower()
        elif src == "http_fetch":
            level = str(getattr(policy, "http_fetch_tool_output_trust", "low")).strip().lower()
        else:
            t_over = getattr(policy, "tool_output_trust_overrides", {})
            if not isinstance(t_over, Mapping):
                t_over = {}
            dflt = str(getattr(policy, "default_tool_output_trust", "high")).strip().lower()
            level = str(t_over.get(tool_name, dflt)).strip().lower()
        if level not in ("low", "medium", "high"):
            level = "high"
        t_cap = int(by_trust.get(level, 0))
        if t_cap <= 0:
            return base
        if base <= 0:
            return t_cap
        return min(base, t_cap)

    def _sanitize_tool_result_for_guard(self, *, session: Session, tool_result: ToolResult) -> ToolResult:
        policy = self._get_security_policy(session)
        if policy is None:
            return tool_result
        scan0 = _tool_output_rule_scan_text(tool_result.output)
        text = scan0
        max_c = self._effective_tool_output_max_chars(policy, tool_result)
        if max_c > 0 and len(text) > max_c:
            marker = str(getattr(policy, "tool_output_truncation_marker", "…[truncated]"))
            text = text[:max_c] + marker
        inj = getattr(policy, "tool_output_injection_patterns", ())
        if isinstance(inj, (list, tuple)) and inj:
            lowered = text.lower()
            normalized = [str(p).strip().lower() for p in inj if isinstance(p, str) and str(p).strip()]
            if any(p in lowered for p in normalized):
                red = str(
                    getattr(policy, "tool_output_injection_redaction", "[tool_output_injection_blocked]")
                )
                return ToolResult(name=tool_result.name, output=red, source=tool_result.source)
        if bool(getattr(policy, "guard_enabled", False)) and self._contains_guard_pattern(text, policy=policy):
            redacted = str(getattr(policy, "guard_tool_output_redaction", "[guard_blocked_tool_output]"))
            return ToolResult(name=tool_result.name, output=redacted, source=tool_result.source)
        if text != scan0:
            return ToolResult(name=tool_result.name, output=text, source=tool_result.source)
        return tool_result

    def _contains_guard_pattern(self, text: str, policy: Any | None = None) -> bool:
        if self._guard_evaluator is not None:
            try:
                if bool(self._guard_evaluator(text)):
                    return True
            except Exception:
                pass
        lowered = text.lower()
        patterns = getattr(policy, "guard_block_patterns", ())
        if not isinstance(patterns, (list, tuple)):
            patterns = ()
        normalized = [str(p).strip().lower() for p in patterns if isinstance(p, str) and str(p).strip()]
        active = tuple(normalized) if normalized else _GUARD_BLOCK_PATTERNS
        return any(pattern in lowered for pattern in active)

    def _handle_tool_call(self, session: Session, context: Any, output: ModelOutput) -> Any:
        raise RuntimeError("tool call must be handled via _handle_tool_call_with_policy")

    def _handle_tool_call_with_policy(
        self,
        request_id: str,
        session: Session,
        context: Any,
        output: ModelOutput,
        *,
        bypass_tool_confirmation: bool,
    ) -> OutputStep:
        tool_call = output.tool_call
        if tool_call is None:
            return step_error(
                request_id=request_id,
                session=session,
                context=context,
                error="tool_call is missing",
                reason=ResponseReason.TOOL_CALL_MISSING,
            )

        decision = self._tool_policy_decide(
            tool_call=tool_call,
            kernel_config=self._kernel_config,
            bypass_tool_confirmation=bypass_tool_confirmation,
        )
        if not decision.allowed:
            return step_error(
                request_id=request_id,
                session=session,
                context=context,
                error=f"tool not allowed: {tool_call.name!r}",
                reason=ResponseReason.TOOL_POLICY_DENIED,
            )

        if tool_call.name == "search_memory" and self._resource_access is not None:
            if not self._resource_access.is_allowed(RESOURCE_LONG_TERM_MEMORY, "read"):
                return step_error(
                    request_id=request_id,
                    session=session,
                    context=context,
                    error="resource policy denies read access to long_term_memory (search_memory)",
                    reason=ResponseReason.RESOURCE_ACCESS_DENIED,
                )

        force_confirmation = (not bypass_tool_confirmation) and self._should_force_confirmation_by_risk(
            session=session,
            tool_name=tool_call.name,
        )
        if decision.needs_confirmation or force_confirmation:
            return OutputStep(
                response=AgentResponse(
                    request_id=request_id,
                    session=session,
                    reply_text=None,
                    error="confirmation required",
                    reason=ResponseReason.CONFIRMATION_REQUIRED,
                    pending_tool_call=tool_call,
                ),
                context=context,
            )

        tc = ToolContext(request_id=request_id, session=session, context=context, tool_call=tool_call)
        deps = ToolDeps(
            session_manager=self._session_manager,
            assembly=self._assembly,
            tools=self._tools,
            sanitize_tool_result=lambda s, r: self._sanitize_tool_result_for_guard(session=s, tool_result=r),
        )

        device_request = deps.tools.resolve_device_request(tc.tool_call)
        actions = {
            True: lambda: step_device_request(deps=deps, tc=tc, device_request=device_request),  # type: ignore[arg-type]
            False: lambda: step_execute_tool(deps=deps, tc=tc),
        }
        return actions[device_request is not None]()
