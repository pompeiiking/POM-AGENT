"""设备后端注册表测试"""

from __future__ import annotations

import pytest

from core.types import DeviceRequest
from modules.tools.device_backend import (
    CompositeDeviceBackend,
    DeviceExecutionResult,
    LocalSimulatorBackend,
    device_result_to_tool_result,
)
from app.device_backend_registry import (
    NoopDeviceBackend,
    build_device_backend,
    resolve_device_backend,
)


class TestLocalSimulatorBackend:
    def test_supports_camera(self) -> None:
        backend = LocalSimulatorBackend()
        assert backend.supports("camera")
        assert backend.supports("microphone")
        assert backend.supports("speaker")
        assert backend.supports("display")
        assert backend.supports("filesystem")
        assert not backend.supports("unknown_device")

    def test_camera_take_photo(self) -> None:
        backend = LocalSimulatorBackend()
        request = DeviceRequest(
            device="camera",
            command="take_photo",
            parameters={"quality": "high"},
        )
        result = backend.execute(request)
        assert result.success
        assert result.output["type"] == "image"
        assert result.output["quality"] == "high"
        assert result.output["simulated"] is True
        assert "path" in result.output

    def test_camera_unknown_command(self) -> None:
        backend = LocalSimulatorBackend()
        request = DeviceRequest(
            device="camera",
            command="unknown_command",
            parameters={},
        )
        result = backend.execute(request)
        assert not result.success
        assert "unknown camera command" in (result.error or "")

    def test_microphone_record(self) -> None:
        backend = LocalSimulatorBackend()
        request = DeviceRequest(
            device="microphone",
            command="record",
            parameters={"duration_seconds": 10},
        )
        result = backend.execute(request)
        assert result.success
        assert result.output["type"] == "audio"
        assert result.output["duration_seconds"] == 10

    def test_speaker_play(self) -> None:
        backend = LocalSimulatorBackend()
        request = DeviceRequest(
            device="speaker",
            command="play",
            parameters={"text": "Hello, world!"},
        )
        result = backend.execute(request)
        assert result.success
        assert result.output["type"] == "tts"
        assert result.output["text"] == "Hello, world!"

    def test_display_show(self) -> None:
        backend = LocalSimulatorBackend()
        request = DeviceRequest(
            device="display",
            command="show",
            parameters={"content": "Test content"},
        )
        result = backend.execute(request)
        assert result.success
        assert result.output["type"] == "display"

    def test_filesystem_read(self) -> None:
        backend = LocalSimulatorBackend()
        request = DeviceRequest(
            device="filesystem",
            command="read",
            parameters={"path": "/test/file.txt"},
        )
        result = backend.execute(request)
        assert result.success
        assert result.output["type"] == "file_content"

    def test_filesystem_list(self) -> None:
        backend = LocalSimulatorBackend()
        request = DeviceRequest(
            device="filesystem",
            command="list",
            parameters={"path": "/test"},
        )
        result = backend.execute(request)
        assert result.success
        assert result.output["type"] == "directory_listing"
        assert "entries" in result.output

    def test_unsupported_device(self) -> None:
        backend = LocalSimulatorBackend()
        request = DeviceRequest(
            device="unknown_device",
            command="do_something",
            parameters={},
        )
        result = backend.execute(request)
        assert not result.success
        assert "unsupported device" in (result.error or "")


class TestNoopDeviceBackend:
    def test_supports_all_devices(self) -> None:
        backend = NoopDeviceBackend()
        assert backend.supports("camera")
        assert backend.supports("any_device")
        assert backend.supports("unknown")

    def test_execute_returns_success(self) -> None:
        backend = NoopDeviceBackend()
        request = DeviceRequest(
            device="camera",
            command="take_photo",
            parameters={"quality": "high"},
        )
        result = backend.execute(request)
        assert result.success
        assert result.output["noop"] is True
        assert result.output["device"] == "camera"
        assert result.output["command"] == "take_photo"


class TestCompositeDeviceBackend:
    def test_uses_first_supporting_backend(self) -> None:
        simulator = LocalSimulatorBackend()
        noop = NoopDeviceBackend()
        composite = CompositeDeviceBackend([simulator, noop])

        request = DeviceRequest(
            device="camera",
            command="take_photo",
            parameters={},
        )
        result = composite.execute(request)
        assert result.success
        assert result.output.get("simulated") is True

    def test_falls_back_to_noop(self) -> None:
        simulator = LocalSimulatorBackend()
        noop = NoopDeviceBackend()
        composite = CompositeDeviceBackend([simulator, noop])

        request = DeviceRequest(
            device="unknown_device",
            command="do_something",
            parameters={},
        )
        result = composite.execute(request)
        assert result.success
        assert result.output.get("noop") is True

    def test_no_backend_supports(self) -> None:
        composite = CompositeDeviceBackend([])
        request = DeviceRequest(
            device="camera",
            command="take_photo",
            parameters={},
        )
        result = composite.execute(request)
        assert not result.success
        assert "no backend supports" in (result.error or "")


class TestResolveDeviceBackend:
    def test_builtin_simulator(self) -> None:
        backend = resolve_device_backend("builtin:simulator")
        assert isinstance(backend, LocalSimulatorBackend)

    def test_builtin_noop(self) -> None:
        backend = resolve_device_backend("builtin:noop")
        assert isinstance(backend, NoopDeviceBackend)

    def test_invalid_ref_no_colon(self) -> None:
        with pytest.raises(ValueError, match="invalid device_backend_ref"):
            resolve_device_backend("invalid")

    def test_unknown_builtin(self) -> None:
        with pytest.raises(ValueError, match="unknown builtin device backend"):
            resolve_device_backend("builtin:unknown")

    def test_unknown_prefix(self) -> None:
        with pytest.raises(ValueError, match="unknown device_backend_ref prefix"):
            resolve_device_backend("unknown:something")


class TestBuildDeviceBackend:
    def test_single_ref(self) -> None:
        backend = build_device_backend(["builtin:simulator"])
        assert isinstance(backend, LocalSimulatorBackend)

    def test_multiple_refs(self) -> None:
        backend = build_device_backend(["builtin:simulator", "builtin:noop"])
        assert isinstance(backend, CompositeDeviceBackend)

    def test_fallback_to_simulator(self) -> None:
        backend = build_device_backend(None, fallback_to_simulator=True)
        assert isinstance(backend, LocalSimulatorBackend)

    def test_no_fallback(self) -> None:
        backend = build_device_backend(None, fallback_to_simulator=False)
        assert isinstance(backend, CompositeDeviceBackend)


class TestDeviceResultToToolResult:
    def test_success_result(self) -> None:
        device_result = DeviceExecutionResult(
            success=True,
            output={"type": "image", "path": "/tmp/photo.jpg"},
        )
        tool_result = device_result_to_tool_result("take_photo", device_result)
        assert tool_result.name == "take_photo"
        assert tool_result.output["type"] == "image"
        assert tool_result.source == "device"

    def test_failure_result(self) -> None:
        device_result = DeviceExecutionResult(
            success=False,
            output={},
            error="device not available",
        )
        tool_result = device_result_to_tool_result("take_photo", device_result)
        assert tool_result.name == "take_photo"
        assert tool_result.output["error"] == "device_execution_failed"
        assert tool_result.output["reason"] == "device not available"
