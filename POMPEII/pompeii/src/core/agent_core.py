from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Protocol
from .session.session import Session, SessionConfig
from .session.session_manager import SessionManager
from .agent_types import AgentRequest, AgentResponse
from .session.message_factory import new_message
from .session.openai_message_format import tool_content_openai_v1
from .user_intent import SystemArchive
from modules.assembly.interface import AssemblyModule
from modules.model.interface import ModelModule, ModelOutput
from modules.tools.interface import ToolModule
from .kernel_config import KernelConfig
from .types import ToolCall, ToolResult
from .policies import (
    OutputStep,
    build_loop_governance,
    build_output_handlers,
    decide_tool_policy,
    max_loops_exceeded_response,
    next_tool_calls,
    resolve_handler,
    tool_call_budget_decision,
    tool_to_device_request,
)
from .policies.tool_actions import ToolContext, ToolDeps, step_device_request, step_error, step_execute_tool


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
    def handle(self, request: AgentRequest) -> AgentResponse:
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
    def handle_confirmation_approved(self, request: AgentRequest, tool_call: ToolCall) -> AgentResponse:
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
    ) -> AgentResponse:
        """
        设备结果入口：
        - Port 收到 device_result 后调用
        - Core 将结果回注到上下文并继续 loop
        - tool_call_id：与先前 assistant.tool_calls[].id 对齐（由 Port 传入 pending.tool_call.call_id）
        """
        ...


ConfigProvider = Callable[[str, str], SessionConfig]


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
    ) -> None:
        super().__init__(session_manager, assembly, model, tools)
        self._config_provider = config_provider
        self._kernel_config = kernel_config

    def handle(self, request: AgentRequest) -> AgentResponse:
        return self._handle(request, bypass_tool_confirmation=False)

    def handle_confirmation_approved(self, request: AgentRequest, tool_call: ToolCall) -> AgentResponse:
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

    def list_archives_for_user(self, user_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._session_manager.list_archives_for_user(user_id, limit=limit)

    def handle_device_result(
        self,
        request: AgentRequest,
        *,
        tool_result: ToolResult,
        tool_call_id: str | None = None,
    ) -> AgentResponse:
        config = self._config_provider(request.user_id, request.channel)
        session = self._session_manager.get_or_create_session(
            user_id=request.user_id,
            channel=request.channel,
            config=config,
        )
        context = self._assembly.apply_tool_result(session, tool_result)
        tid = tool_call_id or uuid.uuid4().hex
        self._session_manager.append_message(
            session.session_id,
            new_message(
                role="tool",
                content=tool_content_openai_v1(
                    tool_call_id=tid,
                    payload={"name": tool_result.name, "output": tool_result.output},
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

    def _handle(self, request: AgentRequest, *, bypass_tool_confirmation: bool) -> AgentResponse:
        if isinstance(request.intent, SystemArchive):
            return self._handle_archive_command(request)
        # 1. 获取会话配置并查找/创建 Session
        config = self._config_provider(request.user_id, request.channel)
        session = self._session_manager.get_or_create_session(
            user_id=request.user_id,
            channel=request.channel,
            config=config,
        )
        self._session_manager.append_message(
            session.session_id,
            new_message(
                role="user",
                content=str(request.payload),
                loop_index=0,
            ),
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
                reason="ok",
            )
        self._session_manager.append_message(
            session.session_id,
            new_message(role="user", content="/archive", loop_index=0),
        )
        session = self._session_manager.trigger_archive(session.session_id)
        return AgentResponse(
            request_id=request.request_id,
            session=session,
            reply_text="会话已归档。",
            error=None,
            reason="ok",
        )

    def _run_loop(
        self,
        request_id: str,
        session: Session,
        context: Any,
        *,
        bypass_tool_confirmation: bool,
    ) -> AgentResponse:
        governance = build_loop_governance(session=session, kernel_config=self._kernel_config)
        tool_calls = 0
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
                    reason="unsupported_output_kind",
                ),
                context=context,
            )

        for _ in range(governance.max_loops):
            output = self._model.run(session, context)
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
            reason="ok",
        )

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
                reason="tool_call_missing",
            )

        decision = decide_tool_policy(
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
                reason=decision.reason or "tool_policy_denied",
            )

        if decision.needs_confirmation:
            return OutputStep(
                response=AgentResponse(
                    request_id=request_id,
                    session=session,
                    reply_text=None,
                    error="confirmation required",
                    reason="confirmation_required",
                    pending_tool_call=tool_call,
                ),
                context=context,
            )

        tc = ToolContext(request_id=request_id, session=session, context=context, tool_call=tool_call)
        deps = ToolDeps(
            session_manager=self._session_manager,
            assembly=self._assembly,
            tools=self._tools,
            tool_to_device_request=tool_to_device_request,
        )

        device_request = deps.tool_to_device_request(tc.tool_call)
        actions = {
            True: lambda: step_device_request(deps=deps, tc=tc, device_request=device_request),  # type: ignore[arg-type]
            False: lambda: step_execute_tool(deps=deps, tc=tc),
        }
        return actions[device_request is not None]()
