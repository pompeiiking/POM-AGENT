from __future__ import annotations

import pytest

from app.config_loaders.kernel_config_loader import KernelConfigLoaderError, KernelConfigSource, load_kernel_config


def _write(tmp_path, text: str):
    p = tmp_path / "kernel_config.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_kernel_config_delegate_allowlist_ok(tmp_path) -> None:
    p = _write(
        tmp_path,
        """
kernel:
  core_max_loops: 1
  max_tool_calls_per_run: 1
  tool_allowlist: ["echo"]
  tool_confirmation_required: []
  delegate_target_allowlist:
    - worker
    - sub_agent
""",
    )
    cfg = load_kernel_config(KernelConfigSource(path=p))
    assert cfg.delegate_target_allowlist == ("worker", "sub_agent")


def test_kernel_config_delegate_allowlist_empty_default(tmp_path) -> None:
    p = _write(
        tmp_path,
        """
kernel:
  core_max_loops: 1
  max_tool_calls_per_run: 1
  tool_allowlist: ["echo"]
  tool_confirmation_required: []
""",
    )
    cfg = load_kernel_config(KernelConfigSource(path=p))
    assert cfg.delegate_target_allowlist == ()


def test_kernel_config_delegate_allowlist_rejects_bad_token(tmp_path) -> None:
    p = _write(
        tmp_path,
        """
kernel:
  core_max_loops: 1
  max_tool_calls_per_run: 1
  tool_allowlist: ["echo"]
  tool_confirmation_required: []
  delegate_target_allowlist:
    - "bad target"
""",
    )
    with pytest.raises(KernelConfigLoaderError, match="delegate_target_allowlist"):
        load_kernel_config(KernelConfigSource(path=p))
