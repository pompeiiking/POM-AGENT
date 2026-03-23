---
name: interface-change
description: 公共接口变更流程：影响评估、兼容性策略、调用方同步更新。修改公共接口、导出类型或共享函数签名时加载。
metadata:
  priority: L1
  category: workflow
  depends: layering, module-boundary
---

# 公共接口变更流程

## 规则

- **修改公共接口前必须评估影响范围** — 搜索所有调用方，确认影响面
- **接口变更必须同步更新所有调用方** — 不允许只改接口不改调用方，留下编译错误
- **优先向后兼容** — 新增参数使用可选参数或默认值，不破坏已有调用

## 什么是"公共接口"

- 从 `index` 文件导出的函数、类、类型
- 事件名和事件载荷结构
- 配置项的 key 和 value 格式
- API路由和请求/响应格式
- 共享的常量和枚举

## 变更流程

```
Step 1: 评估影响
  → 全项目搜索当前接口的所有使用位置
  → 列出所有需要同步修改的文件

Step 2: 选择兼容性策略
  A) 向后兼容（推荐）: 新增可选参数/方法，旧接口继续可用
  B) 迁移（必要时）: 旧接口标记为@deprecated，提供迁移说明，设定移除日期
  C) 破坏性变更（尽量避免）: 一次性修改接口+所有调用方

Step 3: 执行变更
  → 修改接口定义
  → 同步修改所有调用方
  → 更新相关类型定义
  → 更新相关测试

Step 4: 记录
  → CHANGELOG中标注接口变更，列出受影响的模块
  → 如果是破坏性变更，在提交信息中标注 BREAKING CHANGE
```

## 示例

✅ 正确（向后兼容）：
```typescript
// 之前
function createModule(id: string, config: ModuleConfig): Module

// 之后 — 新增可选参数，旧调用不受影响
function createModule(id: string, config: ModuleConfig, options?: ModuleOptions): Module
```

✅ 正确（迁移过渡）：
```typescript
/** @deprecated 使用 createModuleV2 替代，将在 v3.0 移除 */
function createModule(id: string, config: ModuleConfig): Module {
  return createModuleV2(id, { ...config, version: 1 });
}
```

❌ 错误：
```typescript
// 只改了接口，没改调用方 → 其他文件编译失败
function createModule(id: string, config: ModuleConfig, options: ModuleOptions): Module
// 50个调用方全部报错，因为options不是可选的
```

## 提交前检查清单

- [ ] 已搜索并列出所有调用方
- [ ] 所有调用方已同步更新
- [ ] 项目可编译通过（无类型错误）
- [ ] 接口变更已记录在CHANGELOG中
- [ ] 如果是破坏性变更，提交信息包含 BREAKING CHANGE
