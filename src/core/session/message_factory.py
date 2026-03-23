from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from .session import Message, Part


def new_message(*, role: str, content: Any, loop_index: int) -> Message:
    part_content = content if isinstance(content, (str, dict, bytes)) else str(content)
    return Message(
        message_id=uuid4().hex,
        role=role,
        parts=[Part(type="text", content=part_content, metadata={})],
        timestamp=datetime.now(),
        loop_index=loop_index,
        token_count=0,
    )

