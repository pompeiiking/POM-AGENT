from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import entry_points
from core.kernel_config import KernelConfig
from core.policies.tool_policy import ToolPolicyDecision, decide_tool_policy
from core.types import ToolCall


class ToolPolicyRegistryError(ValueError):
    pass


ToolPolicyDecideFn = Callable[..., ToolPolicyDecision]


def resolve_tool_policy_decide(
    ref: str,
    *,
    entrypoint_group: str = "pompeii_agent.tool_policies",
    discover_fn: Callable[[str], dict[str, ToolPolicyDecideFn]] | None = None,
) -> ToolPolicyDecideFn:
    """
    - ``builtin:default``：内置 ``decide_tool_policy``
    - ``entrypoint:<name>``：签名为 ``(*, tool_call: ToolCall, kernel_config: KernelConfig, bypass_tool_confirmation: bool) -> ToolPolicyDecision``
    """
    r = (ref or "").strip() or "builtin:default"
    if r == "builtin:default":
        return decide_tool_policy
    if r.startswith("entrypoint:"):
        name = r[len("entrypoint:") :].strip()
        if not name:
            raise ToolPolicyRegistryError("tool policy entrypoint name must be non-empty")
        if discover_fn is not None:
            reg = discover_fn(entrypoint_group)
        else:
            reg = _discover_tool_policy_callables(group=entrypoint_group)
        fn = reg.get(name)
        if fn is None:
            raise ToolPolicyRegistryError(
                f"tool policy entrypoint {name!r} not found in group {entrypoint_group!r}"
            )
        if not callable(fn):
            raise ToolPolicyRegistryError(f"tool policy entrypoint {name!r} is not callable")
        return fn  # type: ignore[return-value]
    raise ToolPolicyRegistryError("tool_policy_engine_ref must be 'builtin:default' or 'entrypoint:<name>'")


def _discover_tool_policy_callables(*, group: str) -> dict[str, ToolPolicyDecideFn]:
    eps = entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else [e for e in eps if e.group == group]
    out: dict[str, ToolPolicyDecideFn] = {}
    for ep in selected:
        n = str(ep.name).strip()
        if not n:
            raise ToolPolicyRegistryError(f"entry point in group {group!r} has empty name")
        fn = ep.load()
        if not callable(fn):
            raise ToolPolicyRegistryError(f"entry point {group}:{n} is not callable")
        out[n] = fn  # type: ignore[assignment]
    return out
