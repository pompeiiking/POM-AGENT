"""
App 层对外公共 API（设备后端注册表）。

外部用户应从本包导入所有设备后端相关类型::

    from app import (
        DeviceBackend,
        DeviceExecutionResult,
        LocalSimulatorBackend,
        CompositeDeviceBackend,
        NoopDeviceBackend,
        DeviceBackendFactory,
        resolve_device_backend,
        build_device_backend,
    )
"""

from __future__ import annotations

from .device_backend_registry import (
    NoopDeviceBackend,
    DeviceBackendFactory,
    resolve_device_backend,
    build_device_backend,
)

__all__ = [
    "NoopDeviceBackend",
    "DeviceBackendFactory",
    "resolve_device_backend",
    "build_device_backend",
]
