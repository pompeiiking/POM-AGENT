from __future__ import annotations

from dataclasses import dataclass

from core.kernel_config import KernelConfig
from core.types import ToolCall


@dataclass(frozen=True)
class ToolPolicyDecision:
    allowed: bool
    reason: str | None
    needs_confirmation: bool


def decide_tool_policy(
    *,
    tool_call: ToolCall,
    kernel_config: KernelConfig,
    bypass_tool_confirmation: bool,
) -> ToolPolicyDecision:
    allowset = set(kernel_config.tool_allowlist)
    confirmset = set(kernel_config.tool_confirmation_required)

    allowed = tool_call.name in allowset
    if not allowed:
        return ToolPolicyDecision(allowed=False, reason="tool_not_allowed", needs_confirmation=False)

    requires_confirmation = tool_call.name in confirmset
    needs_confirmation = requires_confirmation and (not bypass_tool_confirmation)
    return ToolPolicyDecision(allowed=True, reason=None, needs_confirmation=needs_confirmation)

