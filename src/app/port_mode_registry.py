from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import entry_points

from port.agent_port import CliMode, HttpMode, InteractionMode, WsMode


class PortModeRegistryError(ValueError):
    pass


InteractionModeFactory = Callable[[], InteractionMode]


def validate_interaction_mode_ref_format(ref: str) -> None:
    """
    静态校验 ref 形态（不加载 entry point）。供 ``resource_validation`` 使用。
    """
    r = (ref or "").strip()
    if not r:
        raise PortModeRegistryError("port interaction_mode_ref must be non-empty")
    if r.startswith("builtin:"):
        name = r[len("builtin:") :].strip().lower()
        if name not in ("cli", "http", "ws"):
            raise PortModeRegistryError(
                f"unknown builtin interaction mode: {name!r} (expected cli, http, ws)"
            )
        return
    if r.startswith("entrypoint:"):
        n = r[len("entrypoint:") :].strip()
        if not n:
            raise PortModeRegistryError("entrypoint name must be non-empty")
        return
    raise PortModeRegistryError(
        "interaction_mode_ref must be 'builtin:cli|http|ws' or 'entrypoint:<name>'"
    )


def resolve_interaction_mode(
    ref: str,
    *,
    entrypoint_group: str = "pompeii_agent.interaction_modes",
    discover_fn: Callable[[str], dict[str, InteractionModeFactory]] | None = None,
) -> InteractionMode:
    """
    CLI/WS 等 stdin 循环可选用；HTTP 仍由路由直接 ``GenericAgentPort.handle``。

    - ``builtin:cli`` / ``builtin:http`` / ``builtin:ws``
    - ``entrypoint:<name>``：工厂 ``() -> InteractionMode``，注册到 ``pompeii_agent.interaction_modes``
    """
    r = (ref or "").strip() or "builtin:cli"
    validate_interaction_mode_ref_format(r)
    if r == "builtin:cli":
        return CliMode()
    if r == "builtin:http":
        return HttpMode()
    if r == "builtin:ws":
        return WsMode()
    if r.startswith("entrypoint:"):
        name = r[len("entrypoint:") :].strip()
        if discover_fn is not None:
            reg = discover_fn(entrypoint_group)
        else:
            reg = _discover_mode_factories(group=entrypoint_group)
        factory = reg.get(name)
        if factory is None:
            raise PortModeRegistryError(
                f"interaction mode entrypoint {name!r} not found in group {entrypoint_group!r}"
            )
        obj = factory()
        if not isinstance(obj, InteractionMode):
            raise PortModeRegistryError(
                f"interaction mode entrypoint {name!r} did not return InteractionMode"
            )
        return obj
    raise PortModeRegistryError("unreachable ref resolution")


def _discover_mode_factories(*, group: str) -> dict[str, InteractionModeFactory]:
    eps = entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else [e for e in eps if e.group == group]
    out: dict[str, InteractionModeFactory] = {}
    for ep in selected:
        n = str(ep.name).strip()
        if not n:
            raise PortModeRegistryError(f"entry point in group {group!r} has empty name")
        fn = ep.load()
        if not callable(fn):
            raise PortModeRegistryError(f"entry point {group}:{n} is not callable")
        out[n] = fn  # type: ignore[assignment]
    return out
