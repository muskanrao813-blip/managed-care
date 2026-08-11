# ============================================================
# MANAGED CARE 3.0 - COMPLETE DAILY AUTOMATION (ALL SCRIPTS)
# FIXED VERSION - Looks in /data subdirectory
# Runs at 6:00 AM via Task Scheduler
#
# Purpose: Generate fresh data -> Copy to Render -> Deploy live
# ============================================================

$ScriptDir = "C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python"
$DeployDataDir = Join-Path $ScriptDir "deploy\Data"
$GitProjectDir = "C:\Users\muskan.rao\Documents\managed-care-platform"
$LogDir = Join-Path $ScriptDir "logs"
$LogFile = Join-Path $LogDir "daily_$(Get-Date -Format 'yyyy-MM-dd_HH-mm').log"

# Create directories
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory $LogDir -Force | Out-Null }
if (-not (Test-Path $DeployDataDir)) { New-Item -ItemType Directory $DeployDataDir -Force | Out-Null }

function Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "HH:mm:ss"
    $logMsg = "[$timestamp] [$Level] $Message"
    Write-Host $logMsg
    Add-Content -Path $LogFile -Value $logMsg -Encoding UTF8
}

Log "========== MANAGED CARE DAILY AUTOMATION (ALL SCRIPTS) START ==========="

# Mark pipeline start
python update_pipeline_status.py start 2>&1 | Tee-Object -FilePath $LogFile -Append

# STEP 1: Run all data generation scripts
Log "STEP 1: Running all data generation scripts..."
Set-Location $ScriptDir

# Suppress Python warnings (they're just deprecation notices, not errors)
$env:PYTHONWARNINGS = "ignore::DeprecationWarning,ignore::InsecureRequestWarning"

# List of all scripts to run (in order, some run twice for 2025 and 2026)
$allScripts = @(
    @{name="01_raw_data_program_allocation.py"; year="2025"},
    @{name="01_raw_data_program_allocation.py"; year="2026"},
    @{name="02_comparison_retest_analysis.py"; year="2025"},
    @{name="02_comparison_retest_analysis.py"; year="2026"},
    @{name="04_claude_analysis.py"; year="all"},
    @{name="vytal_appt_flat_analysis.py"; year="all"},
    @{name="05_combined_engagement_effect.py"; year="all"},
    @{name="fetch_engagement_activities.py"; year="all"},
    @{name="map_engagement_hrx_to_phr.py"; year="all"},
    @{name="analyze_vytal_engagement_unique.py"; year="all"},
    @{name="generate_daily_engagement_metrics.py"; year="all"},
    @{name="fetch_hra_wellness.py"; year="2026"},
    @{name="03b_device_eligibility_2026.py"; year="2026"},
    @{name="fetch_voicebot_appt_source.py"; year="all"},
    @{name="08_benefit_appointment_deep.py"; year="all"},
    @{name="process_device_delivered_2025.py"; year="2025"},
    @{name="09_generate_recommendations.py"; year="all"}
)

$scriptCount = 0
foreach ($script in $allScripts) {
    $scriptCount++
    Log "[$scriptCount/$($allScripts.Count)] Running: $($script.name) (year=$($script.year))"

    # Run Python and suppress urllib3/deprecation warnings by filtering stderr
    python $script.name 2>&1 | Where-Object { $_ -notmatch "InsecureRequestWarning|DeprecationWarning|urllib3|dbapi|warnings.warn" } | Tee-Object -FilePath $LogFile -Append

    if ($LASTEXITCODE -ne 0) {
        Log "WARNING: $($script.name) exited with code $LASTEXITCODE (continuing with next script)" "WARN"
    }
}

Log "OK - All scripts completed"

# STEP 2: Copy fresh data to deploy/Data/
Log "STEP 2: Copying data to Render deployment folder..."
$csvPatterns = @("*.csv", "*.json")
$copiedCount = 0

# Look in both root and /Data subdirectory (capital D)
$searchPaths = @($ScriptDir, (Join-Path $ScriptDir "Data"))

foreach ($searchPath in $searchPaths) {
    if (-not (Test-Path $searchPath)) { continue }

    foreach ($pattern in $csvPatterns) {
        $files = Get-ChildItem -Path $searchPath -Include $pattern -File -ErrorAction SilentlyContinue |
                 Where-Object { $_.Name -notmatch "^\..*" -and $_.Name -match "managed_care|claude_insights|vytal" }

        foreach ($file in $files) {
            $destPath = Join-Path $DeployDataDir $file.Name
            Copy-Item -Path $file.FullName -Destination $destPath -Force -ErrorAction SilentlyContinue
            $copiedCount++
            Log "  Copied: $($file.Name)"
        }
    }
}

Log "OK - Copied $copiedCount files to deploy/Data/"

# STEP 3: Commit and push to GitHub for Render auto-rebuild
Log "STEP 3: Pushing to GitHub for Render deployment..."
Set-Location $GitProjectDir

try {
    git fetch origin 2>&1 | Out-Null
    git pull origin main --ff-only -ErrorAction SilentlyContinue 2>&1 | Out-Null

    # Stage all changes in deploy/Data/ using forward slashes (git standard)
    git add -f "Manage care python/deploy/Data/*" 2>&1 | Out-Null

    # Check if there are changes to commit
    $status = git status --porcelain 2>&1
    if ($status) {
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
        git commit -m "Daily data update: Complete pipeline refresh - $timestamp" -ErrorAction Stop 2>&1 | Out-Null
        git push origin main -ErrorAction Stop 2>&1 | Out-Null
        Log "OK - Pushed to GitHub - Render rebuilding in 2-3 minutes"
    } else {
        Log "WARN - No changes to commit"
    }
} catch {
    Log "ERROR - Git push failed: $_" "WARN"
    Log "Continuing with next step..." "WARN"
}

# Mark pipeline end
python update_pipeline_status.py end 2>&1 | Tee-Object -FilePath $LogFile -Append

# STEP 4: Summary
Log ""
Log "========== DAILY AUTOMATION COMPLETE =========="
Log "Total scripts run: $($allScripts.Count)"
Log "Data files copied: $copiedCount files to deploy/Data/"
Log "Render: Auto-rebuilding (watch for update in 2-3 min)"
Log "Dashboard: https://managed-care-dashboard.onrender.com/"
Log "Log: $LogFile"
Log "==========================================="

exit 0
