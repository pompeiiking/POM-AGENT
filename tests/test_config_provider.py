from __future__ import annotations

import pytest

from app.config_provider import in_memory_mapping_config_provider
from app.config_loaders.session_config_loader import SessionConfigLoaderError, load_session_config_from_mapping


def _session_mapping() -> dict[str, object]:
    return {
        "session": {
            "model": "stub",
            "skills": [],
            "security": "baseline",
            "limits": {
                "max_tokens": 1024,
                "max_context_window": 2048,
                "max_loops": 3,
                "timeout_seconds": 30.0,
                "assembly_token_counter": "heuristic",
            },
        }
    }


def test_load_session_config_from_mapping() -> None:
    cfg = load_session_config_from_mapping(_session_mapping())
    assert cfg.model == "stub"
    assert cfg.limits.max_loops == 3
    assert cfg.limits.assembly_token_counter == "heuristic"


def test_in_memory_mapping_config_provider_returns_same_session_config() -> None:
    provider = in_memory_mapping_config_provider(_session_mapping())
    c1 = provider("u1", "c1")
    c2 = provider("u2", "c2")
    assert c1 is c2
    assert c1.model == "stub"


def test_load_session_config_from_mapping_rejects_invalid_shape() -> None:
    with pytest.raises(SessionConfigLoaderError):
        load_session_config_from_mapping({"session": {"model": "stub"}})
