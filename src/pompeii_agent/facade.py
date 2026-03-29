"""
对外推荐 API：通过 ``pompeii_agent`` 映射函数与 ``pompeii_agent.config`` 装配；无需 ``import app``.

完整底层开放能力见 ``pompeii_agent.advanced``。
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.composition import build_core, build_port
from app.http_app_factory import HttpAgentService, InputDTO, build_http_agent_service
from core import AgentCoreImpl
from pompeii_agent.config import ConfigProvider
from core.agent_types import AgentRequest, AgentResponse
from core.user_intent import Chat, UserIntent
from platform_layer.bundled_root import framework_root as _bundled_resources_root
from port.agent_port import GenericAgentPort, InteractionMode, PortEmitter
from port.request_factory import RequestFactory

if TYPE_CHECKING:
    from modules.assembly.interface import AssemblyModule
    from modules.model.config import ModelRegistry


def resources_root() -> Path:
    """返回随包分发的资源根目录（其下含 ``platform_layer/resources``）。"""
    return _bundled_resources_root()


def create_kernel(
    config_provider: ConfigProvider,
    model_registry: ModelRegistry | None = None,
    *,
    src_root: Path | None = None,
    assembly: AssemblyModule | None = None,
) -> AgentCoreImpl:
    """
    创建 Agent 微内核实例（会话、模型、工具、Loop 治理、记忆与资源门等默认装配）。

    ``config_provider``、``model_registry``、``src_root`` 的语义与内部 ``build_core`` 一致。
    """
    return build_core(
        config_provider,
        model_registry,
        src_root=src_root,
        assembly=assembly,
    )


def create_interactive_port(
    mode: InteractionMode,
    request_factory: RequestFactory,
    emitter: PortEmitter,
    *,
    src_root: Path | None = None,
    kernel: AgentCoreImpl | None = None,
    pending_state_sqlite_path: Path | None = None,
) -> GenericAgentPort:
    """
    创建交互 Port（CLI 等）：封装 ``build_port``，可选传入已创建的 ``kernel`` 以与 HTTP 等形态共享会话。
    """
    return build_port(
        mode,
        request_factory,
        emitter,
        src_root=src_root,
        core=kernel,
        pending_state_sqlite_path=pending_state_sqlite_path,
    )


def create_http_service(
    *,
    src_root: Path | None = None,
    kernel: AgentCoreImpl | None = None,
    port_cell: list[Any] | None = None,
) -> HttpAgentService:
    """
    创建 HTTP/WS 服务（FastAPI）：返回 ``app``、``kernel``、``port``，便于嵌入或 ``uvicorn`` 启动。

    ``port_cell`` 与 ``app.http_app_factory.build_http_agent_service`` 相同，供测试注入假 Port。
    """
    return build_http_agent_service(src_root=src_root, kernel=kernel, port_cell=port_cell)


def invoke_kernel(
    kernel: AgentCoreImpl,
    *,
    user_id: str,
    channel: str,
    text: str,
    request_id: str | None = None,
    stream: bool = False,
    intent: UserIntent | None = None,
) -> AgentResponse:
    """
    单次调用内核处理用户输入（内部可走完整 tool loop）。

    默认 ``intent`` 为 ``Chat``；系统指令、多模态等可传入自定义 ``UserIntent`` 与 ``AgentRequest``（见 ``advanced``）。
    """
    rid = request_id or str(uuid.uuid4())
    eff_intent: UserIntent = intent if intent is not None else Chat(text=text)
    return kernel.handle(
        AgentRequest(
            request_id=rid,
            user_id=user_id,
            channel=channel,
            payload=text,
            intent=eff_intent,
            stream=stream,
        )
    )


__all__ = [
    "HttpAgentService",
    "InputDTO",
    "create_http_service",
    "create_interactive_port",
    "create_kernel",
    "framework_root",
    "invoke_kernel",
    "resources_root",
]

framework_root = resources_root
