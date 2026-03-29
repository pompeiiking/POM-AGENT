"""
MCP HTTP 传输桥（MVP）：
- 面向网关/代理形态，按固定 JSON 协议调用远端 `POST {base_url}/tools/call`
- 请求体：{"name": "<tool_name>", "arguments": {...}}
- 响应体：{"output": ...} 或任意 JSON（将整体作为 output）
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from core.session.session import Session
from core.types import ToolCall, ToolResult
from infra.mcp_config_loader import McpHttpServerEntry
from modules.tools.mcp_bridge import McpToolBridge


class McpHttpBridge(McpToolBridge):
    def __init__(self, server: McpHttpServerEntry, *, src_root: Path | None = None) -> None:
        self._server = server
        self._src_root = src_root

    def try_call(self, session: Session, tool_call: ToolCall) -> ToolResult | None:
        _ = (session, self._src_root)
        headers: dict[str, str] = {}
        if self._server.api_key_env:
            key = os.getenv(self._server.api_key_env, "")
            if key:
                headers["Authorization"] = f"Bearer {key}"
        try:
            payload = {"name": tool_call.name, "arguments": dict(tool_call.arguments)}
            with httpx.Client(timeout=self._server.timeout_seconds) as c:
                data = self._call_payload(c, payload, headers)
            output = data.get("output") if isinstance(data, dict) and "output" in data else data
            return ToolResult(name=tool_call.name, output=output, source="mcp")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                name=tool_call.name,
                output={"mcp_error": True, "message": str(exc), "server_id": self._server.id},
                source="mcp",
            )

    def _call_payload(self, client: httpx.Client, payload: dict[str, Any], headers: dict[str, str]) -> Any:
        if self._server.stream_enabled:
            out = self._call_stream(client, payload, headers)
            if out is not None:
                return out
        r = client.post(
            f"{self._server.base_url}/tools/call",
            json=payload,
            headers=headers,
        )
        r.raise_for_status()
        return r.json()

    def _call_stream(self, client: httpx.Client, payload: dict[str, Any], headers: dict[str, str]) -> Any | None:
        url = f"{self._server.base_url}{self._server.stream_endpoint_path}"
        with client.stream("POST", url, json=payload, headers=headers) as r:
            r.raise_for_status()
            acc_text: list[str] = []
            for line in r.iter_lines():
                if not line:
                    continue
                s = str(line).strip()
                if not s.startswith("data:"):
                    continue
                body = s[len("data:") :].strip()
                if body == "[DONE]":
                    break
                try:
                    obj = json.loads(body)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                t = obj.get(self._server.sse_event_type_key)
                if t == self._server.sse_result_event_value and self._server.sse_output_key in obj:
                    return obj[self._server.sse_output_key]
                delta = obj.get(self._server.sse_delta_key)
                if isinstance(delta, str):
                    acc_text.append(delta)
                text = obj.get(self._server.sse_text_key)
                if isinstance(text, str):
                    acc_text.append(text)
            if acc_text:
                return {"text": "".join(acc_text)}
            return None


class McpMultiHttpBridge(McpToolBridge):
    def __init__(self, servers: tuple[McpHttpServerEntry, ...], *, src_root: Path | None = None) -> None:
        self._servers = servers
        self._src_root = src_root

    def try_call(self, session: Session, tool_call: ToolCall) -> ToolResult | None:
        last_err: ToolResult | None = None
        for s in self._servers:
            res = McpHttpBridge(s, src_root=self._src_root).try_call(session, tool_call)
            if res is None:
                continue
            if isinstance(res.output, dict) and res.output.get("mcp_error") is True:
                last_err = res
                continue
            return res
        return last_err
