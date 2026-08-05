# Quick Start — Managed Care Dashboard on Render

## 🎯 Goal
Daily scripts run locally → Push data to Neon PostgreSQL → Dashboard shows live data

## ⏱️ Total Time: ~30 minutes

---

## Phase 1: Local Setup (15 min)

### 1.1 Initialize Neon Schema (2 min)
```bash
cd "Manage care python"
python init_neon_schema.py
```

**Expected output**:
```
✓ Schema created successfully
✓ Tables created: 4
  - managed_care.programme_allocation
  - managed_care.comparison_retest
  - managed_care.device_eligibility
  - managed_care.dashboard_cache
```

### 1.2 Copy Database Config (1 min)
```bash
cp db_config.example.py db_config.py
# No edits needed - already has Neon connection
```

### 1.3 Update Scripts (10 min)

**For each script (01, 02, 03, 04):**

Find the line with `.to_csv(`:
```python
# OLD
df_filtered_latest.to_csv("Data/program_allocation.csv", index=False)

# NEW
from db_layer import save_dataframe
save_dataframe(df_filtered_latest, "programme_allocation")
```

**Quick find & replace**:
| Script | Find | Replace with |
|--------|------|--------------|
| 01 | `to_csv("Data/program_allocation.csv"` | Import + `save_dataframe(df, "programme_allocation")` |
| 02 | `to_csv` in comparison | `save_dataframe(df, "comparison_retest")` |
| 03 | `to_csv` in device | `save_dataframe(df, "device_eligibility")` |
| 04 | `to_csv` in insights | `save_dataframe(df, "dashboard_cache")` |

**See `LOCAL_SETUP.md` → Step 2.3 for exact code.**

### 1.4 Test Locally (2 min)
```bash
python 01_raw_data_program_allocation.py
```

**Expected output**:
```
✓ Saved 12345 rows to managed_care.programme_allocation
✓ Saved 5678 rows to managed_care.comparison_retest
```

If successful → Continue to Phase 2

---

## Phase 2: Deploy Dashboard to Render (10 min)

### 2.1 Create Web Service (3 min)
1. Go to: https://dashboard.render.com
2. Click **New** → **Web Service**
3. Select repo: `muskanrao813-blip/managed-care`
4. Name: `managed-care-dashboard`
5. Runtime: **Docker**
6. Click **Create Web Service**

### 2.2 Set Database URL (2 min)
1. Service Dashboard → **Environment**
2. Click **Add Environment Variable**
3. Key: `DATABASE_URL`
4. Value: 
```
postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require
```
5. Click **Save**

Render redeploys (~3 min). Wait for status: **Live** ✅

### 2.3 Get Public URL (1 min)
Once deployed, Render shows:
```
https://managed-care-dashboard-xxxx.onrender.com
```

**Test it**: Open URL in browser → Should load dashboard

---

## Phase 3: Schedule Daily Runs (5 min)

### 3.1 Create PowerShell Script
Save as: `C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python\run_all_scripts.ps1`

```powershell
# Set Neon connection
$env:DATABASE_URL = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

# Change directory
cd "C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python"

Write-Host "[$(Get-Date)] Starting managed care scripts..."

# Run each script
python 01_raw_data_program_allocation.py
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR in script 01"; exit 1 }

python 02_comparison_retest_analysis.py
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR in script 02"; exit 1 }

python "03b_device_eligibility_2026.py"
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR in script 03"; exit 1 }

python 04_claude_analysis.py
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR in script 04"; exit 1 }

Write-Host "[$(Get-Date)] ✓ All scripts completed"
```

### 3.2 Create Task Scheduler Job
1. Open **Task Scheduler**
2. Right-click **Task Scheduler Library** → **Create Task**
3. **General** tab:
   - Name: `ManagedCareDaily`
   - ☑ Run with highest privileges
4. **Triggers** tab:
   - New trigger → Daily at 6:00 AM
5. **Actions** tab:
   - Program: `powershell.exe`
   - Arguments: `-ExecutionPolicy Bypass -File "C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python\run_all_scripts.ps1"`
6. Click **OK**

### 3.3 Test the Job
1. Task Scheduler → Right-click job → **Run**
2. Watch output
3. Check Render dashboard updates within 10 seconds

---

## ✅ Done!

### What Happens Now
- **6:00 AM Daily**: Task Scheduler runs all scripts
- **Scripts**: Read Trino (OAuth) → Process → Push to Neon
- **Dashboard**: Auto-refreshes with latest data
- **Everyone**: Sees live dashboard at public URL

### URLs & Credentials
- **Dashboard**: https://managed-care-dashboard-xxxx.onrender.com
- **Neon Database**: Already pre-configured (no manual connection needed)
- **GitHub Repo**: https://github.com/muskanrao813-blip/managed-care.git

### Troubleshooting
- Scripts not running? Check Task Scheduler logs
- Dashboard not updating? Check Render logs
- Database errors? Run `python init_neon_schema.py` again
- Need help? See `LOCAL_SETUP.md` or `POSTGRESQL_SETUP.md`

---

## Next: Share with Stakeholders

Once tested and working:
```
📊 Live Managed Care Dashboard
https://managed-care-dashboard-xxxx.onrender.com

Updated daily at 6:00 AM with fresh data.
```

**🎉 Done!**
