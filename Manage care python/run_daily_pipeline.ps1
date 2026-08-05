#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Managed Care 3.0 - Daily Pipeline Runner

.DESCRIPTION
  Runs every day at 6 AM via Task Scheduler
  - Executes scripts 01-04 (local Trino queries)
  - Populates Neon PostgreSQL with all data
  - Commits and pushes to GitHub
  - Render auto-deploys dashboard
#>

$ScriptDir = "C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python"
$ProjectDir = "C:\Users\muskan.rao\Documents\managed-care-platform"
$LogFile = Join-Path $ScriptDir "pipeline_$(Get-Date -Format 'yyyy-MM-dd_HHmmss').log"

Write-Host "==============================================================================
 MANAGED CARE 3.0 — DAILY PIPELINE RUNNER
 Started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
==============================================================================" -ForegroundColor Cyan

$env:DATABASE_URL = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

function Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "HH:mm:ss"
    $logMsg = "[$timestamp] $Message"
    Write-Host $logMsg
    Add-Content -Path $LogFile -Value $logMsg
}

# Step 1: Run scripts
Log "STEP 1: Running Managed Care scripts (01-04)"
Push-Location $ScriptDir
python run_scripts_clean.py 2>&1 | Tee-Object -FilePath $LogFile -Append
Pop-Location

# Step 2: Populate data
Log "STEP 2: Loading all CSVs into Neon"
Push-Location $ScriptDir
python populate_complete_data.py 2>&1 | Tee-Object -FilePath $LogFile -Append
Pop-Location

# Step 3: Commit and push
Log "STEP 3: Committing changes to GitHub"
Push-Location $ProjectDir
git add -A
git commit -m "Daily data update — $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
git push origin main
Pop-Location

Log "COMPLETE — Dashboard: https://managed-care-dashboard.onrender.com/"
Log "Log: $LogFile"
