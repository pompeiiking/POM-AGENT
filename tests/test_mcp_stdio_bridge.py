from __future__ import annotations

import sys
from pathlib import Path

import pytest

from core.session.session import (
    Session,
    SessionConfig,
    SessionLimits,
    SessionStats,
    SessionStatus,
)
from core.types import ToolCall
from infra.mcp_config_loader import McpConfigLoaderError, McpConfigSource, load_mcp_config
from infra.mcp_stdio_bridge import McpStdioBridge


def _src_root() -> Path:
    return Path(__file__).resolve().parents[1] / "src"


def _dummy_session() -> Session:
    lim = SessionLimits(
        max_tokens=100,
        max_context_window=100,
        max_loops=5,
        timeout_seconds=60.0,
    )
    cfg = SessionConfig(model="stub", skills=[], security="none", limits=lim)
    return Session(
        session_id="s_test",
        user_id="u",
        channel="c",
        config=cfg,
        status=SessionStatus.ACTIVE,
        stats=SessionStats(),
        messages=[],
    )


@pytest.mark.integration
def test_mcp_demo_server_ping_roundtrip() -> None:
    from dataclasses import replace

    src = _src_root()
    entry = load_mcp_config(
        McpConfigSource(path=src / "platform_layer" / "resources" / "config" / "mcp_servers.yaml"),
        src_root=src,
    ).servers[0]
    entry = replace(entry, command=sys.executable)

    bridge = McpStdioBridge(entry, src_root=src)
    res = bridge.try_call(_dummy_session(), ToolCall(name="ping", arguments={}))
    assert res is not None
    out = res.output
    assert isinstance(out, dict)
    assert out.get("mcp_error") is not True, out


@pytest.mark.integration
def test_mcp_demo_server_add() -> None:
    from dataclasses import replace

    src = _src_root()
    entry = load_mcp_config(
        McpConfigSource(path=src / "platform_layer" / "resources" / "config" / "mcp_servers.yaml"),
        src_root=src,
    ).servers[0]
    entry = replace(entry, command=sys.executable)
    bridge = McpStdioBridge(entry, src_root=src)
    res = bridge.try_call(_dummy_session(), ToolCall(name="add", arguments={"a": 2, "b": 3}))
    assert res is not None
    out = res.output
    assert isinstance(out, dict)
    assert out.get("mcp_error") is not True, out
    dumped = str(out)
    assert "5" in dumped


def test_mcp_config_parses_bridge_ref_default() -> None:
    import tempfile

    src = _src_root()
    yaml_text = "enabled: false\nservers: []\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(yaml_text)
        p = Path(f.name)
    try:
        cfg = load_mcp_config(McpConfigSource(path=p), src_root=src)
        assert cfg.bridge_ref == "builtin:stdio"
    finally:
        p.unlink(missing_ok=True)


def test_mcp_config_parses_bridge_ref_explicit() -> None:
    import tempfile

    src = _src_root()
    yaml_text = 'enabled: false\nbridge_ref: "builtin:stdio"\nservers: []\n'
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(yaml_text)
        p = Path(f.name)
    try:
        cfg = load_mcp_config(McpConfigSource(path=p), src_root=src)
        assert cfg.bridge_ref == "builtin:stdio"
    finally:
        p.unlink(missing_ok=True)


def test_mcp_config_rejects_invalid_bridge_ref() -> None:
    import tempfile

    src = _src_root()
    yaml_text = 'enabled: false\nbridge_ref: "nope"\nservers: []\n'
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(yaml_text)
        p = Path(f.name)
    try:
        with pytest.raises(McpConfigLoaderError):
            load_mcp_config(McpConfigSource(path=p), src_root=src)
    finally:
        p.unlink(missing_ok=True)


def test_mcp_config_rejects_shell_in_args() -> None:
    import tempfile

    src = _src_root()
    bad = "enabled: true\nservers:\n  - id: x\n    command: python\n    args: [\"-c\", \"import os; os.system('rm')\"]\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(bad)
        p = Path(f.name)
    try:
        with pytest.raises(McpConfigLoaderError):
            load_mcp_config(McpConfigSource(path=p), src_root=src)
    finally:
        p.unlink(missing_ok=True)
