from __future__ import annotations

import time
from unittest.mock import patch

from infra.model_provider_circuit import (
    clear_model_provider_circuit_state,
    model_circuit_precheck,
    model_circuit_record,
)
from modules.model.config import ModelProvider
from modules.model.interface import ModelOutput


def _p(**params) -> ModelProvider:
    return ModelProvider(id="p1", backend="openai_compatible", params=params, failover_chain=[])


def setup_function() -> None:
    clear_model_provider_circuit_state()


def teardown_function() -> None:
    clear_model_provider_circuit_state()


def test_circuit_disabled_when_threshold_zero() -> None:
    provider = _p(model_circuit_failure_threshold=0)
    fail = ModelOutput(kind="text", content="模型 [p1] 调用失败：boom")
    assert model_circuit_precheck(provider) is None
    model_circuit_record(provider, fail)
    assert model_circuit_precheck(provider) is None


def test_circuit_opens_after_threshold_failures() -> None:
    provider = _p(model_circuit_failure_threshold=2, model_circuit_open_seconds=10.0)
    fail = ModelOutput(kind="text", content="模型 [p1] 调用失败：timeout")

    t = [0.0]

    def mono() -> float:
        return t[0]

    with patch.object(time, "monotonic", mono):
        assert model_circuit_precheck(provider) is None
        model_circuit_record(provider, fail)
        assert model_circuit_precheck(provider) is None
        model_circuit_record(provider, fail)
        blocked = model_circuit_precheck(provider)
        assert blocked is not None
        assert "熔断" in str(blocked.content)

        t[0] = 100.0
        assert model_circuit_precheck(provider) is None


def test_success_resets_failure_streak() -> None:
    provider = _p(model_circuit_failure_threshold=2, model_circuit_open_seconds=10.0)
    fail = ModelOutput(kind="text", content="模型 [p1] 调用失败：x")
    ok = ModelOutput(kind="text", content="hello")

    assert model_circuit_precheck(provider) is None
    model_circuit_record(provider, fail)
    model_circuit_record(provider, ok)
    model_circuit_record(provider, fail)
    assert model_circuit_precheck(provider) is None


def test_tool_call_does_not_count_as_failure() -> None:
    from core.types import ToolCall

    provider = _p(model_circuit_failure_threshold=1, model_circuit_open_seconds=10.0)
    tc = ModelOutput(
        kind="tool_call",
        tool_call=ToolCall(name="x", arguments={}, call_id="1"),
    )
    model_circuit_record(provider, tc)
    assert model_circuit_precheck(provider) is None
