from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union


@dataclass(frozen=True, slots=True)
class UserMessageInput:
    kind: Literal["user_message"]
    text: str


@dataclass(frozen=True, slots=True)
class SystemCommandInput:
    kind: Literal["system_command"]
    text: str


@dataclass(frozen=True, slots=True)
class DeviceResultInput:
    kind: Literal["device_result"]
    payload: str


PortInput = Union[UserMessageInput, SystemCommandInput, DeviceResultInput]

