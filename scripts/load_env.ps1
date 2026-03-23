# Load repo-root env.ps1 if present (ASCII-only output; do not commit env.ps1).
$RepoRoot = Split-Path -Parent $PSScriptRoot
$EnvScript = Join-Path $RepoRoot "env.ps1"
if (Test-Path $EnvScript) {
    . $EnvScript
    Write-Host "Loaded env: $EnvScript"
}
else {
    Write-Warning "env.ps1 not found at $EnvScript. Set DEEPSEEK_API_KEY in the environment, or create env.ps1 locally (see README; gitignored)."
}
