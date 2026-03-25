from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import entry_points

from core.kernel_config import KernelConfig
from core.policies.loop_policy import LoopGovernance, build_loop_governance
from core.session.session import Session


class LoopPolicyRegistryError(ValueError):
    pass


LoopGovernanceFn = Callable[[Session, KernelConfig], LoopGovernance]


def resolve_loop_governance_fn(
    ref: str,
    *,
    entrypoint_group: str = "pompeii_agent.loop_policies",
    discover_fn: Callable[[str], dict[str, LoopGovernanceFn]] | None = None,
) -> LoopGovernanceFn:
    """
    - ``builtin:default``：``build_loop_governance``
    - ``entrypoint:<name>``：``(session, kernel_config) -> LoopGovernance``
    """
    r = (ref or "").strip() or "builtin:default"
    if r == "builtin:default":

        def _default(session: Session, kernel_config: KernelConfig) -> LoopGovernance:
            return build_loop_governance(session=session, kernel_config=kernel_config)

        return _default
    if r.startswith("entrypoint:"):
        name = r[len("entrypoint:") :].strip()
        if not name:
            raise LoopPolicyRegistryError("loop policy entrypoint name must be non-empty")
        if discover_fn is not None:
            reg = discover_fn(entrypoint_group)
        else:
            reg = _discover_loop_fns(group=entrypoint_group)
        fn = reg.get(name)
        if fn is None:
            raise LoopPolicyRegistryError(
                f"loop policy entrypoint {name!r} not found in group {entrypoint_group!r}"
            )
        if not callable(fn):
            raise LoopPolicyRegistryError(f"loop policy entrypoint {name!r} is not callable")
        return fn  # type: ignore[return-value]
    raise LoopPolicyRegistryError("loop_policy_engine_ref must be 'builtin:default' or 'entrypoint:<name>'")


def _discover_loop_fns(*, group: str) -> dict[str, LoopGovernanceFn]:
    eps = entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else [e for e in eps if e.group == group]
    out: dict[str, LoopGovernanceFn] = {}
    for ep in selected:
        n = str(ep.name).strip()
        if not n:
            raise LoopPolicyRegistryError(f"entry point in group {group!r} has empty name")
        fn = ep.load()
        if not callable(fn):
            raise LoopPolicyRegistryError(f"entry point {group}:{n} is not callable")
        out[n] = fn  # type: ignore[assignment]
    return out
