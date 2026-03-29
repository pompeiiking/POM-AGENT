# 端口层与交互模式

## 概念

Port 层（`GenericAgentPort`）负责将外部交互渠道（CLI / HTTP / WebSocket）与 Agent 内核解耦：

```
CLI / HTTP / WebSocket
    │
    ▼
GenericAgentPort
  │
  ├── 输入转换（raw → AgentRequest）
  │     └── intent_parser.parse_user_intent()
  │
  ├── 内核调用（AgentCore.handle）
  │
  └── 事件发射（AgentResponse → PortEvent）
        │
        ├── ReplyEvent         → 文本回复
        ├── ErrorEvent         → 错误信息
        ├── StatusEvent        → 状态通知
        ├── StreamDeltaEvent   → 流式片段
        ├── ConfirmationEvent  → 工具确认
        ├── DeviceRequestEvent→ 设备请求
        └── DelegateEvent      → 多 Agent 协作
```

---

## 交互模式（InteractionMode）

| 模式 | 说明 |
|------|------|
| `CliMode` | 从 stdin 读取，按 `exit`/`quit` 退出 |
| `HttpMode` | 类型标识，HTTP 由框架驱动，不走 stdin |
| `WsMode` | WebSocket 标识，由回调驱动 |

### CliMode

```python
from pompeii_agent import CliMode

mode = CliMode()
# mode.receive()  → str | None（从 stdin 读取）
# mode.should_exit("exit") → True
```

---

## Emitter（事件发射器）

Emitter 将 `PortEvent` 渲染到具体渠道：

| Emitter | 说明 |
|---------|------|
| `CliEmitter` | 渲染到 stdout |
| `HttpEmitter` | 收集到列表，供 HTTP handler 序列化 |
| 自定义 | 实现 `PortEmitter` Protocol |

### HttpEmitter

```python
from pompeii_agent import HttpEmitter

emitter = HttpEmitter()
# 在 Port.handle 期间收集所有事件
events = emitter.events  # list[PortEvent]
# 序列化
dumped = emitter.dump()  # list[dict]
```

### 自定义 Emitter

```python
from pompeii_agent import PortEmitter, PortEvent

class MyEmitter(PortEmitter):
    def emit(self, event: PortEvent) -> None:
        match event.kind:
            case "reply":
                print(f"[REPLY] {event.text}")
            case "error":
                print(f"[ERROR] {event.message}")
```

---

## 创建交互 Port

### CLI Port

```python
from pompeii_agent import (
    create_interactive_port,
    CliMode,
    CliEmitter,
    cli_request_factory,
)

port = create_interactive_port(
    mode=CliMode(),
    request_factory=cli_request_factory(user_id="cli-user"),
    emitter=CliEmitter(),
    kernel=kernel,
)
```

### HTTP Port（使用 create_http_service）

```python
from pompeii_agent import create_http_service, HttpEmitter

service = create_http_service(kernel=kernel)
# service.app → FastAPI app
# service.port_cell → list，可注入 mock port
```

### 共享内核的 HTTP Port

```python
# 已有 kernel 在 HTTP 中使用，同时创建 CLI port 共享会话
cli_port = create_interactive_port(
    mode=CliMode(),
    request_factory=cli_request_factory(),
    emitter=CliEmitter(),
    kernel=kernel,  # 与 HTTP 共享同一内核
)
```

---

## 事件体系（PortEvent）

所有事件均为 frozen dataclass，可安全序列化：

```python
from pompeii_agent import (
    PortEvent,
    ReplyEvent,
    ErrorEvent,
    StatusEvent,
    StreamDeltaEvent,
    ConfirmationEvent,
    DeviceRequestEvent,
    DelegateEvent,
    PolicyNoticeEvent,
)
```

### ReplyEvent — 文本回复

```python
ReplyEvent(kind="reply", text="Hello!")
```

### ErrorEvent — 错误

```python
ErrorEvent(
    kind="error",
    message="tool execution failed",
    reason="max_tool_calls_exceeded",
)
```

### StatusEvent — 状态

```python
StatusEvent(kind="status", status="confirmation: approved")
```

### StreamDeltaEvent — 流式片段

```python
StreamDeltaEvent(kind="stream_delta", fragment="Hello ")
```

### ConfirmationEvent — 工具确认

```python
ConfirmationEvent(
    kind="confirmation",
    prompt="确定执行此操作吗？",
    confirmation_id="abc123",
    tool_call=tool_call,   # ToolCall 对象
)
```

### DeviceRequestEvent — 设备请求

```python
DeviceRequestEvent(
    kind="device_request",
    device_request_id="dev-001",
    request=DeviceRequest(...),
)
```

### DelegateEvent — 多 Agent 协作

```python
DelegateEvent(kind="delegate", target="sub-agent", payload="...")
```

### PolicyNoticeEvent — 策略通知

```python
PolicyNoticeEvent(kind="policy_notice", policy="resource_access", detail="...")
```

---

## 请求工厂（RequestFactory）

`RequestFactory = Callable[[UserMessageInput], AgentRequest]`

```python
from pompeii_agent import (
    cli_request_factory,    # CLI: 固定 request_id="cli-1"
    http_request_factory,  # HTTP: 每请求生成 UUID
    ws_request_factory,    # WebSocket
    session_request_factory,  # 指定 user_id + channel
)
```

自定义请求工厂：

```python
from pompeii_agent import AgentRequest
from my_intent_parser import parse_intent

def my_factory(event: UserMessageInput) -> AgentRequest:
    intent = parse_intent(event.text)
    return AgentRequest(
        request_id=str(uuid.uuid4()),
        user_id="my-user",
        channel="my-channel",
        payload=event.text,
        intent=intent,
    )
```

---

## 意图解析（parse_user_intent）

框架内置意图解析器，支持以下格式：

| 原始输入 | 解析结果 |
|----------|---------|
| `你好` | `Chat(text="你好")` |
| `/help` | `SystemHelp()` |
| `/summary` | `SystemSummary()` |
| `/archive` | `SystemArchive()` |
| `/remember 张三的信息` | `SystemRemember(text="张三的信息")` |
| `/forget 张三` | `SystemForget(phrase="张三")` |
| `/preference list` | `SystemPreference(action="list")` |
| `/preference set name=alice` | `SystemPreference(action="set", key="name", value="alice")` |
| `/fact add 张三是一名学生` | `SystemFact(action="add", statement="张三是一名学生")` |

### 自定义意图解析

```python
from my_intent_parser import MyIntentParser

class MyParser(MyIntentParser):
    def parse(self, text: str) -> UserIntent:
        if text.startswith("!"):
            return SystemCommand(...)
        return Chat(text=text)
```

---

## 输入类型（PortInput）

| 类型 | 说明 |
|------|------|
| `UserMessageInput` | 用户消息（`text` + `openai_user_content`） |
| `SystemCommandInput` | 系统命令 |
| `DeviceResultInput` | 设备执行结果（回传） |

---

## 完整示例：自定义 HTTP Handler

```python
from pompeii_agent import (
    GenericAgentPort,
    HttpMode,
    HttpEmitter,
    http_request_factory,
)
from fastapi import FastAPI, Request

app = FastAPI()
kernel = AgentBuilder().session(model="stub", skills=["echo"]).build()
emitter_factory = lambda: HttpEmitter()

port = GenericAgentPort(
    mode=HttpMode(),
    core=kernel,
    request_factory=http_request_factory(user_id="http-user"),
    emitter=emitter_factory(),   # 每次创建新 emitter
)

@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    emitter = HttpEmitter()
    port.handle(
        UserMessageInput(kind="user_message", text=body["text"]),
        user_id=body.get("user_id"),
        channel=body.get("channel"),
        emitter=emitter,
    )
    return {"events": emitter.dump()}
```
