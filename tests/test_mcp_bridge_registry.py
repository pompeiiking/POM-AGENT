from __future__ import annotations

from pathlib import Path

import pytest

from app.mcp_bridge_registry import McpBridgeRegistryError, resolve_mcp_bridge
from core.session.session import Session
from core.types import ToolCall
from infra.mcp_config_loader import McpRuntimeConfig, McpServerEntry


def _dummy_entry() -> McpServerEntry:
    return McpServerEntry(id="t", command="python", args=["-c", "pass"])


def _minimal_cfg(*, bridge_ref: str = "builtin:stdio") -> McpRuntimeConfig:
    return McpRuntimeConfig(enabled=True, servers=(_dummy_entry(),), bridge_ref=bridge_ref)


class _StubBridge:
    def try_call(self, session: Session, tool_call: ToolCall):
        return None


def test_resolve_entrypoint_custom_factory(tmp_path: Path) -> None:
    def factory(cfg: McpRuntimeConfig, src_root: Path) -> _StubBridge:
        _ = (cfg, src_root)
        return _StubBridge()

    cfg = _minimal_cfg(bridge_ref="entrypoint:custom")
    br = resolve_mcp_bridge(
        cfg=cfg,
        src_root=tmp_path,
        discover_fn=lambda _g: {"custom": factory},
    )
    assert isinstance(br, _StubBridge)


def test_resolve_entrypoint_missing_raises(tmp_path: Path) -> None:
    cfg = _minimal_cfg(bridge_ref="entrypoint:nope")
    with pytest.raises(McpBridgeRegistryError):
        resolve_mcp_bridge(cfg=cfg, src_root=tmp_path, discover_fn=lambda _g: {})


def test_resolve_unknown_ref_pattern_raises(tmp_path: Path) -> None:
    cfg = McpRuntimeConfig(enabled=True, servers=(_dummy_entry(),), bridge_ref="http:nope")
    with pytest.raises(McpBridgeRegistryError):
        resolve_mcp_bridge(cfg=cfg, src_root=tmp_path)
