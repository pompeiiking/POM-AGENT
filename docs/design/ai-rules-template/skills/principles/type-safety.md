---
name: type-safety
description: 强类型严格模式的具体规则，禁用any和类型逃生舱，所有公共函数必须有返回类型。写类型声明或遇到类型问题时加载。
metadata:
  priority: L1
  category: principles
---

# 强类型严格模式

## 通用规则（所有语言）

- **不用类型系统的"逃生舱"来绕过编译/检查** — 类型问题必须正面解决
- **所有公共函数必须有明确的参数类型和返回类型声明**
- **类型定义集中管理** — 不在多个文件中重复定义相同类型

## TypeScript 专属规则

- `strict: true`, `noImplicitAny: true` 必须开启
- **禁止 `any`** — 用 `unknown` + 类型守卫，或定义具体类型
- **禁止 `@ts-ignore`** — 修复类型问题而非跳过
- **禁止 `as` 强制断言**（除非有充分理由并添加注释说明）
- 优先使用 `interface` 定义对象形状，`type` 用于联合类型和工具类型

✅ 正确：
```typescript
function parseConfig(raw: unknown): AppConfig {
  if (!isValidConfig(raw)) {
    throw new ConfigError('Invalid config format');
  }
  return raw;  // 类型守卫已收窄类型
}
```

❌ 错误：
```typescript
function parseConfig(raw: any): any {   // any进any出
  return raw as AppConfig;               // 强制断言，绕过检查
}

// @ts-ignore  ← 掩盖了真正的类型错误
const result = brokenFunction();
```

## Python 专属规则

- 启用 mypy 或 pyright 严格模式
- 所有公共函数必须有类型注解（参数 + 返回值）
- **禁止 `# type: ignore`**（除非有充分理由并注释说明）
- 使用 `TypedDict` 替代普通 `dict` 传递结构化数据

✅ 正确：
```python
def get_user_by_id(user_id: str) -> User | None:
    """通过ID查找用户"""
    return self.repo.find(user_id)
```

❌ 错误：
```python
def get_user_by_id(user_id):  # 无类型注解
    return self.repo.find(user_id)  # type: ignore
```

## 其他语言

[TODO:填充该语言的类型安全规则]

## 提交前检查清单

- [ ] 所有公共函数都有参数类型和返回类型声明
- [ ] 没有 `any` / `@ts-ignore` / `# type: ignore` / `as` 强制断言
- [ ] 新增的类型定义没有与现有类型重复
- [ ] 复杂类型有简短的说明注释
