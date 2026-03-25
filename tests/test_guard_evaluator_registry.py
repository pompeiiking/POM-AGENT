from __future__ import annotations

import pytest

from app.guard_evaluator_registry import GuardEvaluatorRegistryError, resolve_guard_evaluator


def test_resolve_guard_evaluator_builtin_default_returns_none() -> None:
    got = resolve_guard_evaluator(evaluator_ref="builtin:default")
    assert got is None


def test_resolve_guard_evaluator_builtin_paranoid_matches_text() -> None:
    got = resolve_guard_evaluator(evaluator_ref="builtin:paranoid")
    assert got is not None
    assert got("this contains jailbreak payload") is True
    assert got("normal text") is False


def test_resolve_guard_evaluator_entrypoint_uses_discovered_registry() -> None:
    fake = resolve_guard_evaluator(
        evaluator_ref="entrypoint:custom",
        discover_fn=lambda group: {"custom": (lambda text: "x" in text)},
    )
    assert fake is not None
    assert fake("abcx") is True


def test_resolve_guard_evaluator_rejects_unknown_entrypoint() -> None:
    with pytest.raises(GuardEvaluatorRegistryError):
        resolve_guard_evaluator(
            evaluator_ref="entrypoint:missing",
            discover_fn=lambda group: {},
        )

