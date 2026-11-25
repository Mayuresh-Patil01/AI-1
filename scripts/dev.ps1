# Starts SORTIFIED for development: the engine in a second window, the UI in this one.
# Usage: double-click dev.cmd, or run:  .\dev.cmd

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path "engine\.venv\Scripts\python.exe") -or -not (Test-Path "ui\node_modules")) {
    Write-Host "First time? Running setup..." -ForegroundColor Yellow
    & "$PSScriptRoot\setup.ps1"
}

# Engine: --reload restarts it automatically when Python files change.
Start-Process powershell -WorkingDirectory "$root\engine" -ArgumentList @(
    "-NoExit", "-Command",
    "`$host.UI.RawUI.WindowTitle = 'SORTIFIED engine'; .venv\Scripts\python -m uvicorn sortified.main:app --reload --port 8000"
)

# Open the browser once the UI is up, then run the UI dev server here.
Start-Job { Start-Sleep 4; Start-Process "http://localhost:5173" } | Out-Null
Set-Location ui
npm run dev
