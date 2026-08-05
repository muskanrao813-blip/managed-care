#Requires -RunAsAdministrator
<#
.SYNOPSIS
Launch Managed Care daily pipeline via Claude Code CLI
Runs when laptop starts (via Task Scheduler)

.DESCRIPTION
This script invokes Claude Code to run the Managed Care skill daily

.EXAMPLE
powershell.exe -ExecutionPolicy Bypass -File launch_daily_via_claude.ps1
#>

$ScriptDir = "D:\OneDrive - Bajaj Finserv Health Limited\Documents\manage care\Manage care python"
$ProjectDir = "C:\Users\muskan.rao\Documents\managed-care-platform"

# Set environment
$env:DATABASE_URL = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

# Optional: Claude API key for AI recommendations
# $env:ANTHROPIC_API_KEY = "sk-..."

Write-Host "╔════════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                MANAGED CARE 3.0 — DAILY PIPELINE VIA CLAUDE SKILL              ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host "Environment: DATABASE_URL set for Neon" -ForegroundColor Gray
Write-Host ""

# Method 1: Direct Python runner (most reliable)
Write-Host "Running Managed Care daily pipeline..." -ForegroundColor Yellow
Push-Location $ScriptDir

$startTime = Get-Date
python cli_daily_runner.py
$exitCode = $LASTEXITCODE
$duration = ((Get-Date) - $startTime).TotalSeconds

Pop-Location

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "✓ Pipeline completed successfully in ${duration}s" -ForegroundColor Green
    Write-Host "✓ Dashboard: https://managed-care-dashboard.onrender.com/" -ForegroundColor Green
    Write-Host "✓ Next run: Tomorrow at $(Get-Date -Hour 6 -Minute 0 -Second 0 -Millisecond 0)" -ForegroundColor Green
} else {
    Write-Host "✗ Pipeline failed with exit code $exitCode" -ForegroundColor Red
    Write-Host "Check logs at: $ScriptDir\pipeline_*.log" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
