# Managed Care Daily Pipeline Runner
# Runs all 4 scripts and pushes data to Neon PostgreSQL
# Scheduled daily at 6:00 AM via Task Scheduler

# Set Neon connection
$env:DATABASE_URL = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

# Set working directory
$ScriptDir = "C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python"
Set-Location $ScriptDir

# Log file
$LogFile = Join-Path $ScriptDir "logs\daily_run_$(Get-Date -Format 'yyyy-MM-dd').log"
$LogDir = Join-Path $ScriptDir "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory $LogDir -Force | Out-Null }

# Start logging
"[$(Get-Date)] ========== MANAGED CARE DAILY PIPELINE ==========" | Tee-Object -FilePath $LogFile -Append
"[$(Get-Date)] Database: Neon PostgreSQL (managed_care schema)" | Tee-Object -FilePath $LogFile -Append
"[$(Get-Date)] " | Tee-Object -FilePath $LogFile -Append

# Script 01: Programme Allocation
"[$(Get-Date)] Running Script 01: Programme Allocation..." | Tee-Object -FilePath $LogFile -Append
python 01_raw_data_program_allocation.py *>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    "[$(Get-Date)] ERROR in script 01 - Exit code: $LASTEXITCODE" | Tee-Object -FilePath $LogFile -Append
    exit 1
}

# Script 02: Comparison & Retest
"[$(Get-Date)] Running Script 02: Comparison & Retest..." | Tee-Object -FilePath $LogFile -Append
python 02_comparison_retest_analysis.py *>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    "[$(Get-Date)] ERROR in script 02 - Exit code: $LASTEXITCODE" | Tee-Object -FilePath $LogFile -Append
    exit 1
}

# Script 03: Device Eligibility
"[$(Get-Date)] Running Script 03: Device Eligibility..." | Tee-Object -FilePath $LogFile -Append
python "03b_device_eligibility_2026.py" *>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    "[$(Get-Date)] ERROR in script 03 - Exit code: $LASTEXITCODE" | Tee-Object -FilePath $LogFile -Append
    exit 1
}

# Script 04: Claude Analysis
"[$(Get-Date)] Running Script 04: Claude Analysis..." | Tee-Object -FilePath $LogFile -Append
python 04_claude_analysis.py *>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    "[$(Get-Date)] ERROR in script 04 - Exit code: $LASTEXITCODE" | Tee-Object -FilePath $LogFile -Append
    exit 1
}

# Success
"[$(Get-Date)] " | Tee-Object -FilePath $LogFile -Append
"[$(Get-Date)] SUCCESS - All scripts completed" | Tee-Object -FilePath $LogFile -Append
"[$(Get-Date)] Data pushed to Neon PostgreSQL" | Tee-Object -FilePath $LogFile -Append
"[$(Get-Date)] Dashboard will update within 10 seconds" | Tee-Object -FilePath $LogFile -Append
"[$(Get-Date)] ==============================================" | Tee-Object -FilePath $LogFile -Append

exit 0
