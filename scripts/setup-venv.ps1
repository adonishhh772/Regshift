$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Backend = Join-Path $Root "backend"
$Venv = Join-Path $Backend ".venv"

Write-Host "Creating virtual environment at $Venv ..."
python -m venv $Venv

$Python = Join-Path $Venv "Scripts\python.exe"
$Pip = Join-Path $Venv "Scripts\pip.exe"

& $Pip install --upgrade pip
& $Pip install -r (Join-Path $Backend "requirements.txt")

Write-Host ""
Write-Host "Done. Activate with:"
Write-Host "  cd backend"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Run backend:"
Write-Host "  `$env:DATA_DIR='$Root\data'; uvicorn app.main:app --reload --port 8000"
