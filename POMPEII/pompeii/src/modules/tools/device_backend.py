from __future__ import annotations

from typing import Protocol, runtime_checkable

from core.session.session import Session
from core.types import ToolCall, ToolResult


@runtime_checkable
class DeviceToolBackend(Protocol):
    """
    设备类工具可选本地实现（测试桩 / 内联模拟）。

    说明：内核默认对 `tool_to_device_request` 命中的工具走 Port 的 `device_request` 流程，
    不会调用 `ToolModule.execute`。本协议供 `ToolModuleImpl.execute` 在**直接执行**
    路径下优先尝试本地结果（例如单测或未来「内联设备」模式）。
    """

    def try_local(self, session: Session, tool_call: ToolCall) -> ToolResult | None:
        ...


class NullDeviceBackend:
    def try_local(self, session: Session, tool_call: ToolCall) -> ToolResult | None:
        _ = (session, tool_call)
        return None
