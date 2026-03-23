---
name: file-structure
description: 项目目录结构、新增文件放置规则、禁止创建的文件、文档封闭清单。新建文件或不确定文件该放哪里时加载。
metadata:
  priority: L2
  category: project
  depends: layering, naming
---

# 项目目录结构

## 项目根目录

[TODO:填充你的项目目录结构，示例:]
```
project-root/
├── src/                    # 源码根目录
│   ├── core/               # 核心层：框架内核、状态管理、事件系统
│   ├── features/           # 业务层：按功能模块组织
│   │   └── [feature]/      # 每个功能一个目录
│   │       ├── index.ts    # 公共API出口
│   │       ├── components/ # 该功能的UI组件
│   │       ├── hooks/      # 该功能的React hooks
│   │       ├── types.ts    # 该功能的类型定义
│   │       └── utils/      # 该功能的工具函数
│   ├── shared/             # 共享层：跨功能复用的组件/工具
│   └── types/              # 全局类型定义
├── data/                   # 数据目录（与源码分离）
├── tests/                  # 测试（如果选择统一测试目录方案）
├── docs/                   # 文档（guides/ 运维测试；design/ 设计与 CHANGELOG）
├── config/                 # 环境变量模板（env.ps1.example、.env.example）
├── RULES.md                # 项目规范（本系统）
├── STATUS.md               # 项目状态快照
├── CHANGELOG.md            # 变更日志
└── README.md               # 项目简介
```

## 新增文件放置规则

| 文件类型 | 放置位置 | 示例 |
|----------|---------|------|
| 功能组件 | `src/features/[功能名]/components/` | `UserCard.tsx` |
| 共享组件 | `src/shared/components/` | `Button.tsx` |
| 全局类型 | `src/types/` | `global.d.ts` |
| 功能类型 | `src/features/[功能名]/types.ts` | — |
| 工具函数（功能专属） | `src/features/[功能名]/utils/` | `formatDate.ts` |
| 工具函数（全局通用） | `src/shared/utils/` | `debounce.ts` |
| 数据文件 | `data/[分类]/` | `data/content/posts.json` |
| 测试文件 | [TODO:根据testing skill选择的方案] | — |
| 配置文件 | 项目根目录 | `tsconfig.json` |

## 禁止创建的文件

- **源码目录下的数据文件**（JSON/YAML/CSV等，tsconfig等构建配置除外）
- **未在RULES.md文档体系中登记的文档文件**
- **临时文件/调试文件**（如 `test.ts`, `temp.js`, `debug.log`）
- **重复的工具函数文件**（先搜索shared/utils是否已有类似功能）

## 新建文件决策流

```
Q1: "这个文件属于哪个功能模块？"
  → 明确属于某功能 → 放 features/[功能名]/ 下
  → 多个功能都用 → 放 shared/ 下
  → 属于框架核心 → 放 core/ 下

Q2: "这个目录已经有index文件吗？"
  → 没有 → 创建index文件，导出公共API
  → 有 → 在index中添加新文件的导出

Q3: "类似功能的文件是否已存在？"
  → 是 → 扩展已有文件而非新建
  → 否 → 创建新文件
```

## 提交前检查清单

- [ ] 新文件放在了正确的目录下（按上方放置规则）
- [ ] 新文件所在目录的 index 文件已更新导出
- [ ] 没有在源码目录下创建数据文件
- [ ] 没有创建未登记的文档文件
- [ ] 检查过shared/utils中是否已有类似功能的工具函数
