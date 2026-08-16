$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$pythonPath = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python 3.13 was not found at $pythonPath. Update `$pythonPath in this launcher to your Python executable."
}

Write-Host "Starting Career Copilot at http://127.0.0.1:8765"
Write-Host "Keep this window open. Press Ctrl+C to stop."
& $pythonPath -m career_copilot
