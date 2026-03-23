---
name: bootstrap
description: 通用规范模板的项目转化流程。当RULES.md中TEMPLATE_STATUS为UNINITIALIZED时执行。
metadata:
  priority: L1
  category: system
---

# 模板转化流程

> 本文件引导AI将通用模板转化为项目专属规范。转化完成后删除本文件。

## 第一步：需求采集

**在修改任何文件之前，必须先向开发者了解以下信息。不要猜测，每一项都必须确认。**

### 必问（基础信息）

- **Q1: 项目名称** → 用于替换所有 `[项目名]` 占位符
- **Q2: 编程语言和框架** → 用于填充类型安全规则、代码风格
- **Q3: 核心功能（一两句话）** → 判断哪些原则需要加强或简化
- **Q4: 架构分层** → 填充 layering skill 的分层结构（如果未确定，一起讨论）
- **Q5: 目录结构** → 填充 file-structure skill（新项目则一起规划）

### 按需问（根据Q2和Q3判断是否需要）

- **Q6: 数据与代码如何分离？数据格式？** → 填充 data-separation skill
- **Q7: 性能要求或限制？** → 填充 performance skill
- **Q8: 单人还是团队？多个AI助手？** → 调整 session-handoff 详细程度
- **Q9: 已确定的第三方依赖？** → 填充 collaboration skill 的技术栈列表
- **Q10: 已有的代码规范或偏好？** → 填充 naming 和 code-style skill
- **Q11: 是否有多人/多AI分模块开发？模块间接口是否已定义？** → 决定是否启用 contracts/ 目录，填充 interface-contract skill

## 第二步：修改文件

**获得回答后，按以下顺序修改：**

1. **RULES.md 主文件**
   - `TEMPLATE_STATUS: UNINITIALIZED` → `TEMPLATE_STATUS: INITIALIZED:[项目名]`
   - 删除标题中"多AI协作开发通用规范 — Skill系统" → 改为 `[项目名] 项目规范`
   - 删除顶部模板说明段落
   - 填充文档体系中的 `[TODO:项目专属文档]`

2. **skills/ 中有 [TODO:填充] 的文件**
   - 按 Q1-Q10 的回答逐个填充
   - 不适用的语言段落删除（如项目不用TypeScript则删除TS段落）
   - 不适用的整个skill文件保留但简化（不要删除skill文件）

3. **创建 STATUS.md**（参照 status-management skill 的模板）

4. **创建 CHANGELOG.md**，写入第一条记录：
   ```
   ### [日期] — [操作者标识]
   **任务**: 初始化项目规范，从通用模板转化为 [项目名] 专属规范
   **变更文件**: RULES.md, skills/下多个文件, STATUS.md, CHANGELOG.md
   **影响范围**: 全局
   ```

## 第三步：验证

```
修改完成后，执行以下检查：

□ 全文搜索 [TODO:填充] — 必须0个结果
□ 全文搜索 [项目名]   — 必须0个结果
□ TEMPLATE_STATUS 已改为 INITIALIZED
□ STATUS.md 已创建
□ CHANGELOG.md 已创建且有第一条记录
□ 目录结构与开发者确认的一致
□ 技术栈与开发者确认的一致
```

验证通过后，向开发者报告转化结果，并**删除本文件（_bootstrap.md）**。

## 第四步：后续建议

**全新项目（空目录）：**
1. 是否需要初始化项目结构？（创建目录、package.json等）
2. 是否需要创建架构设计文档？
3. 准备好开始第一个功能模块

**已有项目（已有代码）：**
1. 需要阅读现有代码了解项目现状
2. 现有代码是否需要做一次规范审查？
3. 是否有具体的开发任务要开始？
