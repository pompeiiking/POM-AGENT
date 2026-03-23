from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

from core.types import ToolCall

if TYPE_CHECKING:
    from core.session.session import Session


@dataclass(frozen=True)
class ModelOutput:
    kind: Literal["text", "tool_call"]
    content: str | None = None
    tool_call: ToolCall | None = None


class ModelModule(Protocol):
    def run(self, session: Session, context: Any) -> ModelOutput: ...

