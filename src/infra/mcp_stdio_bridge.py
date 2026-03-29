"""
MCP stdio 客户端桥接：实现 `McpToolBridge`，在独立线程中 `asyncio.run` 一次会话级调用。

安全说明：
- 仅使用 `mcp_servers.yaml` 中声明的 command/args/env；
- 不在本模块中拼接用户可控字符串到进程启动参数；
- 超时由配置 `timeout_seconds` 控制。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

from infra.mcp_config_loader import McpServerEntry
from core.session.session import Session
from core.types import ToolCall, ToolResult
from modules.tools.mcp_bridge import McpToolBridge


def _call_tool_result_to_output(result: CallToolResult) -> Any:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    return {
        "isError": result.isError,
        "content": [
            {"type": c.type, "text": getattr(c, "text", None)} for c in (result.content or [])
        ],
    }


class McpStdioBridge(McpToolBridge):
    """连接单个 stdio MCP Server 的配置化桥接。"""

    def __init__(self, server: McpServerEntry, *, src_root: Path | None = None) -> None:
        self._server = server
        self._src_root = src_root.resolve() if src_root is not None else None

    def try_call(self, session: Session, tool_call: ToolCall) -> ToolResult | None:
        _ = session
        return _run_mcp_tool_call_sync(self._server, tool_call, src_root=self._src_root)


def _run_mcp_tool_call_sync(
    entry: McpServerEntry,
    tool_call: ToolCall,
    *,
    src_root: Path | None,
) -> ToolResult | None:
    timeout = entry.timeout_seconds

    async def _once() -> ToolResult:
        env = dict(entry.env) if entry.env else None
        if env is None and src_root is not None:
            env = {"PYTHONPATH": str(src_root)}
        elif env is not None and "PYTHONPATH" not in env and src_root is not None:
            env = {**env, "PYTHONPATH": str(src_root)}

        params = StdioServerParameters(
            command=entry.command,
            args=list(entry.args),
            env=env,
            cwd=entry.cwd,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as mcp_session:
                await mcp_session.initialize()
                args_dict = dict(tool_call.arguments)
                result = await asyncio.wait_for(
                    mcp_session.call_tool(tool_call.name, args_dict),
                    timeout=timeout,
                )
                return ToolResult(
                    name=tool_call.name,
                    output=_call_tool_result_to_output(result),
                    source="mcp",
                )

    def _runner() -> ToolResult:
        return asyncio.run(_once())

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_runner)
            return future.result(timeout=timeout + 15.0)
    except Exception as exc:  # noqa: BLE001 — 返回可诊断错误，不冒泡
        return ToolResult(
            name=tool_call.name,
            output={
                "mcp_error": True,
                "message": str(exc),
                "server_id": entry.id,
            },
            source="mcp",
        )


class McpMultiStdioBridge(McpToolBridge):
    """按配置顺序依次尝试多个 stdio server；成功（无 mcp_error）则返回，否则尝试下一个。"""

    def __init__(self, servers: tuple[McpServerEntry, ...], *, src_root: Path | None = None) -> None:
        self._servers = servers
        self._src_root = src_root

    def try_call(self, session: Session, tool_call: ToolCall) -> ToolResult | None:
        _ = session
        last_err: ToolResult | None = None
        for s in self._servers:
            res = _run_mcp_tool_call_sync(s, tool_call, src_root=self._src_root)
            if res is None:
                continue
            out = res.output
            if isinstance(out, dict) and out.get("mcp_error") is True:
                last_err = res
                continue
            return res
        return last_err
