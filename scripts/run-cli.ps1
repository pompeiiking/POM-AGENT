# 加载 env.ps1 后启动 CLI（与 run-http 相同的环境变量注入）
# 用法：在 pompeii 根目录执行
#   .\scripts\run-cli.ps1

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "load_env.ps1")
$env:PYTHONPATH = "src"
python -m app.cli_runtime
