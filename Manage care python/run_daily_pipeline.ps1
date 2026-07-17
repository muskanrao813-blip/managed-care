# ==============================================================
# Managed Care 3.0 - Daily Pipeline Runner
# Runs all scripts in sequence for both 2025 and 2026 camp years,
# then restarts the dashboard server.
# Scheduled via Windows Task Scheduler to run at 6:00 AM daily.
# ==============================================================

$SCRIPT_DIR = "D:\OneDrive - Bajaj Finserv Health Limited\Documents\manage care\Manage care python"
$PYTHON     = "python"
$LOG_DIR    = Join-Path $SCRIPT_DIR "logs"
$TIMESTAMP  = Get-Date -Format "yyyy-MM-dd_HH-mm"
$LOG_FILE   = Join-Path $LOG_DIR "pipeline_$TIMESTAMP.log"

# Create logs directory if missing
if (-not (Test-Path $LOG_DIR)) { New-Item -ItemType Directory $LOG_DIR | Out-Null }

function Log($msg) {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    Write-Host $line
    Add-Content -Path $LOG_FILE -Value $line -Encoding UTF8
}

function Run-Script($script, $yearLabel) {
    Log "--- Running $script (year=$yearLabel) ---"
    $proc = Start-Process -FilePath $PYTHON `
        -ArgumentList $script `
        -WorkingDirectory $SCRIPT_DIR `
        -RedirectStandardOutput "$LOG_DIR\${script}_${yearLabel}_stdout.txt" `
        -RedirectStandardError  "$LOG_DIR\${script}_${yearLabel}_stderr.txt" `
        -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -ne 0) {
        Log "ERROR: $script (year=$yearLabel) exited with code $($proc.ExitCode). Check stderr log."
        return $false
    }
    Log "OK: $script (year=$yearLabel) completed."
    return $true
}

Log "====== Managed Care Daily Pipeline START ======"
Log "Script dir : $SCRIPT_DIR"
Log "Log file   : $LOG_FILE"

# Force UTF-8 output from all Python scripts (prevents UnicodeEncodeError in Task Scheduler)
$env:PYTHONIOENCODING = 'utf-8'

Set-Location $SCRIPT_DIR

# ── Helper: patch SELECTED_CAMP_YEAR without adding BOM ─────
function Patch-Year($file, $year) {
    $enc     = [System.Text.UTF8Encoding]::new($false)  # UTF-8, NO BOM
    $content = [System.IO.File]::ReadAllText((Resolve-Path $file).Path, $enc)
    $patched = $content -replace 'SELECTED_CAMP_YEAR\s*=\s*"[0-9]+"', "SELECTED_CAMP_YEAR = `"$year`""
    [System.IO.File]::WriteAllText((Resolve-Path $file).Path, $patched, $enc)
}

# ── Script 01: run for 2025, then 2026 ──────────────────────
foreach ($yr in @("2025", "2026")) {
    Patch-Year "01_raw_data_program_allocation.py" $yr
    $ok = Run-Script "01_raw_data_program_allocation.py" $yr
    if (-not $ok) { Patch-Year "01_raw_data_program_allocation.py" "2026"; Log "Pipeline aborted at Script 01 ($yr)"; exit 1 }
}
Patch-Year "01_raw_data_program_allocation.py" "2026"

# ── Script 02: run for 2025, then 2026 ──────────────────────
foreach ($yr in @("2025", "2026")) {
    Patch-Year "02_comparison_retest_analysis.py" $yr
    $ok = Run-Script "02_comparison_retest_analysis.py" $yr
    if (-not $ok) { Patch-Year "02_comparison_retest_analysis.py" "2026"; Log "Pipeline aborted at Script 02 ($yr)"; exit 1 }
}
Patch-Year "02_comparison_retest_analysis.py" "2026"

# ── Script 04: runs once, reads all master CSVs ──────────────
$ok = Run-Script "04_claude_analysis.py" "all"
if (-not $ok) { Log "Pipeline aborted at Script 04"; exit 1 }

# ── VYTAL Appointment Flat Table: Pull latest appointments from Trino ───────
# Queries f_appointmentflattable for all VYTAL enrolled users
# Must run AFTER Script 04 (which generates policy data for filtering)
# Outputs: vytal_appt_flat.csv (used by dashboard Care Operations section)
$ok = Run-Script "vytal_appt_flat_analysis.py" "all"
if (-not $ok) { Log "WARNING: vytal_appt_flat_analysis.py failed. Using last known appointment data. Pipeline continues." }

# ── Script 05: Combined Engagement Effect analysis ──────────────
$ok = Run-Script "05_combined_engagement_effect.py" "all"
if (-not $ok) { Log "WARNING: 05_combined_engagement_effect.py failed. Pipeline continues." }

# ── Engagement Activities: Fetch meal, sleep, steps, weight logs via OAuth ────────
# Queries: meallogs (phr_id), activity_sleep_trackers (hrx_id), activity_steps (hrx_id), weight_progresses (hrx_id/phr_id)
# Requires OAuth2 — uses cached token (~/.trino/token)
# Outputs: activity_meal_logs.csv, activity_sleep_logs.csv, activity_steps_logs.csv, activity_weight_logs.csv
$ok = Run-Script "fetch_engagement_activities.py" "all"
if (-not $ok) { Log "WARNING: fetch_engagement_activities.py failed. Using last known activity logs CSVs. Pipeline continues." }

# ── Map HRX_ID to PHR_ID for Sleep/Steps: Join with weight_progresses bridge ────
# Maps sleep/steps activity data (which use hrx_id) to phr_id via weight_progresses
# Outputs: activity_sleep_logs_with_phr.csv, activity_steps_logs_with_phr.csv
$ok = Run-Script "map_engagement_hrx_to_phr.py" "all"
if (-not $ok) { Log "WARNING: map_engagement_hrx_to_phr.py failed. Using original activity logs without phr_id mapping. Pipeline continues." }

# ── VYTAL Enrollment & Engagement Analysis ────────────────
# Analyzes VYTAL enrolled users (unique, post-June 1 2026 activity only)
# Matches with engagement activities: steps (hrx_id), meals/weight (phr_id), app activity (hrx_id logins/launches)
# Requires: vasu.verma credentials for d_policy query + OAuth2 for activity table queries
# Outputs: managed_care_engagement_activities.csv (summary table for dashboard, unique users only)
$ok = Run-Script "analyze_vytal_engagement_unique.py" "all"
if (-not $ok) { Log "WARNING: analyze_vytal_engagement_unique.py failed. Using last known engagement activities summary. Pipeline continues." }

# ── Daily Engagement Metrics ────────────────
# Generates daily breakdown of engagement metrics (post-June 1, 2026)
# Allows dashboard to filter engagement data by Care Operations date range selector
# Outputs: managed_care_engagement_daily.csv (date | activity_type | unique_users | pct_of_enrolled)
$ok = Run-Script "generate_daily_engagement_metrics.py" "all"
if (-not $ok) { Log "WARNING: generate_daily_engagement_metrics.py failed. Using last known daily engagement metrics. Pipeline continues." }

# ── HRA Fetch: Pull STARTED+COMPLETED HRA from assessment_reports via OAuth ───
# Requires OAuth2 — uses cached token (~/.trino/token). Re-auth if token expired.
# Outputs managed_care_hra_wellness.csv (used by Script 3b for lifestyle scoring)
$ok = Run-Script "fetch_hra_wellness.py" "2026"
if (-not $ok) { Log "WARNING: fetch_hra_wellness.py failed. Using last known HRA CSV. Pipeline continues." }

# ── Script 3b: Device & Lifestyle eligibility for 2026 enrolled users ────────
# Reads policy_data.csv + managed_care_hra_wellness.csv + Trino biomarkers/appts
# Scoring: Clinical(30%) + Engagement(25%) + Adherence(25%) + Lifestyle(20%)
# All 5 conditions: Diabetes/Cholesterol/Liver/Renal/Thyroid from lab LOINC codes
# Outputs managed_care_device_eligibility_2026.csv with allocation ranks (100/type)
$ok = Run-Script "03b_device_eligibility_2026.py" "2026"
if (-not $ok) { Log "WARNING: 03b_device_eligibility_2026.py failed. Pipeline continues." }

# ── Voicebot Appointment Source: Classify VYTAL appts by source ─────
# Uses Mcare campaigns (IDs 234, 236, 240) — intersted=True flag in sms_session meta
# Requires OAuth2 cached token. Runs after vytal_appt_flat_analysis.py
# Outputs: managed_care_appt_source.csv (Voice Bot / Organic per appointment)
$ok = Run-Script "fetch_voicebot_appt_source.py" "all"
if (-not $ok) { Log "WARNING: fetch_voicebot_appt_source.py failed. Using last known appt source CSV. Pipeline continues." }

# ── Script 08: Benefit + Appointment Deep Analysis ──────────────────
# Analyzes all benefits (claims), repeat bookings, appointment follow-ups
# Queries f_claim + f_appointmentflattable for detailed benefit breakdowns
# Outputs: managed_care_benefit_deep.json (used by dashboard for benefit analysis)
$ok = Run-Script "08_benefit_appointment_deep.py" "all"
if (-not $ok) { Log "WARNING: 08_benefit_appointment_deep.py failed. Using last known benefit deep data. Pipeline continues." }

# ── Device delivered 2025: re-run impact analysis against fresh comparison CSV ──
$ok = Run-Script "process_device_delivered_2025.py" "2025"
if (-not $ok) { Log "WARNING: process_device_delivered_2025.py failed. Pipeline continues." }

# ── Restart dashboard server ─────────────────────────────────
Log "Restarting dashboard server on port 8000..."
# Kill any existing python process serving port 8000
$existing = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($existing) {
    $procIds = $existing | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $procIds) {
        try { Stop-Process -Id $procId -Force; Log "Killed PID $procId (was using port 8000)" } catch {}
    }
    Start-Sleep -Seconds 2
}

# Start dashboard server in background
Start-Process -FilePath $PYTHON `
    -ArgumentList "run_dashboard.py" `
    -WorkingDirectory $SCRIPT_DIR `
    -RedirectStandardOutput "$LOG_DIR\dashboard_stdout.txt" `
    -RedirectStandardError  "$LOG_DIR\dashboard_stderr.txt" `
    -NoNewWindow

Log "Dashboard server started: http://localhost:8000/managed_care_dashboard_final.html"
Log "====== Managed Care Daily Pipeline DONE ======"

# Clean up old logs older than 14 days
Get-ChildItem $LOG_DIR -Filter "pipeline_*.log" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } |
    Remove-Item -Force
