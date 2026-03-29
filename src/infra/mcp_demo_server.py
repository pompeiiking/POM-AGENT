"""
本地演示用 MCP Server（stdio），仅用于开发与测试。

安全说明：勿在生产直接暴露；生产应使用官方 Registry 中已审计的 Server，
并配合 allowlist、网络隔离与最小权限（参见 modelcontextprotocol.io/registry、awesome-secure-mcp-servers）。

运行（在仓库 `pompeii` 根目录，且 PYTHONPATH 含 `src`）::

    python -m infra.mcp_demo_server
"""

from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pompeii-demo", json_response=True)


@mcp.tool()
def ping() -> str:
    """Liveness check for MCP integration."""
    return "pong"


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def main() -> None:
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
