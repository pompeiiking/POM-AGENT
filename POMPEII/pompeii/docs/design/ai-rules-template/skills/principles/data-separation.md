---
name: data-separation
description: 数据文件与代码文件严格分离，通过接口访问数据，数据格式变化不影响业务逻辑。涉及数据文件或配置时加载。
metadata:
  priority: L2
  category: principles
  depends: layering
---

# 数据与逻辑分离

## 规则

- **源码目录下不允许出现数据文件**（配置JSON如 tsconfig.json 除外）
- **数据目录下不允许出现代码文件**
- **代码不直接读取数据文件路径**，必须通过数据访问接口（DataSource/Repository）
- **数据格式变化不应导致业务逻辑代码修改** — 格式转换在数据访问层处理

## 示例

✅ 正确：
```typescript
// 数据访问接口 — 业务层不关心数据来自JSON还是数据库
interface PostDataSource {
  getAll(): Promise<Post[]>;
  getById(id: string): Promise<Post | null>;
}

// JSON实现 — 格式转换在这里处理
class JsonPostDataSource implements PostDataSource {
  async getAll(): Promise<Post[]> {
    const raw = await this.loader.load('posts');
    return raw.map(this.normalize);  // 格式转换封装在数据层
  }
}
```

❌ 错误：
```typescript
// 业务逻辑直接读文件、直接处理格式
import posts from '../data/posts.json';

function getRecentPosts() {
  return posts.filter(p => p.date > '2026-01-01');  // 硬编码路径+格式耦合
}
```

## 项目数据目录结构

[TODO:填充你的数据目录结构，示例:]
```
data/
├── content/     # 内容数据（文章、页面等）
├── config/      # 应用配置
└── assets/      # 静态资源元数据
```

## 提交前检查清单

- [ ] 新增的数据文件放在了数据目录下，不在源码目录中
- [ ] 代码中没有直接 `import` 或 `require` 数据文件
- [ ] 数据格式的解析/转换逻辑在数据访问层，不在业务层
- [ ] 更换数据格式（如JSON→YAML）只需改数据访问层实现
