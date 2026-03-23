---
name: security
description: 密钥管理、环境变量、敏感数据处理、依赖安全、输入验证。涉及认证、密钥、外部API或用户输入时加载。
metadata:
  priority: L1
  category: workflow
---

# 安全规范

## 铁律（已在全局铁律中，此处展开详述）

**密钥凭证不入代码库。** API Key、密码、token、证书等敏感信息只走环境变量。

## 规则

### 1. 密钥与凭证管理

- **所有密钥/token/密码通过环境变量注入**，不硬编码在源码中
- **提供 `.env.example` 文件**列出所有需要的环境变量（值留空或用占位符）
- **`.env` 文件必须在 `.gitignore` 中** — 绝不提交到版本控制
- **日志中不输出密钥** — 日志框架应自动脱敏或手动过滤

✅ 正确：
```typescript
// .env.example（提交到git）
// API_KEY=your_api_key_here
// DATABASE_URL=postgresql://...

// 代码中通过环境变量读取
const apiKey = process.env.API_KEY;
if (!apiKey) throw new ConfigError('API_KEY environment variable is required');
```

❌ 错误：
```typescript
const apiKey = "sk-1234567890abcdef";  // 硬编码密钥！
console.log(`Connecting with key: ${apiKey}`);  // 日志泄露密钥！
```

### 2. 用户输入验证

- **所有外部输入（用户输入、API参数、文件内容）在系统边界处验证**
- **验证逻辑与业务逻辑分离** — 用专门的验证层/中间件
- **验证失败返回明确错误信息**，不暴露系统内部细节

### 3. 依赖安全

- **新增依赖前检查**：最近更新时间、下载量、已知漏洞
- **定期更新依赖** — 不使用已知有安全漏洞的版本
- **锁定依赖版本** — 使用 lock 文件（package-lock.json / yarn.lock / poetry.lock）

### 4. 错误信息安全

- **面向用户的错误信息不暴露系统内部** — 不暴露文件路径、堆栈、数据库结构
- **内部错误详情只写入日志**，不返回给前端

✅ 正确：
```typescript
// 返回给用户
res.status(500).json({ error: '服务暂时不可用，请稍后重试' });

// 写入日志（内部）
logger.error('Database connection failed', { host, port, error: err.message });
```

❌ 错误：
```typescript
// 暴露内部信息给用户
res.status(500).json({ error: err.stack });  // 完整堆栈泄露！
```

## 提交前检查清单

- [ ] 代码中没有硬编码的密钥、token、密码
- [ ] `.env` 文件在 `.gitignore` 中
- [ ] 新增的环境变量已在 `.env.example` 中列出
- [ ] 日志中没有输出敏感信息
- [ ] 外部输入在系统边界处有验证
- [ ] 面向用户的错误信息不包含内部细节
