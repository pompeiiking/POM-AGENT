## Pompeii-Agent 当前状态（快照）

### 概览
- **目标**：以 Python 为起点，构建可长期演进的微内核 Agent 基础设施。
- **当前架构骨架**：`app`（runtime/composition）+ `port`（emit 事件边界）+ `core`（loop 编排）+ `modules`（assembly/model/tools）+ `platform`（配置/资源）

### 已完成（里程碑）
- 端口事件体系（`PortEvent`）与 `emit` 边界
- `tool_call` 最小闭环（model → tools → assembly → loop）
- KernelConfig（长期保存）与治理参数接入（max_loops/max_tool_calls）
- 工具安全门与确认流（确认状态在 port 层维护）

### 活跃 STUB 清单（必须持续清理）
> 规则：所有占位实现必须包含 `// STUB(YYYY-MM-DD): 原因 — 替换计划`
- 待扫描并统一补齐（下一次系统性收敛任务执行）

### 已知风险/债务（优先级从高到低）
- **分层方向**：需要审查 `platform/*` 是否存在反向依赖 `core/*`
- **STUB 规范**：占位实现目前未统一按 STUB 格式标注
- **确认输入建模**：确认目前复用 raw 输入通道，后续需升级为 `system_command` 类型输入事件

