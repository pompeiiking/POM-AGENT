# 工具子系统详解

## 概览

```
用户输入
    │
    ▼
ToolModule.execute(session, ToolCall)
    │
    ├── 1. 本地 handlers 查找（local_handlers dict）
    │       ├── 命中 → 返回 ToolResult
    │       └── 未命中
    ├── 2. MCP 桥接回退（McpToolBridge.try_call）
    │       ├── 命中 → 返回 ToolResult
    │       └── 未命中
    └── 3. 返回 error: "unknown tool"
```

---

## 工具处理器签名

```python
from pompeii_agent import ToolHandler, Session, ToolCall, ToolResult

def my_handler(session: Session, tool_call: ToolCall) -> ToolResult:
    return ToolResult(
        name=tool_call.name,
        output={"result": "..."},
        source="my_handler",   # 可选，标识工具来源
    )
```

---

## 注册工具的三种方式

### 1. 直接注册可调用对象（推荐）

```python
from pompeii_agent import ToolBuilder, echo_handler

tb = (
    ToolBuilder()
    .register_handler("echo", echo_handler)   # 直接函数引用
    .register_handler("weather", my_weather_handler)  # 任何 Callable
)
```

### 2. 字符串引用（自动动态 import）

```python
tb = (
    ToolBuilder()
    .register("weather", "mypackage.weather:weather_handler")
    .register("search", "mypackage.search:search_handler")
)
```

格式：`"module.path:function_name"` — 框架通过 `importlib` 自动加载。

### 3. 注入完整 ToolModuleImpl

```python
from pompeii_agent import ToolModuleImpl, ToolNetworkPolicyConfig, LocalSimulatorBackend

tools = ToolModuleImpl(
    local_handlers={"my_tool": my_handler},
    device_routes={},
    mcp=None,
    network_policy=ToolNetworkPolicyConfig(enabled=False),
    device_backend=LocalSimulatorBackend(),
)

tb = ToolBuilder().tools_module(tools)
```

---

## 内置工具

框架默认注册三个内置工具（`ToolBuilder` 默认已包含）：

### echo

```python
# 工具名: echo
# 参数: text (str)

resp = invoke_kernel(kernel, user_id="u1", channel="c1",
    text="用 echo 工具返回 hello world")
```

返回：

```python
{"echo": {"text": "hello world"}, "session_id": "u1"}
```

### calc（安全数学计算）

```python
# 工具名: calc
# 参数: expression (str)

invoke_kernel(kernel, user_id="u1", channel="c1",
    text="用 calc 计算 (2**10 + 100) / 6")
```

支持运算符：`+ - * / // % **`（AST 解析，完全安全，无 `eval`）

### now（当前时间）

```python
# 工具名: now
# 参数: —

invoke_kernel(kernel, user_id="u1", channel="c1",
    text="现在是什么时间？")
```

返回：

```python
{"kind": "now", "iso_utc": "2026-03-29T...", "timestamp": 1743254400.0}
```

---

## HTTP GET 工具（`make_http_get_handler`）

`make_http_get_handler` 返回一个绑定了网络策略的 HTTP GET 工具：

```python
from pompeii_agent import (
    make_http_get_handler,
    ToolNetworkPolicyConfig,
    ToolBuilder,
)

policy = ToolNetworkPolicyConfig(
    enabled=True,
    http_url_guard_enabled=True,
    http_url_allowed_hosts=("api.example.com", "weather.service"),
    http_blocked_content_type_prefixes=("application/octet-stream",),
)

http_get_handler = make_http_get_handler(policy)

tb = (
    ToolBuilder()
    .register_handler("http_get", http_get_handler)
)
```

参数（通过 `ToolCall.arguments` 传入）：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `url` | str | 必填 | 目标 URL |
| `timeout_seconds` | float | 10.0 | 超时（1-60 秒） |
| `max_response_bytes` | int | 256000 | 最大响应字节数（1024-2_000_000） |

---

## 设备后端（Device Backend）

设备后端用于同步执行设备请求（如拍照、录音、文件系统等）：

### LocalSimulatorBackend（内置）

```python
from pompeii_agent import LocalSimulatorBackend

tools = ToolModuleImpl(
    local_handlers={},
    device_backend=LocalSimulatorBackend(),
)
```

支持的模拟设备：

| 设备 | 命令 | 说明 |
|------|------|------|
| `camera` | `take_photo` | 返回模拟图片路径 |
| `microphone` | `record` | 返回模拟音频路径 |
| `speaker` | `play` | TTS 播放模拟 |
| `display` | `show` | 显示内容模拟 |
| `filesystem` | `read` / `list` | 文件读取模拟 |

### CompositeDeviceBackend（组合多个后端）

```python
from pompeii_agent import CompositeDeviceBackend

backend = CompositeDeviceBackend(backends=[
    MyRealDeviceBackend(),
    LocalSimulatorBackend(),
])
```

### NoopDeviceBackend（禁用设备）

```python
from pompeii_agent import NoopDeviceBackend
# 跳过所有设备请求，返回 error
```

### 设备路由配置

将工具名映射到设备：

```python
from pompeii_agent import ToolBuilder, DeviceRoute, LocalSimulatorBackend

tb = (
    ToolBuilder()
    .device_route(
        tool="take_photo",
        device="camera",
        command="take_photo",
        quality="high",
    )
    .device_backend = LocalSimulatorBackend()
)
```

---

## 网络策略（ToolNetworkPolicyConfig）

```python
from pompeii_agent import ToolNetworkPolicyConfig

policy = ToolNetworkPolicyConfig(
    enabled=True,                          # 开启工具网络限制
    deny_tool_names=("shell", "exec"),    # 直接拒绝的工具名
    http_url_guard_enabled=True,            # HTTP GET URL 守卫
    http_url_allowed_hosts=(),             # 允许的 hosts（空=全部拒绝）
    http_blocked_content_type_prefixes=(), # 阻止的内容类型前缀
    mcp_allowlist_enforced=True,          # MCP 工具白名单强制
    mcp_tool_allowlist=(),                 # 允许的 MCP 工具
)
```

---

## 工具发现（Entrypoint Discovery）

框架支持通过 `entry_points` 自动发现工具：

```python
# 在 pyproject.toml 中注册
[project.entry-points."pompeii_agent.tools"]
my_tool = "mypackage.tools:my_handler"
another_tool = "mypackage.tools:another_handler"
```

```python
tb = (
    ToolBuilder()
    # 默认从 group="pompeii_agent.tools" 发现
    .register_handler("my_tool", discovered_handler)
)
```

禁用自动发现：

```python
tb = ToolBuilder(enable_entrypoints=False)
```

---

## ToolHandler 签名详解

```python
from pompeii_agent import Session, ToolCall, ToolResult

def my_handler(session: Session, tool_call: ToolCall) -> ToolResult:
    # session.session_id   → 当前会话 ID
    # session.user_id      → 用户 ID
    # session.channel      → 渠道
    #
    # tool_call.name       → 工具名
    # tool_call.arguments  → dict 参数
    # tool_call.call_id    → 调用 ID
    #
    return ToolResult(
        name=tool_call.name,
        output={...},      # 任意可序列化数据
        source="my_handler",  # 可选
    )
```
