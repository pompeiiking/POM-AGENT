from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any, Callable, Mapping


GuardEvaluator = Callable[[str], bool]


class GuardEvaluatorRegistryError(ValueError):
    pass


def discover_guard_evaluators(*, group: str) -> dict[str, GuardEvaluator]:
    eps = entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else [e for e in eps if e.group == group]
    evaluators: dict[str, GuardEvaluator] = {}
    for ep in selected:
        name = str(ep.name).strip()
        if not name:
            raise GuardEvaluatorRegistryError(f"entry point in group {group!r} has empty name")
        fn = ep.load()
        if not callable(fn):
            raise GuardEvaluatorRegistryError(f"entry point {group}:{name} is not callable")
        evaluators[name] = fn
    return evaluators


def resolve_guard_evaluator(
    *,
    evaluator_ref: str,
    entrypoint_group: str = "pompeii_agent.guard_evaluators",
    discover_fn: Callable[[str], Mapping[str, GuardEvaluator]] | None = None,
) -> GuardEvaluator | None:
    ref = str(evaluator_ref).strip()
    if not ref:
        return None
    if ref.startswith("builtin:"):
        name = ref[len("builtin:") :].strip().lower()
        return _builtin_guard_evaluator(name)
    if ref.startswith("entrypoint:"):
        name = ref[len("entrypoint:") :].strip()
        if not name:
            raise GuardEvaluatorRegistryError("guard evaluator entrypoint name must be non-empty")
        discover = discover_fn or (lambda g: discover_guard_evaluators(group=g))
        registry = dict(discover(entrypoint_group))
        evaluator = registry.get(name)
        if evaluator is None:
            raise GuardEvaluatorRegistryError(
                f"guard evaluator entrypoint {name!r} not found in group {entrypoint_group!r}"
            )
        return evaluator
    raise GuardEvaluatorRegistryError(
        "guard_evaluator_ref must start with 'builtin:' or 'entrypoint:'"
    )


def _builtin_guard_evaluator(name: str) -> GuardEvaluator | None:
    if name in ("", "none", "default"):
        return None
    if name == "paranoid":
        patterns = ("bypass", "jailbreak", "prompt injection", "system prompt")
        return lambda text: any(p in str(text).lower() for p in patterns)
    raise GuardEvaluatorRegistryError(f"unknown builtin guard evaluator: {name!r}")

