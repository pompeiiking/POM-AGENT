from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KernelConfig:
    """
    内核长期配置（Kernel Governance）。

    设计意图：
    - 会话级策略（model/skills/limits/security）属于 SessionConfig，由 ConfigProvider 提供
    - 内核级兜底与治理参数属于 KernelConfig，由装配层读取并注入 Core
    """

    core_max_loops: int
    max_tool_calls_per_run: int
    tool_allowlist: list[str]
    tool_confirmation_required: list[str]

