from __future__ import annotations

import time
from unittest.mock import patch

from infra.model_provider_rate_limit import (
    clear_model_provider_rate_limit_state,
    model_rate_precheck,
)
from modules.model.config import ModelProvider
from modules.model.interface import ModelOutput


def _p(**params) -> ModelProvider:
    return ModelProvider(id="rl1", backend="openai_compatible", params=params, failover_chain=[])


def setup_function() -> None:
    clear_model_provider_rate_limit_state()


def teardown_function() -> None:
    clear_model_provider_rate_limit_state()


def test_rate_limit_disabled_when_max_zero() -> None:
    p = _p(model_rate_max_calls_per_window=0)
    assert model_rate_precheck(p) is None
    assert model_rate_precheck(p) is None


def test_rate_limit_allows_within_window() -> None:
    p = _p(model_rate_max_calls_per_window=3, model_rate_window_seconds=10.0)
    assert model_rate_precheck(p) is None
    assert model_rate_precheck(p) is None
    assert model_rate_precheck(p) is None


def test_rate_limit_blocks_fourth_call() -> None:
    p = _p(model_rate_max_calls_per_window=3, model_rate_window_seconds=10.0)
    assert model_rate_precheck(p) is None
    assert model_rate_precheck(p) is None
    assert model_rate_precheck(p) is None
    blocked = model_rate_precheck(p)
    assert blocked is not None
    assert "过于频繁" in str(blocked.content)


def test_rate_limit_recovers_after_window() -> None:
    p = _p(model_rate_max_calls_per_window=1, model_rate_window_seconds=5.0)
    t = [0.0]

    def mono() -> float:
        return t[0]

    with patch.object(time, "monotonic", mono):
        assert model_rate_precheck(p) is None
        assert model_rate_precheck(p) is not None
        t[0] = 6.0
        assert model_rate_precheck(p) is None
