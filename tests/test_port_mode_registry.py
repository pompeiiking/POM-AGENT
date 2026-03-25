from __future__ import annotations

import pytest

from app.config_loaders.runtime_config_loader import RuntimeConfigSource, load_runtime_config
from app.port_mode_registry import (
    PortModeRegistryError,
    resolve_interaction_mode,
    validate_interaction_mode_ref_format,
)
from port.agent_port import CliMode, HttpMode, WsMode


def test_validate_builtin_ok() -> None:
    validate_interaction_mode_ref_format("builtin:cli")
    validate_interaction_mode_ref_format("builtin:HTTP")


def test_validate_rejects_unknown_builtin() -> None:
    with pytest.raises(PortModeRegistryError, match="unknown builtin"):
        validate_interaction_mode_ref_format("builtin:stdin")


def test_validate_entrypoint_ok() -> None:
    validate_interaction_mode_ref_format("entrypoint:my_mode")


def test_resolve_builtin_cli() -> None:
    m = resolve_interaction_mode("builtin:cli")
    assert isinstance(m, CliMode)


def test_resolve_builtin_http_ws() -> None:
    assert isinstance(resolve_interaction_mode("builtin:http"), HttpMode)
    assert isinstance(resolve_interaction_mode("builtin:ws"), WsMode)


def test_resolve_custom_entrypoint() -> None:
    class _M(CliMode):
        pass

    m = resolve_interaction_mode(
        "entrypoint:custom",
        discover_fn=lambda _g: {"custom": lambda: _M()},
    )
    assert isinstance(m, _M)


def test_load_runtime_default_port_ref(tmp_path) -> None:
    p = tmp_path / "runtime.yaml"
    p.write_text(
        """
session_store:
  backend: sqlite
  sqlite_path: platform_layer/resources/data/sessions.db
""",
        encoding="utf-8",
    )
    rc = load_runtime_config(RuntimeConfigSource(path=p))
    assert rc.port_interaction_mode_ref == "builtin:cli"


def test_load_runtime_port_section(tmp_path) -> None:
    p = tmp_path / "runtime.yaml"
    p.write_text(
        """
session_store:
  backend: sqlite
  sqlite_path: x.db
port:
  interaction_mode_ref: "builtin:ws"
""",
        encoding="utf-8",
    )
    rc = load_runtime_config(RuntimeConfigSource(path=p))
    assert rc.port_interaction_mode_ref == "builtin:ws"
