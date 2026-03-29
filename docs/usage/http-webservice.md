# HTTP / WebSocket 服务

## create_http_service — 一行创建服务

```python
from pompeii_agent import create_http_service, AgentBuilder
import uvicorn

kernel = AgentBuilder().session(model="stub", skills=["echo"]).build()
service = create_http_service(kernel=kernel)

uvicorn.run(service.app, host="0.0.0.0", port=8000)
```

返回的 `service` 包含：

```python
service.app      # FastAPI app
service.kernel  # AgentCoreImpl
service.port    # GenericAgentPort（用于 WS）
```

---

## HTTP 接口

### POST /chat — 发送消息

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "channel": "web",
    "text": "你好，上海天气怎么样？"
  }'
```

响应：

```json
{
  "events": [
    {"kind": "status", "status": "..."},
    {"kind": "reply", "text": "上海的天气是..."}
  ]
}
```

请求体：

```python
{
    "user_id": "alice",       # str，必填
    "channel": "web",          # str，必填
    "text": "...",            # str，必填
    "stream": false,           # bool，可选
    "intent": {...}           # 可选，手动传入 UserIntent
}
```

### GET /health — 健康检查

```bash
curl http://localhost:8000/health
```

响应：`{"status": "ok"}`

### GET /sessions — 查询会话列表

```bash
curl "http://localhost:8000/sessions?user_id=alice"
```

---

## WebSocket /ws — 实时交互

```python
import asyncio
import websockets
import json

async def chat():
    uri = "ws://localhost:8000/ws?user_id=alice&channel=web"
    async with websockets.connect(uri) as ws:
        # 发送消息
        await ws.send(json.dumps({
            "text": "你好",
            "stream": True,
        }))
        # 接收事件流
        async for msg in ws:
            event = json.loads(msg)
            print(event)
            if event["kind"] == "reply":
                print(event["text"])

asyncio.run(chat())
```

---

## 自定义 HTTP Handler

完全控制 FastAPI 路由：

```python
from fastapi import FastAPI
from pompeii_agent import AgentBuilder, GenericAgentPort, HttpMode
from port.input_events import UserMessageInput
from port.http_emitter import HttpEmitter
from port.request_factory import http_request_factory

app = FastAPI()
kernel = AgentBuilder().session(model="stub", skills=["echo"]).build()

@app.post("/api/agent")
async def agent_chat(req: dict):
    port = GenericAgentPort(
        mode=HttpMode(),
        core=kernel,
        request_factory=http_request_factory(user_id=req.get("user_id", "")),
        emitter=HttpEmitter(),
    )
    emitter = HttpEmitter()
    port.handle(
        UserMessageInput(kind="user_message", text=req["text"]),
        user_id=req.get("user_id"),
        channel=req.get("channel", "api"),
        emitter=emitter,
    )
    return {"events": emitter.dump()}
```

---

## 共享会话的 HTTP + CLI

```python
from pompeii_agent import (
    create_http_service,
    create_interactive_port,
    CliMode, CliEmitter, cli_request_factory,
    AgentBuilder,
)
import threading, uvicorn

kernel = AgentBuilder().session(model="stub", skills=["echo"]).build()

# HTTP 服务（主线程）
service = create_http_service(kernel=kernel)
t = threading.Thread(target=lambda: uvicorn.run(service.app, port=8000), daemon=True)
t.start()

# CLI 共享同一内核
cli_port = create_interactive_port(
    mode=CliMode(),
    request_factory=cli_request_factory(user_id="cli-user"),
    emitter=CliEmitter(),
    kernel=kernel,   # 与 HTTP 共享内核，会话互通
)

# CLI 事件循环
from port.input_events import UserMessageInput, SystemCommandInput
import sys
while True:
    line = input("you> ")
    if not line or line.strip().lower() in {"exit", "quit"}:
        break
    cli_port.handle(SystemCommandInput(kind="system_command", text=line))
```

---

## 注入 Mock Port（测试）

使用 `port_cell` 注入测试 Port：

```python
from pompeii_agent import create_http_service, AgentBuilder
from port.agent_port import GenericAgentPort
from port.http_emitter import HttpEmitter
from port.request_factory import http_request_factory
from port.agent_port import HttpMode

kernel = AgentBuilder().session(model="stub", skills=["echo"]).build()
port_cell = []

service = create_http_service(kernel=kernel, port_cell=port_cell)

# 在测试中替换 port
mock_port = GenericAgentPort(
    mode=HttpMode(),
    core=kernel,
    request_factory=http_request_factory(user_id="test"),
    emitter=HttpEmitter(),
)
port_cell.append(mock_port)
```

---

## 挂载到已有 FastAPI 应用

```python
from fastapi import FastAPI
from pompeii_agent import create_http_service, AgentBuilder

app = FastAPI()
kernel = AgentBuilder().session(model="stub", skills=["echo"]).build()
service = create_http_service(kernel=kernel)

# 挂载到 /agent 前缀
app.include_router(service.app, prefix="/agent")

# 已有路由
@app.get("/status")
async def status():
    return {"app": "running"}
```

---

## CORS 配置

`create_http_service` 返回的 FastAPI app 使用默认 CORS 中间件。如需自定义：

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pompeii_agent import create_http_service, AgentBuilder

kernel = AgentBuilder().session(model="stub", skills=["echo"]).build()
service = create_http_service(kernel=kernel)

service.app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://myapp.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import uvicorn
uvicorn.run(service.app, port=8000)
```
