# contracts/

**CONTRACT_STATUS**: INITIALIZED — 索引与边界说明（权威类型与实现仍以 `src/` 为准）。

本目录存放**模块间接口契约**的人类可读摘要，便于对接方与多会话协作时对齐，**不替代**源码中的 Protocol / dataclass。

| 文档 | 内容 |
|------|------|
| [kernel_port_boundary.md](./kernel_port_boundary.md) | Port → Core 边界：`AgentRequest` / `AgentResponse` 字段与终止原因 |

**规范**：修改契约须人类授权并在 `docs/design/CHANGELOG.md` 溯源（见 `docs/design/ai-rules-template/RULES.md`）。
