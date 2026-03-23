# AI开发规范通用模板 — Skill系统

> 一套模块化的AI辅助开发规范，确保多人/多AI协作时代码质量一致、接口对接顺畅、项目风格统一。

## 这是什么

一个**即拿即用的规范模板**，复制到任何新项目后，AI首次阅读会自动引导你完成项目专属转化。

解决的核心问题：
- 团队中多人使用不同AI（Cursor/Windsurf/Copilot等），代码风格和接口设计不统一
- AI助手在不同会话中"失忆"，重复犯同样的错误
- 没有统一的变更记录，不知道谁改了什么

## 快速开始

```
1. 复制整个 ai-rules-template/ 目录到你的项目根目录
2. 重命名为你喜欢的名称（如 rules/ 或直接放根目录）
3. 让AI阅读 RULES.md
4. AI会检测到 TEMPLATE_STATUS: UNINITIALIZED，自动执行转化流程
5. 回答AI的提问（项目名、技术栈、架构等）
6. 转化完成，开始开发
```

## 目录结构

```
ai-rules-template/
├── README.md               ← 本文件（使用说明，导出后可删除）
├── RULES.md                ← 主文件：全局铁律 + Skill索引 + AI接入协议
└── skills/                 ← 模块化规则
    ├── _bootstrap.md       ← 自举：首次使用时引导项目转化（转化后自动删除）
    ├── principles/         ← 11个设计原则（零硬编码、类型安全、分层、命名等）
    ├── workflow/            ← 10个工作流程（bug修复、协作、提交、交接、契约等）
    └── project/            ← 2个项目专属骨架（目录结构、代码风格，含TODO占位）
```

## 工作原理

### Progressive Disclosure（渐进式披露）

AI不需要一次性阅读所有规则（那会浪费token且降低注意力）：

```
Level 1: 主文件索引（~300 tokens）— 启动时加载，包含铁律和skill一句话描述
Level 2: 匹配的skill（每个<5000 tokens）— 按当前任务按需加载
Level 3: 附属资源 — 执行中按需加载（契约文档、模板等）
```

### 自举转化

模板中的 `[TODO:填充]` 占位符标记了需要项目专属配置的位置。AI首次阅读时：
1. 检测到 `TEMPLATE_STATUS: UNINITIALIZED`
2. 加载 `_bootstrap.md`，向开发者提问（技术栈、架构、命名偏好等）
3. 根据回答填充所有TODO占位
4. 转化完成后删除 `_bootstrap.md`

### 接口契约

团队多人用不同AI开发不同模块时，人类架构师在 `contracts/` 目录中定义模块间接口（类型、签名、事件、约束），所有AI严格遵守，不得擅自修改。

## 适用场景

- ✅ **多人团队 + 多AI工具**：统一不同AI的行为和输出标准
- ✅ **个人项目 + 单AI**：防止AI在不同会话中风格漂移
- ✅ **全新项目**：从零开始建立规范
- ✅ **已有项目**：导入后做一次规范审查
- ✅ **任何语言/框架**：skill中的语言专属部分通过TODO占位适配

## 定制指南

### 增删skill

- 新增：在 `skills/[category]/` 下创建 `.md` 文件，遵循现有skill的frontmatter格式，在 `RULES.md` 索引中添加条目
- 删除：删除文件 + 从索引中移除 + 检查其他skill的 `depends` 是否引用了它

### 修改规则

- 全局铁律：直接编辑 `RULES.md` 第一节
- 具体规则：编辑对应skill文件
- 优先级：同步更新 `RULES.md` 第二节的L1/L2/L3列表和skill的frontmatter

### Skill格式要求

```markdown
---
name: kebab-case-name        # 必须与文件名一致
description: 做什么。何时用。  # 50-200字符，含关键词
metadata:
  priority: L1/L2/L3
  category: principles/workflow/project
  depends: other-skill-1, other-skill-2  # 可选
---

# 标题

## 规则
[核心规则]

## 示例
✅ 正确 / ❌ 错误

## 提交前检查清单
- [ ] 检查项
```

## 文件清单（25个）

| 类别 | 数量 | 文件 |
|------|------|------|
| 系统 | 2 | RULES.md, _bootstrap.md |
| principles | 11 | zero-hardcoding, abstraction, data-separation, layering, module-boundary, naming, comments, type-safety, stub-management, error-handling, performance |
| workflow | 10 | anti-paranoid, collaboration, changelog, status-management, git-commit, testing, session-handoff, interface-change, security, interface-contract |
| project | 2 | file-structure, code-style |
| 说明 | 1 | README.md（本文件，导出后可选删除） |
