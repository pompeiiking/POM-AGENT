$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$env:PYTHONPATH = "src"
python -m app.resource_migrate_runtime $args
