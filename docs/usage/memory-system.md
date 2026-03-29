# 记忆系统

## 概览

记忆系统由 `MemoryOrchestrator` 管理，采用**双存储架构**：

```
短期记忆（SQLite）
    │ 定期归档
    ▼
长期记忆（SQLite + 向量）
    │
    ├── 精确检索（FTS5 全文搜索）
    └── 语义检索（OpenAI 兼容嵌入向量）
          │
          └── RRF 混合排序 → 返回 top-k → 注入上下文
```

---

## 启用记忆系统

```python
from pompeii_agent import AgentBuilder

kernel = (
    AgentBuilder()
    .session(model="stub", skills=["echo"])
    .kernel(core_max_loops=8, tool_allowlist=["echo", "search_memory"])
    .memory()
        .enable()                      # 必须显式开启
        .retrieve_top_k(6)             # 每次检索返回 top-k
        .embedding_dim(64)              # 嵌入维度
    .done()
    .build()
)
```

---

## 检索 API

记忆系统自动注册 `search_memory` 工具：

```python
# 在 AgentBuilder 中添加 search_memory 到白名单即可使用
.kernel(tool_allowlist=["echo", "search_memory"])
```

Agent 在处理每条输入前会自动调用 `search_memory` 检索相关记忆并注入上下文。

### 手动调用

```python
from pompeii_agent.advanced import MemoryOrchestrator

hits = memory_orch.retrieve_as_tool_json(
    user_id="u1",
    channel="web",
    query_text="关于张三的信息",
)
# hits 是 list[dict]，包含 score、content 等字段
```

---

## 嵌入后端

### 内置 Hash 嵌入（默认，无需 API Key）

```python
.memory().enable().embedding_dim(64)
```

基于文本哈希的近似检索，适合开发/测试环境。

### OpenAI 兼容嵌入

```python
.memory()
    .enable()
    .use_openai_embedding(
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com",       # 可替换为其他兼容 API
        model="text-embedding-3-small",
    )
```

支持任何兼容 OpenAI embeddings 格式的 API（如 Ollama、DeepSeek、Cohere 等）。

---

## 检索策略

### 混合排序（RRF）

默认使用 **RRF（Reciprocal Rank Fusion）** 混合精确检索与语义检索结果：

```python
.memory()
    .retrieve_top_k(6)          # 最终返回 top-k
    .rerank_enabled(True)       # 开启 rerank
    .rerank_max_candidates(24)  # rerank 候选数
```

### 频道过滤

```python
.memory().channel_filter("match_or_global")
# "match_only"   — 只检索当前 channel 的记忆
# "match_or_global" — 当前 channel + 全局记忆
```

### 归档策略

```python
.memory()
    .promote_on_archive(True)                    # 归档时提升到长期记忆
    .archive_chunk_max_chars(8000)               # 归档块大小
    .archive_trust("medium")                     # 信任级别
```

---

## 会话消息自动归档

当会话消息超过阈值时，自动触发 LLM 摘要归档：

```python
.kernel(
    archive_llm_summary_enabled=True,
    archive_llm_summary_provider_id="my-model",
    archive_llm_summary_max_dialogue_chars=12000,
    archive_llm_summary_max_output_chars=2000,
)
```

需要同时配置 `AgentBuilder.model_registry(...)` 指定摘要用模型。

---

## 记忆 API（MemoryOrchestrator）

```python
from pompeii_agent.advanced import MemoryOrchestrator

# 检索
hits = orch.retrieve(
    user_id="u1",
    channel="web",
    query_text="张三的信息",
    top_k=6,
)

# 直接写入
orch.add(
    user_id="u1",
    channel="web",
    content="张三喜欢打篮球",
    metadata={"source": "user"},
)

# 删除
orch.delete(hit_id="xxx", user_id="u1")

# 归档
orch.archive(session_id="sess-123")
```

---

## 完整示例

```python
from pompeii_agent import AgentBuilder, ModelRegistryBuilder, ModelProviderBuilder

registry = (
    ModelRegistryBuilder(default_provider="deepseek")
    .add(ModelProviderBuilder("deepseek", "openai_compatible")
        .api_base_url("https://api.deepseek.com")
        .model_name("deepseek-chat")
        .api_key_env("DEEPSEEK_API_KEY"))
    .build()
)

kernel = (
    AgentBuilder()
    .session(model="deepseek", skills=["echo"])
    .kernel(
        core_max_loops=12,
        tool_allowlist=["echo", "search_memory"],
        archive_llm_summary_enabled=True,
        archive_llm_summary_provider_id="deepseek",
    )
    .memory()
        .enable()
        .retrieve_top_k(3)
        .embedding_dim(64)
        .rerank_enabled(True)
        .channel_filter("match_or_global")
    .done()
    .model_registry(registry)
    .build()
)

# 触发 /remember 写入记忆
invoke_kernel(kernel, user_id="alice", channel="c1",
    text="/remember 我的宠物叫旺财，是一只金毛")

# 后续对话自动携带相关记忆
invoke_kernel(kernel, user_id="alice", channel="c1",
    text="我之前和你说过我的宠物叫什么？")
```
