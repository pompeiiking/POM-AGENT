from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from core.agent_types import AgentResponse
from core.session.session import Session
from modules.model.interface import ModelOutput


@dataclass(frozen=True)
class OutputStep:
    response: AgentResponse | None
    context: Any


class OutputHandler(Protocol):
    def __call__(
        self,
        request_id: str,
        session: Session,
        context: Any,
        output: ModelOutput,
    ) -> OutputStep: ...


def build_output_handlers(
    *,
    on_text: Callable[[str, Session, ModelOutput], AgentResponse],
    on_tool_call: Callable[[str, Session, Any, ModelOutput], OutputStep],
) -> Mapping[str, OutputHandler]:
    def handle_text(
        request_id: str,
        session: Session,
        context: Any,
        output: ModelOutput,
    ) -> OutputStep:
        return OutputStep(response=on_text(request_id, session, output), context=context)

    def handle_tool_call(
        request_id: str,
        session: Session,
        context: Any,
        output: ModelOutput,
    ) -> OutputStep:
        return on_tool_call(request_id, session, context, output)

    return {
        "text": handle_text,
        "tool_call": handle_tool_call,
    }


def resolve_handler(
    *,
    handlers: Mapping[str, OutputHandler],
    kind: str,
    on_unsupported: Callable[[str, Session, ModelOutput], OutputStep],
) -> OutputHandler:
    supported = kind in handlers
    actions = {
        True: lambda: handlers[kind],
        False: lambda: (lambda request_id, session, context, output: on_unsupported(request_id, session, output)),
    }
    return actions[supported]()

