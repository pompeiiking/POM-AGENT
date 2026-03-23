# API 密钥配置操作手册

本手册说明如何为 Pompeii-Agent 配置 DeepSeek API Key，使模型模块能正常调用 DeepSeek 接口。

**复制粘贴说明**：代码块中的命令均为单行或逐行独立，请按说明整行复制到 PowerShell 执行，避免复制到多余空格、换行或续行符导致报错。

---

## 一、获取 API Key

1. 打开 [DeepSeek 开放平台](https://platform.deepseek.com) 并登录。
2. 进入「API Keys」或「密钥管理」页面，创建新密钥。
3. 复制生成的 Key（形如 `sk-xxxxxxxx...`），妥善保存。**不要将真实 Key 提交到 Git 或写入配置文件。**

---

## 二、本地运行（本机 / 开发机）

程序通过 **环境变量** `DEEPSEEK_API_KEY` 读取密钥，不读配置文件中的敏感字段。任选一种方式即可。

### 方式 A：当前终端临时设置（PowerShell）

打开 PowerShell，在**运行项目前**执行（每行单独复制，将 `sk-你的真实密钥` 换成真实 Key）：

```
$env:DEEPSEEK_API_KEY = "sk-你的真实密钥"
```

然后启动服务（每行单独复制）：

```
cd C:\Users\22271\Desktop\Agent\POMPEII\pompeii
$env:PYTHONPATH = "src"
python -m app.http_runtime
```

- **优点**：简单，不改文件。  
- **缺点**：关闭终端后失效，新开终端需重新设置。

---

### 方式 B：使用脚本注入（推荐，同一终端多次运行）

1. **复制示例脚本**（仅复制一次）：
   - 将 `config/env.ps1.example` 复制为 **`config/env.ps1`**（或复制到仓库根目录并命名为 `env.ps1`，与旧习惯兼容）。  
   - 用记事本或 VS Code 打开该 `env.ps1`，把 `your-deepseek-api-key-here` 换成你的真实 Key 并保存。

2. **每次打开新终端后**，在项目根目录执行（每行单独复制；若使用根目录 `env.ps1` 则把路径改成 `.\env.ps1`）：
   ```
   cd C:\Users\22271\Desktop\Agent\POMPEII\pompeii
   . .\config\env.ps1
   $env:PYTHONPATH = "src"
   python -m app.http_runtime
   ```

3. **若提示「禁止运行脚本」**（无法执行 dot-source）：在同一终端用下面**一行**代替（仅当你信任本机脚本内容时使用）：
   ```
   Get-Content -Path .\config\env.ps1 -Raw | Invoke-Expression
   ```
   然后再执行 `$env:PYTHONPATH = "src"` 与 `python -m app.http_runtime`。  
   或直接使用 **`.\scripts\run-http.cmd`**（内部已用 Bypass 加载 `load_env.ps1`，不依赖你对 `.ps1` 的执行策略）。

**注意**：不要将 `env.ps1`（内含真实 Key）提交到 Git。可将 `env.ps1` 加入 `.gitignore`。

---

### 方式 C：使用 .env 文件（需项目支持加载）

若项目后续支持从 `.env` 自动加载环境变量（例如用 `python-dotenv`），可：

1. 将 `config/.env.example` 复制为 `.env`（通常放在项目根目录，与多数工具约定一致）。
2. 编辑 `.env`，将 `your-deepseek-api-key-here` 改为你的真实 Key。
3. 确保 `.env` 已加入 `.gitignore`，不提交到仓库。

当前版本**未**内置 `.env` 加载；若采用此方式，需在应用入口自行加载或使用方式 A/B。

---

## 三、Docker 运行

在 Docker 中通过 **环境变量** 传入 Key，不要写进镜像或配置文件。

### 构建镜像（无需在 Dockerfile 里写 Key）

每行单独复制执行：

```
cd C:\Users\22271\Desktop\Agent\POMPEII\pompeii
docker build -t pompeii-agent:dev .
```

### 运行时传入 API Key

**方式 1：命令行 -e**（整行复制，将 `sk-你的真实密钥` 换成真实 Key）

```
docker run -it --rm -p 8000:8000 -e DEEPSEEK_API_KEY="sk-你的真实密钥" pompeii-agent:dev
```

**方式 2：使用本地 env 文件（Key 写在本地，不提交）**

1. 在项目根目录创建 `docker.env`，内容一行：
   ```text
   DEEPSEEK_API_KEY=sk-你的真实密钥
   ```
2. 将 `docker.env` 加入 `.gitignore`。
3. 运行（整行复制执行）：
   ```
   docker run -it --rm -p 8000:8000 --env-file docker.env pompeii-agent:dev
   ```

---

## 四、验证是否生效

1. 启动 HTTP 服务（本地或 Docker）。
2. 请求健康检查（整行复制执行）：
   ```
   Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
   ```
3. 发送一条普通对话（整行复制执行）：
   ```
   Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/input" -ContentType "application/json; charset=utf-8" -Body '{"kind":"user_message","user_id":"u1","channel":"http","text":"你好"}'
   ```

- **配置正确**：返回中会包含模型正常回复内容。  
- **未配置或 Key 错误**：返回中可能出现「DeepSeek 模型未配置：请在环境变量 DEEPSEEK_API_KEY 中设置 API Key」或接口报错信息。

---

## 五、安全与规范

| 项目 | 说明 |
|------|------|
| **不要**在 `model_providers.yaml` 中填写 `api_key` | 该文件会进 Git；密钥仅通过环境变量注入。 |
| **不要**提交 `env.ps1`、`.env`、`docker.env` | 若其中含真实 Key，应加入 `.gitignore`。 |
| **不要**在 `config/.env.example`、`config/env.ps1.example` 中写真实 Key | 仅保留占位符，供他人复制后自行填写。 |
| 密钥泄露时 | 到 DeepSeek 平台撤销该 Key 并重新生成。 |

---

## 六、常见问题

**Q：返回“DeepSeek 模型未配置”怎么办？**  
A：当前进程未读到 `DEEPSEEK_API_KEY`。请确认：  
- 在**启动进程的同一终端**中已设置环境变量（方式 A/B），或  
- Docker 使用了 `-e DEEPSEEK_API_KEY=...` 或 `--env-file`。

**Q：PowerShell 里写了 `$env:DEEPSEEK_API_KEY` 但无效？**  
A：确保先执行设置，再在同一窗口执行 `python -m app.http_runtime`；新开的终端需要重新设置或重新执行 `.\env.ps1`。

**Q：能否在代码里写死 Key？**  
A：不能。按项目规范，敏感信息一律通过环境变量或密钥管理服务注入，不写进代码或配置仓库。

---

**文档版本**：与 `src/app/version.py` 对齐（当前 **0.4.4**）。密钥与模型行为无关会话存储；会话落盘见 `docs/design/会话存储与归档实现说明.md`。
