# 使用教程导航

## 目录

### 入门
- [Getting Started（安装与基础概念）](./getting-started.md)
  安装、项目结构、核心概念（Kernel / Port / Module）

### Agent 装配
- [AgentBuilder 完整指南](./agent-builder.md)
  SessionBuilder / KernelBuilder / ToolBuilder / MemoryBuilder / SecurityBuilder / RuntimeBuilder 全解

### 工具系统
- [工具子系统详解](./tool-system.md)
  本地工具注册、内置工具（echo/calc/now/http_get）、网络策略

- [MCP 集成](./mcp-integration.md)
  McpStdioBridge / McpHttpBridge / McpMultiStdioBridge / MCP 工具白名单

### 记忆系统
- [记忆系统](./memory-system.md)
  长期记忆 + 短期记忆、RRF 混合检索、OpenAI 嵌入后端、检索 API

### 交互层
- [端口层与交互模式](./port-layer.md)
  GenericAgentPort / CliMode / HttpMode / WsMode / PortEvent 体系

- [HTTP / WebSocket 服务](./http-webservice.md)
  create_http_service / FastAPI / uvicorn / WebSocket 端点

### 安全与资源
- [安全策略](./security.md)
  输入限流 / Guard 模型 / 工具风险分级 / 资源访问控制

### 高级
- [高级用法](./advanced.md)
  底层 API（advanced）/ 自定义 AssemblyModule / 自定义 ModelModule / 自定义 PortEmitter

---

## 公共 API 速查

```python
# 唯一入口
import pompeii_agent

# 装配
from pompeii_agent import AgentBuilder, create_kernel, invoke_kernel

# 工具
from pompeii_agent import (
    ToolBuilder, ToolModuleImpl, ToolHandler,
    echo_handler, calc_handler, now_handler, make_http_get_handler,
    ToolNetworkPolicyConfig, McpToolBridge,
)

# 模型
from pompeii_agent import ModelRegistryBuilder, ModelProviderBuilder

# 端口
from pompeii_agent import (
    CliMode, HttpMode, WsMode, CliEmitter, HttpEmitter,
    create_interactive_port, create_http_service,
    parse_user_intent, PortEvent,
)

# 类型
from pompeii_agent import (
    AgentCoreImpl, AgentRequest, AgentResponse,
    Session, ToolCall, ToolResult,
    UserIntent, Chat,
)
```

> **注意：** `pompeii_agent` 是对外唯一公共接口，请勿直接 import `core.*`、`modules.*`、`app.*` 等内部路径。
