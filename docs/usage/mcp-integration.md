# MCP 集成

## 什么是 MCP

MCP（Model Context Protocol）是 Anthropic 提出的工具调用协议。Pompeii-Agent 通过 MCP 桥接器接入任何 MCP 服务器，使 Agent 能调用远程 MCP 工具。

---

## MCP 桥接器类型

| 桥接器 | 说明 | 使用场景 |
|--------|------|---------|
| `McpStdioBridge` | 通过子进程 stdio 通信 | 本地 MCP 服务器 |
| `McpHttpBridge` | 通过 HTTP 调用 MCP 服务器 | 远程 MCP 服务器（轮询） |
| `McpMultiStdioBridge` | 同时管理多个 Stdio 桥接 | 接入多个 MCP 服务器 |
| `McpMultiHttpBridge` | 同时管理多个 HTTP 桥接 | 接入多个远程 MCP 服务器 |

---

## McpStdioBridge — 本地 MCP 服务器

### 定义 MCP 服务器入口

```python
from pompeii_agent import McpStdioBridge, McpServerEntry

bridge = McpStdioBridge(server=McpServerEntry(
    id="weather-server",
    command="python",
    args=["-m", "my_mcp_weather_server"],
    env={"API_KEY": "my-key"},     # 可选，环境变量
    timeout=30.0,                  # 可选，通信超时
))
```

### 注入到 Agent

```python
from pompeii_agent import AgentBuilder, ToolBuilder

kernel = (
    AgentBuilder()
    .tool()
        .mcp_bridge(bridge)
    .done()
    .build()
)
```

### MCP 服务器配置（MCP 服务器端）

MCP 服务器接受以下格式的 JSON-RPC 消息（stdio）：

**初始化请求：**

```json
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {...}}
```

**工具调用：**

```json
{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "get_weather", "arguments": {"city": "Shanghai"}}}
```

---

## McpHttpBridge — 远程 MCP 服务器

```python
from pompeii_agent import McpHttpBridge, McpHttpServerEntry

bridge = McpHttpBridge(server=McpHttpServerEntry(
    id="remote-weather",
    url="https://mcp.example.com/rpc",
    headers={"Authorization": "Bearer my-token"},  # 可选
    timeout=30.0,
))
```

---

## McpMultiStdioBridge — 多 MCP 服务器

同时接入多个 MCP 服务器：

```python
from pompeii_agent import McpMultiStdioBridge, McpServerEntry

bridge = McpMultiStdioBridge(servers=[
    McpServerEntry(id="weather", command="python", args=["-m", "weather_server"]),
    McpServerEntry(id="search", command="python", args=["-m", "search_server"]),
])

kernel = AgentBuilder().tool().mcp_bridge(bridge).done().build()
```

---

## McpMultiHttpBridge — 多远程 MCP 服务器

```python
from pompeii_agent import McpMultiHttpBridge, McpHttpServerEntry

bridge = McpMultiHttpBridge(servers=[
    McpHttpServerEntry(id="remote-weather", url="https://mcp1.example.com/rpc"),
    McpHttpServerEntry(id="remote-search", url="https://mcp2.example.com/rpc"),
])
```

---

## MCP 工具白名单

通过 `allowlist_mcp_tools()` 限制 Agent 可用的 MCP 工具：

```python
from pompeii_agent import ToolBuilder

tb = (
    ToolBuilder()
    .mcp_bridge(bridge)
    .allowlist_mcp_tools(["get_weather", "search"])
)
```

**等价于 `ToolNetworkPolicyConfig` 配置：**

```python
from pompeii_agent import ToolNetworkPolicyConfig

policy = ToolNetworkPolicyConfig(
    enabled=True,
    mcp_allowlist_enforced=True,
    mcp_tool_allowlist=("get_weather", "search"),
)

tb = ToolBuilder().mcp_bridge(bridge).network_policy(policy)
```

---

## MCP 运行时配置（MCP YAML）

通过 YAML 文件配置 MCP 服务器（可选，编程式注入更推荐）：

```yaml
# mcp_servers.yaml
enabled: true
servers:
  - id: weather
    type: stdio
    command: python
    args: ["-m", "weather_server"]
    env:
      API_KEY: "${WEATHER_API_KEY}"
  - id: remote-search
    type: http
    url: https://mcp.example.com/rpc
    headers:
      Authorization: "Bearer ${SEARCH_TOKEN}"
```

加载：

```python
from pompeii_agent.advanced import resolve_mcp_bridge
from infra import McpConfigSource, load_mcp_config

cfg = load_mcp_config(McpConfigSource(path="path/to/mcp_servers.yaml"), src_root=root)
bridge = resolve_mcp_bridge(cfg=cfg, src_root=root)
```

---

## resolve_mcp_bridge — 动态解析 MCP 桥接器

```python
from pompeii_agent.advanced import resolve_mcp_bridge

bridge = resolve_mcp_bridge(cfg=mcp_config, src_root=root_path)
```

根据配置类型自动选择 `McpStdioBridge` 或 `McpHttpBridge`。

---

## 自定义 MCP 桥接器

实现 `McpToolBridge` 接口：

```python
from pompeii_agent.advanced import McpToolBridge

class MyMcpBridge(McpToolBridge):
    def try_call(self, session: Session, tool_call: ToolCall) -> ToolResult | None:
        # 自定义逻辑
        if tool_call.name.startswith("my_"):
            return ToolResult(name=tool_call.name, output={"custom": True})
        return None  # 不处理，交由下一环节

    def list_tools(self) -> list[str]:
        return []
```

注入方式与其他桥接器相同：

```python
tb = ToolBuilder().mcp_bridge(MyMcpBridge())
```
