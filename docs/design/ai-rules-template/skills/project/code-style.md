---
name: code-style
description: 项目代码风格：文件内部结构顺序、组件写法模板、样式方案、格式化配置。写代码时加载。
metadata:
  priority: L3
  category: project
  depends: naming, comments
---

# 代码风格

## 文件内部结构顺序

**每个源码文件按以下顺序组织（不可打乱）：**

```
1. 导入语句（按分组排列）
   a. 语言/框架内置模块
   b. 第三方库
   c. 项目内部模块（按层级从底到顶）
   d. 同目录/相对路径模块
   e. 类型导入（type imports）

2. 类型定义（该文件的局部类型/接口）

3. 常量定义

4. 主要导出（函数/类/组件）

5. 辅助函数（内部使用，不导出）
```

## 示例

✅ 正确：
```typescript
// === 1. 导入 ===
import { useEffect, useState } from 'react';          // a. 框架
import { motion } from 'framer-motion';                // b. 第三方
import { eventBus } from '@/core/event-bus';           // c. 项目内部
import { formatDate } from './utils';                  // d. 同目录
import type { UserProfile } from '@/types';            // e. 类型

// === 2. 类型 ===
interface UserCardProps {
  userId: string;
  showAvatar?: boolean;
}

// === 3. 常量 ===
const ANIMATION_DURATION = 0.3;

// === 4. 主要导出 ===
export function UserCard({ userId, showAvatar = true }: UserCardProps) {
  // ...
}

// === 5. 辅助函数 ===
function getInitials(name: string): string {
  // ...
}
```

❌ 错误：
```typescript
// 导入散乱，常量和函数混在一起
import { formatDate } from './utils';
const MAX = 10;
import { useState } from 'react';
function helper() { }
import type { User } from '@/types';
export function Main() { }
```

## 组件写法模板

[TODO:填充你的框架的组件模板，以下为React示例:]

```typescript
// 函数组件模板
interface [ComponentName]Props {
  // props定义
}

export function [ComponentName]({ prop1, prop2 }: [ComponentName]Props) {
  // hooks
  // 状态
  // 副作用
  // 事件处理函数
  // 渲染
  return (
    // JSX
  );
}
```

## 样式方案

[TODO:填充你的样式方案，示例:]
```
- 使用 TailwindCSS 作为主要样式方案
- 组件专属样式使用 CSS Modules（如需要）
- 不使用内联style对象（除动态计算值外）
- 不使用全局CSS类名（除reset和基础排版）
```

## 格式化配置

[TODO:填充你的格式化工具配置，示例:]
```
- 格式化工具: Prettier
- 缩进: 2空格
- 分号: 有
- 引号: 单引号
- 行尾: LF
- 最大行宽: 100字符
- 尾随逗号: all
```

## 语言专属规则

[TODO:填充你的语言/框架专属规则]

## 提交前检查清单

- [ ] 文件内部结构按规定顺序排列（导入→类型→常量→导出→辅助）
- [ ] 导入语句按分组排列
- [ ] 组件写法符合项目模板
- [ ] 样式使用了项目规定的方案
- [ ] 代码已通过格式化工具格式化
