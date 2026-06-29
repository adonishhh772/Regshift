$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Virtual env not found. Run scripts/setup-venv.ps1 first."
    exit 1
}

$env:DATA_DIR = Join-Path $Root "data"
Set-Location $Backend
& $VenvPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
