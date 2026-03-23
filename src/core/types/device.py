from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class DeviceRequest:
    device: str
    command: str
    parameters: Mapping[str, Any]

