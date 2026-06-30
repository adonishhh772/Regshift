# Verify RegShift + Langfuse stack health after startup
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "`n=== Docker containers ===" -ForegroundColor Cyan
docker compose -f docker-compose.mini.yml -f docker-compose.langfuse.yml ps

Write-Host "`n=== Service checks ===" -ForegroundColor Cyan

function Test-Endpoint {
    param([string]$Name, [string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
        Write-Host "[OK] $Name ($Url) -> $($response.StatusCode)" -ForegroundColor Green
    }
    catch {
        Write-Host "[FAIL] $Name ($Url) -> $($_.Exception.Message)" -ForegroundColor Red
    }
}

Test-Endpoint "RegShift API" "http://localhost:8000/health"
Test-Endpoint "RegShift UI" "http://localhost:3000"
Test-Endpoint "Langfuse UI" "http://localhost:3001"

Write-Host "`n=== Langfuse infra (internal Docker network) ===" -ForegroundColor Cyan
Write-Host "  langfuse-postgres   -> Postgres (users, projects, API keys)"
Write-Host "  langfuse-clickhouse -> ClickHouse (LLM trace analytics)"
Write-Host "  langfuse-redis      -> Redis (job queue + cache)"
Write-Host "  langfuse-minio      -> MinIO (trace blob storage)"
Write-Host "  langfuse-worker     -> background trace ingestion"
Write-Host "  langfuse-web        -> UI + API on port 3001"
Write-Host ""

$health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 10 -ErrorAction SilentlyContinue
if ($health) {
    Write-Host "LLM gateway enabled: $($health.llm.enabled)" -ForegroundColor Yellow
    Write-Host "Langfuse available:  $($health.langfuse.available)" -ForegroundColor Yellow
    Write-Host "Neo4j available:     $($health.neo4j.available)" -ForegroundColor Yellow
}
