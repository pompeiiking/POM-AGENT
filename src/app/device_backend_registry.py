"""
设备后端注册表（架构设计 §1.5 装配链 / §12.6 可替换模块）

职责：
- 解析 tools.yaml 中的 device_backend_ref 引用
- 提供 builtin 实现与 entrypoint 扩展

支持的引用格式：
- builtin:simulator — 本地模拟后端（开发/测试）
- builtin:noop — 空操作后端（仅返回成功）
- entrypoint:<name> — 从 pompeii_agent.device_backends 加载
"""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Callable

from modules.tools.device_backend import (
    CompositeDeviceBackend,
    DeviceBackend,
    DeviceExecutionResult,
    LocalSimulatorBackend,
)
from core.types import DeviceRequest


class NoopDeviceBackend:
    """空操作设备后端：所有请求返回成功但无实际操作"""

    def supports(self, device: str) -> bool:
        return True

    def execute(self, request: DeviceRequest) -> DeviceExecutionResult:
        return DeviceExecutionResult(
            success=True,
            output={
                "device": request.device,
                "command": request.command,
                "parameters": dict(request.parameters),
                "noop": True,
                "message": "No-op device backend: request acknowledged but not executed",
            },
        )


DeviceBackendFactory = Callable[[], DeviceBackend]

_BUILTIN_BACKENDS: dict[str, DeviceBackendFactory] = {
    "simulator": lambda: LocalSimulatorBackend(),
    "noop": lambda: NoopDeviceBackend(),
}


def resolve_device_backend(ref: str) -> DeviceBackend:
    """
    解析设备后端引用
    
    Args:
        ref: 引用字符串，格式为 builtin:<name> 或 entrypoint:<name>
    
    Returns:
        DeviceBackend 实例
    
    Raises:
        ValueError: 引用格式无效或未找到实现
    """
    if not ref or ":" not in ref:
        raise ValueError(f"invalid device_backend_ref: {ref!r}")
    
    prefix, name = ref.split(":", 1)
    prefix = prefix.strip().lower()
    name = name.strip()
    
    if prefix == "builtin":
        factory = _BUILTIN_BACKENDS.get(name)
        if factory is None:
            available = ", ".join(sorted(_BUILTIN_BACKENDS.keys()))
            raise ValueError(
                f"unknown builtin device backend: {name!r}; available: {available}"
            )
        return factory()
    
    if prefix == "entrypoint":
        return _load_entrypoint_backend(name)
    
    raise ValueError(f"unknown device_backend_ref prefix: {prefix!r}")


def _load_entrypoint_backend(name: str) -> DeviceBackend:
    """从 entrypoint 加载设备后端"""
    eps = entry_points(group="pompeii_agent.device_backends")
    for ep in eps:
        if ep.name == name:
            factory = ep.load()
            if callable(factory):
                return factory()
            raise ValueError(f"entrypoint {name!r} is not callable")
    
    raise ValueError(f"device backend entrypoint not found: {name!r}")


def build_device_backend(
    refs: list[str] | None = None,
    *,
    fallback_to_simulator: bool = True,
) -> DeviceBackend:
    """
    构建设备后端（可组合多个）
    
    Args:
        refs: 设备后端引用列表，按优先级排序
        fallback_to_simulator: 无引用时是否回退到模拟器
    
    Returns:
        DeviceBackend 实例（可能是 CompositeDeviceBackend）
    """
    backends: list[DeviceBackend] = []
    
    if refs:
        for ref in refs:
            try:
                backends.append(resolve_device_backend(ref))
            except ValueError:
                pass
    
    if not backends and fallback_to_simulator:
        backends.append(LocalSimulatorBackend())
    
    if len(backends) == 1:
        return backends[0]
    
    return CompositeDeviceBackend(backends)
