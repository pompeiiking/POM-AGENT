# 全局共享类型契约

> 状态: 草案
> 负责人: [TODO:填充]
> 最后更新: [TODO:填充]

## 说明

本文件定义所有模块都必须使用的公共类型。任何模块在实现时，涉及这些类型的地方必须严格使用此处的定义，不得自行定义同名或类似类型。

## 共享类型定义

```typescript
// [TODO:填充全局共享类型]
//
// 示例：
// interface BaseEntity {
//   id: string;
//   createdAt: Date;
//   updatedAt: Date;
// }
//
// type Status = 'active' | 'inactive' | 'pending';
```

## 共享常量/枚举

```typescript
// [TODO:填充全局共享常量]
//
// 示例：
// enum ErrorCode {
//   NOT_FOUND = 'NOT_FOUND',
//   UNAUTHORIZED = 'UNAUTHORIZED',
//   VALIDATION_ERROR = 'VALIDATION_ERROR',
// }
```

## 共享错误类型

```typescript
// [TODO:填充全局错误类型]
//
// 示例：
// interface AppError {
//   code: ErrorCode;
//   message: string;
//   details?: Record<string, unknown>;
// }
```
