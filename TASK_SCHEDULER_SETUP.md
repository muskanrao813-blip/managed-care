# Task Scheduler Setup — Daily Managed Care Pipeline

## Overview

This sets up automatic daily runs of all 4 scripts at 6:00 AM, pushing fresh data to Neon PostgreSQL.

**Result**: Dashboard at https://managed-care-dashboard.onrender.com/ auto-updates every morning.

---

## Step-by-Step Setup (5 minutes)

### Step 1: Open Task Scheduler

- Press **Windows Key + R**
- Type: `taskschd.msc`
- Press **Enter**

### Step 2: Create New Task

In Task Scheduler window:
1. Right-click **Task Scheduler Library** (left panel)
2. Select **Create Task...**

### Step 3: General Tab

Fill in:
- **Name**: `ManagedCareDaily`
- **Description**: `Run Managed Care scripts daily at 6 AM`
- Check: ☑ **Run with highest privileges**
- Check: ☑ **Run whether user is logged in or not**

Click **OK** (will come back to configure more)

### Step 4: Triggers Tab

1. Click **New...**
2. Configure trigger:
   - **Begin the task**: On a schedule
   - **Daily**
   - **Start**: 6:00:00 AM
   - **Repeat every**: 1 day
   - **Duration**: Indefinitely
3. Click **OK**

### Step 5: Actions Tab

1. Click **New...**
2. Configure action:
   - **Action**: Start a program
   - **Program/script**: `C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python\run_daily.bat`
   - **Start in**: `C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python`
3. Click **OK**

### Step 6: Conditions Tab

Recommended settings:
- Uncheck: ☐ Start the task only if the computer is on AC power
- This allows runs even on battery

### Step 7: Settings Tab

Keep defaults:
- ☑ Allow task to be run on demand
- ☑ If the task is already running, do not start a new instance
- ☑ Stop the task if it runs longer than: 1 hour

### Step 8: Save

1. Click **OK** at bottom
2. Enter Windows password (required for "Run with highest privileges")
3. Task created!

---

## Testing (2 minutes)

### Test the job:

1. In Task Scheduler, find **ManagedCareDaily**
2. Right-click → **Run**
3. Wait 3-5 minutes for scripts to complete
4. Check log file: `C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python\logs\daily_run_YYYY-MM-DD.log`
5. Go to dashboard: https://managed-care-dashboard.onrender.com/
6. **Refresh browser** → See data appearing!

### Verify data was pushed:

- Programme allocation table should show rows
- Comparison/retest data should appear
- Device eligibility populated
- Dashboard KPIs update with real numbers

---

## Daily Operation

**Every day at 6:00 AM**:
1. Windows Task Scheduler runs `run_daily.bat`
2. PowerShell executes all 4 scripts
3. Scripts connect to Neon PostgreSQL (DATABASE_URL env var)
4. Data saved to `managed_care.` tables
5. Render dashboard reads from Neon
6. Public URL shows fresh data

**Logs saved**: `C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python\logs\`

---

## Monitoring

### Check last run:
1. Task Scheduler → Right-click **ManagedCareDaily** → **Properties**
2. **History** tab shows last execution time & result

### View logs:
```
C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python\logs\daily_run_YYYY-MM-DD.log
```

### Check Render dashboard:
- https://managed-care-dashboard.onrender.com/
- Should show updated data after 6 AM

---

## Troubleshooting

**Task didn't run at 6 AM?**
- Check Windows Task Scheduler History tab for errors
- Verify computer was powered on at 6 AM
- Check file permissions on `run_daily.bat`

**Scripts failed?**
- Check log file for specific error
- Verify Trino OAuth credentials (scripts will handle them)
- Verify Neon PostgreSQL connection string in `db_config.py`

**Data not on dashboard?**
- Check log file: `[$(Get-Date)] SUCCESS` message?
- Refresh Render dashboard in browser
- Wait 10 seconds for dashboard to read from Neon

---

## Summary

✅ 6:00 AM daily: Automatic script execution  
✅ All data → Neon PostgreSQL (managed_care schema)  
✅ Dashboard reads live data  
✅ Zero manual intervention  
✅ Recommendations based on fresh daily data  

**Done!** 🎉
