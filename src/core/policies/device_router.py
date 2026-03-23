from __future__ import annotations

from typing import Callable, Mapping

from core.types import DeviceRequest, ToolCall


def tool_to_device_request(tool_call: ToolCall) -> DeviceRequest | None:
    table: Mapping[str, Callable[[ToolCall], DeviceRequest]] = {
        "take_photo": _take_photo_request,
    }
    builder = table.get(tool_call.name)
    return None if builder is None else builder(tool_call)


def _take_photo_request(tool_call: ToolCall) -> DeviceRequest:
    return DeviceRequest(device="camera", command="take_photo", parameters=dict(tool_call.arguments))

