# Pompeii-Agent 设计文档索引

> 返回文档总览：[`../README.md`](../README.md)

- **变更日志（主）**：`CHANGELOG.md`（与 `src/app/version.py` 同步）
- **继续开发**：[`../guides/继续开发手册.md`](../guides/继续开发手册.md) — 插拔设计矩阵、配置地图、entry points、已知缺口与优先级
- **模块间契约（仓库根）**：[`../../contracts/README.md`](../../contracts/README.md) — Port/Core 边界摘要；权威类型以 `src/` 为准

- **架构设计**：
  - `架构设计ver0.5.md`：整体微内核架构（**ver0.6 当前有效版本**）。合并了原《会话与双库长期记忆架构设计》、《长期记忆定义》、《开发状态与系统接口》三份卫星文档。含：L0–L8 分层、表格化运转流程、共享服务、双库记忆子系统（§9）、系统接口清单（§12）、可替换模块（§12.6）
  - `架构设计ver0.4.md`：原始五关卡与模块分工全文（ver0.6 继承其框架；细节冲突以 ver0.6 + 代码为准）
  - `archive/`：历史草案及已合并的卫星文档

- **项目规范模板（ai-rules-template）**：
  - `RULES.md`：项目规则总览（代码风格 / 分层约束 / STUB 规范等）
  - `STATUS.md`：设计模板的状态示例
  - `CHANGELOG.md`：设计模板的变更示例
  - `contracts/`：接口契约与共享类型约定
  - `skills/principles/`：分层/抽象/零硬编码/异常处理等原则
  - `skills/workflow/`：协作流程、提交规范、测试策略等
  - `skills/project/`：代码风格与文件结构建议

