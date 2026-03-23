---
name: naming
description: 文件、变量、函数、类的命名一致性规范，禁止同义词混用和无意义缩写。新建任何标识符时加载。
metadata:
  priority: L2
  category: principles
---

# 命名一致性

## 规则

- **全项目同一种命名约定**，不混用多种风格
- **同一概念必须使用同一名称** — 不允许一处叫 `user` 另一处叫 `account`
- **禁止无意义缩写** — 用 `eventBus` 不用 `eb`，用 `configuration` 不用 `cfg`
- **禁止无意义命名** — `data`, `info`, `item`, `temp`, `result`, `obj` 不能独立作为变量名

## 项目命名规则

### 文件命名（全项目统一一种）

- 源码文件：[TODO:选择 kebab-case / camelCase / PascalCase]
- 组件文件：[TODO:选择命名规则]
- 数据文件：[TODO:选择命名规则]
- 类型定义文件：[TODO:选择命名规则]
- 测试文件：与源文件同名 + `.test` 后缀

### 代码命名

| 类别 | 规则 | 示例 |
|------|------|------|
| 类/接口/类型 | PascalCase | `UserRepository`, `EventBus` |
| 函数/方法/变量 | camelCase | `getUserById`, `isActive` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `API_BASE_URL` |
| 私有属性/方法 | [TODO:选择 前缀下划线 / # 私有字段 / 其他] | `_cache`, `#internal` |
| 布尔变量 | `is/has/can/should` 前缀 | `isLoading`, `hasPermission` |
| 事件名 | `命名空间:动作` 或 `on动词` | `user:updated`, `onResize` |

## 示例

✅ 正确：
```typescript
const isUserAuthenticated = checkAuth(currentUser);
const retryDelayMs = 3000;
function calculateTotalPrice(items: CartItem[]): number { /* ... */ }
```

❌ 错误：
```typescript
const d = getData();          // 无意义命名
const usrAuth = chkA(u);      // 无意义缩写
const flag = true;             // flag是什么flag？
function proc(x: any) { }     // proc什么？x是什么？
```

## 提交前检查清单

- [ ] 新变量/函数名能让不看上下文的人理解含义
- [ ] 没有使用 `data`, `info`, `temp`, `result` 等作为独立变量名
- [ ] 同一概念在所有文件中使用同一名称
- [ ] 文件命名遵循项目统一约定
- [ ] 布尔变量使用了 `is/has/can/should` 前缀
