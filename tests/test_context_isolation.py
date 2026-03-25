from __future__ import annotations

import pytest

from modules.assembly.context_isolation import (
    format_isolated_zone,
    tool_execution_source_token,
    trust_for_tool_result_source,
)


def test_format_isolated_zone_wraps_body() -> None:
    out = format_isolated_zone("memory", "hello", source="long_term_memory", trust="medium")
    assert "pompeii:zone-begin" in out
    assert "name=memory" in out
    assert "source=long_term_memory" in out
    assert "trust=medium" in out
    assert "hello" in out
    assert "pompeii:zone-end" in out


def test_format_isolated_zone_rejects_bad_tokens() -> None:
    with pytest.raises(ValueError):
        format_isolated_zone("bad zone", "x", source="a", trust="high")


def test_trust_for_tool_result_source() -> None:
    assert trust_for_tool_result_source("mcp") == "low"
    assert trust_for_tool_result_source("device") == "low"
    assert trust_for_tool_result_source(None) == "high"


def test_tool_execution_source_token() -> None:
    assert tool_execution_source_token(None) == "local"
    assert tool_execution_source_token("mcp") == "mcp"
    assert tool_execution_source_token("weird;rm") == "unknown"
