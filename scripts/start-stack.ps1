# RegShift full dev stack: Neo4j + backend + frontend + Langfuse (Postgres, ClickHouse, Redis, MinIO)
# Usage: .\scripts\start-stack.ps1

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Test-Path ".env")) {
    Write-Error ".env not found. Copy infra/llm.env.example and infra/langfuse.env.example values into .env first."
}

Write-Host "Starting RegShift + Langfuse stack..." -ForegroundColor Cyan
Write-Host "  RegShift UI:    http://localhost:3000"
Write-Host "  RegShift API:   http://localhost:8000/health"
Write-Host "  Langfuse UI:    http://localhost:3001"
Write-Host ""
Write-Host "Langfuse infra (Docker internal only): Postgres, ClickHouse, Redis, MinIO"
Write-Host ""

docker compose -f docker-compose.mini.yml -f docker-compose.langfuse.yml up --build
