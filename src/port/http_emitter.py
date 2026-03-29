from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .events import PortEvent


class HttpEmitter:
    """
    HTTP 对接用 emitter：
    - 每次请求创建一个 emitter
    - Port.handle(...) 期间 emit 的事件都会被收集到 events 中
    - 由 HTTP handler 决定如何序列化返回
    """

    def __init__(self) -> None:
        self.events: list[PortEvent] = []

    def emit(self, event: PortEvent) -> None:
        self.events.append(event)

    def dump(self) -> list[dict[str, Any]]:
        return [asdict(e) for e in self.events]

