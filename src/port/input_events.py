from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Union


@dataclass(frozen=True, slots=True)
class UserMessageInput:
    kind: Literal["user_message"]
    text: str
    stream: bool = False
    # OpenAI Chat 风格 user content 块（text / image_url）；与 text 并存时 text 可作 caption 与意图解析
    openai_user_content: tuple[dict[str, Any], ...] | None = None


@dataclass(frozen=True, slots=True)
class SystemCommandInput:
    kind: Literal["system_command"]
    text: str


@dataclass(frozen=True, slots=True)
class DeviceResultInput:
    kind: Literal["device_result"]
    payload: str


PortInput = Union[UserMessageInput, SystemCommandInput, DeviceResultInput]

