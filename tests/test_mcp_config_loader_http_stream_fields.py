from __future__ import annotations

from pathlib import Path

import pytest

from infra.mcp_config_loader import McpConfigLoaderError, McpConfigSource, load_mcp_config


def test_http_server_stream_field_mapping_parse(tmp_path: Path) -> None:
    p = tmp_path / "mcp.yaml"
    p.write_text(
        "\n".join(
            [
                "enabled: true",
                'bridge_ref: "builtin:http_json"',
                "http_servers:",
                "  - id: h1",
                '    base_url: "http://127.0.0.1:8089"',
                "    stream_enabled: true",
                '    stream_endpoint_path: "/stream"',
                '    sse_event_type_key: "event"',
                '    sse_delta_key: "chunk"',
                '    sse_text_key: "txt"',
                '    sse_output_key: "result"',
                '    sse_result_event_value: "done"',
            ]
        ),
        encoding="utf-8",
    )
    cfg = load_mcp_config(McpConfigSource(path=p), src_root=tmp_path)
    hs = cfg.http_servers[0]
    assert hs.stream_enabled is True
    assert hs.sse_event_type_key == "event"
    assert hs.sse_delta_key == "chunk"
    assert hs.sse_text_key == "txt"
    assert hs.sse_output_key == "result"
    assert hs.sse_result_event_value == "done"


def test_http_server_stream_field_mapping_reject_empty(tmp_path: Path) -> None:
    p = tmp_path / "mcp.yaml"
    p.write_text(
        "\n".join(
            [
                "enabled: true",
                'bridge_ref: "builtin:http_json"',
                "http_servers:",
                "  - id: h1",
                '    base_url: "http://127.0.0.1:8089"',
                '    sse_event_type_key: ""',
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(McpConfigLoaderError):
        _ = load_mcp_config(McpConfigSource(path=p), src_root=tmp_path)
