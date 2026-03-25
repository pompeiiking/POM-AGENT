from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ArchiveDialogueSummarizer(Protocol):
    """由装配层注入：按 provider 与对话纯文本生成归档摘要（可阻塞；Core 仅在后台线程调用）。"""

    def __call__(
        self,
        *,
        provider_id: str,
        dialogue_plain: str,
        max_output_chars: int,
        system_prompt: str,
    ) -> str:
        ...


@dataclass(frozen=True, slots=True)
class ArchiveLlmSummaryBinding:
    """archive_llm_summary_enabled 为真时由 composition 注入 AgentCore。"""

    provider_id: str
    max_dialogue_chars: int
    max_output_chars: int
    system_prompt: str
    summarize: ArchiveDialogueSummarizer
