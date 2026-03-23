---
name: git-commit
description: Git提交信息格式、scope定义、提交频率和原子性要求。提交代码时加载。
metadata:
  priority: L2
  category: workflow
---

# Git提交规范

## 提交信息格式

```
<type>(<scope>): <简短描述>

[可选: 详细说明]

[可选: BREAKING CHANGE: 不兼容变更说明]
```

### type 类型

| type | 含义 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(user): 添加用户注册表单验证` |
| `fix` | bug修复 | `fix(auth): 修复登录状态未持久化` |
| `refactor` | 重构（不改变功能） | `refactor(core): 提取事件总线为独立模块` |
| `docs` | 文档 | `docs: 更新API文档` |
| `test` | 测试 | `test(user): 添加注册流程单元测试` |
| `chore` | 构建/工具/配置 | `chore: 升级TypeScript到5.4` |
| `style` | 代码格式（不影响逻辑） | `style: 统一缩进为2空格` |
| `perf` | 性能优化 | `perf(render): 减少不必要的重渲染` |

### scope 范围

[TODO:填充项目的scope定义，示例:]
```
core     — 核心框架/内核
ui       — UI组件库
auth     — 认证模块
user     — 用户功能
config   — 配置相关
build    — 构建工具链
```

## 规则

- **一个提交做一件事** — 原子性，回滚时不会牵连无关代码
- **提交信息用中文或英文（统一一种）** — 不混用
- **不提交半成品** — 每个提交在 `git checkout` 后必须能编译通过
- **不提交生成文件和临时文件** — 确保 `.gitignore` 正确配置

## 示例

✅ 正确：
```
feat(user): 实现用户注册表单验证

- 新增 RegisterForm 组件
- 新增 validators.ts 校验规则
- 支持邮箱格式、密码强度、确认密码校验
```

❌ 错误：
```
update files               ← 没有type，没有scope，描述无意义
fix: 修了很多东西          ← 非原子提交
feat: WIP                  ← 半成品
```

## 提交前检查清单

- [ ] 提交信息符合 `<type>(<scope>): <描述>` 格式
- [ ] 本次提交只包含一个逻辑单元的变更
- [ ] 代码能编译通过，不是半成品
- [ ] CHANGELOG.md 已同步更新
- [ ] 没有提交临时文件、日志文件或生成文件
