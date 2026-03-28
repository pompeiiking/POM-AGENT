"""
设备后端抽象层（架构设计 §4.3 工具部设备执行器）

职责：
- 定义设备执行器 Protocol
- 提供本地模拟实现（开发/测试）
- 支持 registry 热插拔

设备请求流程：
1. ToolModule.resolve_device_request → DeviceRequest
2. Core 判断需设备 → emit DeviceRequestEvent
3. 外部设备执行 → 返回 DeviceResultInput
4. Core.handle_device_result → 继续 Loop

本模块提供「同步执行」的设备后端，用于：
- 本地模拟（无需等待外部设备）
- 内置设备（如本地文件系统、截图等）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol

from core.types import DeviceRequest, ToolResult


@dataclass(frozen=True)
class DeviceExecutionResult:
    """设备执行结果"""
    success: bool
    output: Mapping[str, Any]
    error: str | None = None
    executed_at: datetime | None = None


class DeviceBackend(Protocol):
    """
    设备后端 Protocol（关卡④ 设备执行器）
    
    实现者需提供：
    - supports(device): 是否支持该设备类型
    - execute(request): 同步执行设备请求
    """

    def supports(self, device: str) -> bool:
        """检查是否支持指定设备类型"""
        ...

    def execute(self, request: DeviceRequest) -> DeviceExecutionResult:
        """执行设备请求，返回执行结果"""
        ...


class LocalSimulatorBackend:
    """
    本地模拟设备后端（开发/测试用）
    
    支持的模拟设备：
    - camera: 模拟拍照，返回占位图片路径
    - microphone: 模拟录音，返回占位音频路径
    - speaker: 模拟播放，返回播放状态
    - display: 模拟显示，返回显示状态
    """

    SUPPORTED_DEVICES: frozenset[str] = frozenset({
        "camera",
        "microphone", 
        "speaker",
        "display",
        "filesystem",
    })

    def supports(self, device: str) -> bool:
        return device in self.SUPPORTED_DEVICES

    def execute(self, request: DeviceRequest) -> DeviceExecutionResult:
        if not self.supports(request.device):
            return DeviceExecutionResult(
                success=False,
                output={},
                error=f"unsupported device: {request.device}",
            )

        handler = getattr(self, f"_handle_{request.device}", None)
        if handler is None:
            return DeviceExecutionResult(
                success=False,
                output={},
                error=f"no handler for device: {request.device}",
            )

        return handler(request)

    def _handle_camera(self, request: DeviceRequest) -> DeviceExecutionResult:
        """模拟相机拍照"""
        command = request.command
        params = dict(request.parameters)
        
        if command == "take_photo":
            quality = params.get("quality", "medium")
            return DeviceExecutionResult(
                success=True,
                output={
                    "type": "image",
                    "path": f"/tmp/simulated_photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
                    "quality": quality,
                    "simulated": True,
                    "message": f"Simulated photo taken with quality={quality}",
                },
                executed_at=datetime.now(),
            )
        
        return DeviceExecutionResult(
            success=False,
            output={},
            error=f"unknown camera command: {command}",
        )

    def _handle_microphone(self, request: DeviceRequest) -> DeviceExecutionResult:
        """模拟麦克风录音"""
        command = request.command
        params = dict(request.parameters)
        
        if command == "record":
            duration = params.get("duration_seconds", 5)
            return DeviceExecutionResult(
                success=True,
                output={
                    "type": "audio",
                    "path": f"/tmp/simulated_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav",
                    "duration_seconds": duration,
                    "simulated": True,
                    "message": f"Simulated audio recorded for {duration}s",
                },
                executed_at=datetime.now(),
            )
        
        return DeviceExecutionResult(
            success=False,
            output={},
            error=f"unknown microphone command: {command}",
        )

    def _handle_speaker(self, request: DeviceRequest) -> DeviceExecutionResult:
        """模拟扬声器播放"""
        command = request.command
        params = dict(request.parameters)
        
        if command == "play":
            text = params.get("text", "")
            return DeviceExecutionResult(
                success=True,
                output={
                    "type": "tts",
                    "text": text,
                    "simulated": True,
                    "message": f"Simulated TTS playback: {text[:50]}...",
                },
                executed_at=datetime.now(),
            )
        
        return DeviceExecutionResult(
            success=False,
            output={},
            error=f"unknown speaker command: {command}",
        )

    def _handle_display(self, request: DeviceRequest) -> DeviceExecutionResult:
        """模拟显示器"""
        command = request.command
        params = dict(request.parameters)
        
        if command == "show":
            content = params.get("content", "")
            return DeviceExecutionResult(
                success=True,
                output={
                    "type": "display",
                    "content": content,
                    "simulated": True,
                    "message": "Simulated display output",
                },
                executed_at=datetime.now(),
            )
        
        return DeviceExecutionResult(
            success=False,
            output={},
            error=f"unknown display command: {command}",
        )

    def _handle_filesystem(self, request: DeviceRequest) -> DeviceExecutionResult:
        """模拟文件系统操作（受限）"""
        command = request.command
        params = dict(request.parameters)
        
        if command == "read":
            path = params.get("path", "")
            return DeviceExecutionResult(
                success=True,
                output={
                    "type": "file_content",
                    "path": path,
                    "content": f"[Simulated content of {path}]",
                    "simulated": True,
                },
                executed_at=datetime.now(),
            )
        
        if command == "list":
            path = params.get("path", "/")
            return DeviceExecutionResult(
                success=True,
                output={
                    "type": "directory_listing",
                    "path": path,
                    "entries": ["file1.txt", "file2.txt", "subdir/"],
                    "simulated": True,
                },
                executed_at=datetime.now(),
            )
        
        return DeviceExecutionResult(
            success=False,
            output={},
            error=f"unknown filesystem command: {command}",
        )


class CompositeDeviceBackend:
    """
    组合设备后端：按优先级尝试多个后端
    
    用于组合本地模拟 + 真实设备后端
    """

    def __init__(self, backends: list[DeviceBackend]) -> None:
        self._backends = backends

    def supports(self, device: str) -> bool:
        return any(b.supports(device) for b in self._backends)

    def execute(self, request: DeviceRequest) -> DeviceExecutionResult:
        for backend in self._backends:
            if backend.supports(request.device):
                return backend.execute(request)
        
        return DeviceExecutionResult(
            success=False,
            output={},
            error=f"no backend supports device: {request.device}",
        )


def device_result_to_tool_result(
    tool_name: str,
    device_result: DeviceExecutionResult,
    *,
    source: str = "device",
) -> ToolResult:
    """将设备执行结果转换为 ToolResult"""
    if device_result.success:
        return ToolResult(
            name=tool_name,
            output=dict(device_result.output),
            source=source,
        )
    else:
        return ToolResult(
            name=tool_name,
            output={
                "error": "device_execution_failed",
                "reason": device_result.error or "unknown error",
            },
            source=source,
        )
