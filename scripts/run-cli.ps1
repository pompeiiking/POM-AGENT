$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
. (Join-Path $PSScriptRoot "load_env.ps1")
$env:PYTHONPATH = "src"
python -m app.cli_runtime
