# Local Setup — Daily Scripts + Neon PostgreSQL

## Overview

Your scripts run **100% locally** on Task Scheduler with all your auth:
1. Scripts 01-04 run daily at 6 AM
2. Read from Trino (your OAuth)
3. Process data
4. Push to Neon PostgreSQL (shared with Dietician QA project)
5. Dashboard auto-refreshes to show new data

## Step 0: Initialize Schema (One-time)

Run the schema initialization script to create the `managed_care` schema in Neon:

```bash
cd "Manage care python"
python init_neon_schema.py
```

Output should show:
```
✓ Schema created successfully
✓ Tables created: 4
  - managed_care.programme_allocation
  - managed_care.comparison_retest
  - managed_care.device_eligibility
  - managed_care.dashboard_cache
```

**Done!** Schema is ready. Proceed to Step 1.

## Step 1: No Database Setup Needed

The Neon PostgreSQL connection is already configured in:
- `db_layer.py` — Uses Neon connection by default
- `db_config.py` — Points to Neon database

Just copy it:
```bash
cd "Manage care python"
cp db_config.example.py db_config.py
```

**No changes needed** — it already has the Neon connection string.

## Step 2: Update Scripts to Push Data
For each script (01, 02, 03, 04), replace CSV saving with database writing.

**Example: Script 01**

Before:
```python
df_filtered_latest.to_csv("Data/program_allocation.csv", index=False)
```

After:
```python
from db_layer import save_dataframe
save_dataframe(df_filtered_latest, "programme_allocation")
```

**Do this for all scripts**:
- `01_raw_data_program_allocation.py` → `save_dataframe(df, "programme_allocation")`
- `02_comparison_retest_analysis.py` → `save_dataframe(df, "comparison_retest")`
- `03b_device_eligibility_2026.py` → `save_dataframe(df, "device_eligibility")`
- `04_claude_analysis.py` → `save_dataframe(df_insights, "dashboard_cache")`

### 2.5 Test Locally
```bash
# Make sure DATABASE_URL is set
echo $DATABASE_URL  # Linux/Mac
echo %DATABASE_URL%  # Windows

# Run script 01
python 01_raw_data_program_allocation.py

# Should output:
# ✓ Saved 12345 rows to programme_allocation
# ✓ Saved 5678 rows to comparison_retest
```

If successful, check Render PostgreSQL:
```bash
# Connect to database
psql $DATABASE_URL

# View tables
\dt

# Count rows
SELECT COUNT(*) FROM programme_allocation;
```

## Step 3: Schedule Daily Runs (Windows)

### 3.1 Create Task Scheduler Job

1. Open **Task Scheduler**
2. Right-click **Task Scheduler Library** → **Create Task**
3. **General** tab:
   - Name: `ManagedCareDaily`
   - Run with highest privileges: ☑
4. **Triggers** tab:
   - New trigger → Daily
   - Time: 6:00 AM
   - Repeat every: 1 day
5. **Actions** tab:
   - New action:
   - Program/script: `python.exe`
   - Arguments: `"C:\path\to\Manage care python\run_all_scripts.ps1"`
   - Start in: `C:\path\to\Manage care python`
6. **Conditions** tab: Uncheck "Stop if computer switches to battery"
7. **Settings** tab: Check "Run task as soon as possible if missed"
8. **OK** → Enter your Windows password

### 3.2 Create PowerShell Runner Script

Create `run_all_scripts.ps1`:
```powershell
# Set database URL
$env:DATABASE_URL = "postgresql://myuser:mypass@host:5432/managed_care"

# Change to script directory
cd "C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python"

# Run scripts in order
Write-Host "[6:00 AM] Starting managed care scripts..."
Write-Host ""

Write-Host "Running script 01..."
python 01_raw_data_program_allocation.py
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR in script 01"; exit 1 }

Write-Host ""
Write-Host "Running script 02..."
python 02_comparison_retest_analysis.py
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR in script 02"; exit 1 }

Write-Host ""
Write-Host "Running script 03..."
python "03b_device_eligibility_2026.py"
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR in script 03"; exit 1 }

Write-Host ""
Write-Host "Running script 04..."
python 04_claude_analysis.py
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR in script 04"; exit 1 }

Write-Host ""
Write-Host "✓ All scripts completed successfully"
```

Save as: `C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python\run_all_scripts.ps1`

### 3.3 Test the Scheduler
1. Task Scheduler → Right-click task → **Run**
2. Watch for PowerShell window
3. Check script output
4. Verify data in Render PostgreSQL

## Step 4: Deploy Dashboard Frontend (5 min)

See `POSTGRESQL_SETUP.md` → **Step 2** to deploy the dashboard to Render.

The dashboard will:
- Read from Render PostgreSQL
- Show live data after scripts run
- Auto-refresh every 30 seconds

## Data Flow (Daily)

```
6:00 AM (Task Scheduler)
  ↓
run_all_scripts.ps1 (PowerShell)
  ↓
Scripts 01-04 run locally
  - Read Trino (your OAuth)
  - Process data
  - call save_dataframe() → Render PostgreSQL
  ↓
9:00 AM (after scripts finish)
  ↓
Dashboard shows fresh data
  ↓
Users access: https://managed-care-dashboard-xxxx.onrender.com
```

## Troubleshooting

**Script fails: "DATABASE_URL not found"**
- Verify env var is set before running script
- Test: `echo $DATABASE_URL` should print the PostgreSQL URL

**Data not appearing in dashboard**
- Check script output for "✓ Saved" messages
- Query database: `SELECT COUNT(*) FROM programme_allocation;`
- Check Render dashboard logs for Flask errors

**PostgreSQL connection times out**
- Verify URL is correct
- Check Render PostgreSQL is running
- Ping host: `ping oregon-postgres.render.com`

**Task Scheduler didn't run**
- Check Event Viewer for task errors
- Verify Python path is correct
- Try manual run: Right-click task → Run

## Next: Deploy Dashboard

Once local setup is working:
1. Go to `POSTGRESQL_SETUP.md` → Step 2
2. Deploy Flask dashboard to Render
3. Set `DATABASE_URL` in Render environment
4. Share public URL with stakeholders

