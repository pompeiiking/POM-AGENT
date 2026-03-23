# 加载 env.ps1 后启动 HTTP 服务（模型相关用例需已配置 DEEPSEEK_API_KEY）
# 用法：在 pompeii 根目录执行
#   .\scripts\run-http.ps1

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "load_env.ps1")
$env:PYTHONPATH = "src"
python -m app.http_runtime
