# 契约摘要：Port → Core 边界

**权威实现**：`src/core/agent_types.py`、`src/port/events.py`、`src/port/agent_port.py`。

## AgentRequest

| 字段 | 类型（概念） | 说明 |
|------|----------------|------|
| `request_id` | string | 单次请求关联 ID；日志与排错对齐 |
| `user_id` | string | 用户分区 |
| `channel` | string | 通道分区（与 Session 一致） |
| `payload` | any | 用户载荷（多模态结构等） |
| `intent` | optional | `UserIntent`；系统指令短路时非空 |
| `stream` | bool | 是否允许模型流式增量 |

工厂：`port/request_factory.py`（CLI / 会话 / HTTP 等）。

## AgentResponse

| 字段 | 说明 |
|------|------|
| `request_id` | 与请求对齐 |
| `session` | 当前会话快照 |
| `reply_text` / `error` | 用户可见回复或错误文案 |
| `reason` | `ResponseReason` 枚举（终止原因） |
| `pending_tool_call` / `pending_device_request` | 确认流 / 设备流 |
| `delegate_target` / `delegate_payload` | `reason=delegate` 时 |

## ResponseReason（节选）

完整枚举见 `src/core/agent_types.py`。常见值：`ok`、`max_loops`、`confirmation_required`、`device_request`、`resource_access_denied`、`delegate` 等。

## Port 出向事件

事件类型与载荷见 `src/port/events.py`（`ReplyEvent`、`ConfirmationEvent`、`ErrorEvent`、`DelegateEvent` 等）。

当前对接常用事件：

- `reply`：最终文本回复
- `error`：错误事件（含 `reason`）
- `status`：运行状态提示
- `policy_notice`：策略提示（如 `resource_approval_required`）
- `confirmation`：工具确认事件
- `device_request`：设备请求事件
- `delegate`：子代理委派事件
