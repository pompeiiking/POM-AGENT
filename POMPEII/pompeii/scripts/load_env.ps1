# Load env.ps1 if present: prefer config/env.ps1, then repo-root env.ps1 (ASCII-only output).
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Candidates = @(
    (Join-Path $RepoRoot "config\env.ps1"),
    (Join-Path $RepoRoot "env.ps1")
)
$Loaded = $false
foreach ($EnvScript in $Candidates) {
    if (Test-Path $EnvScript) {
        . $EnvScript
        Write-Host "Loaded env: $EnvScript"
        $Loaded = $true
        break
    }
}
if (-not $Loaded) {
    Write-Warning "env.ps1 not found. Copy config/env.ps1.example to config/env.ps1 (or env.ps1 at repo root) and set DEEPSEEK_API_KEY."
}
