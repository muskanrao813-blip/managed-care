# PostgreSQL Setup for Managed Care Dashboard

## Overview

Your dashboard now reads from **PostgreSQL** instead of CSVs:
- ✅ Daily scripts push data automatically
- ✅ Dashboard always shows fresh data
- ✅ No manual CSV management
- ✅ Persistent storage on Render

## Architecture

```
Your Machine (Task Scheduler)
  → Scripts 01-04 run daily
  → Push data to PostgreSQL on Render
           ↓
Render PostgreSQL (central database)
           ↓
Render Dashboard Server (Flask)
           ↓
Browser (live dashboard with fresh data)
```

## Step 1: Create PostgreSQL on Render (2 min)

### 1.1 Go to Render Dashboard
- https://dashboard.render.com

### 1.2 Create PostgreSQL Database
1. Click **New** → **PostgreSQL**
2. Name: `managed-care-db`
3. Database: `managed_care`
4. Region: Singapore
5. Pricing: **Free** (optional, limited storage)
6. Click **Create Database**

### 1.3 Get Connection String
Once created:
1. Dashboard shows: **Internal Database URL** and **External Database URL**
2. Copy the **External Database URL** (format: `postgresql://user:pass@host:5432/db`)

Example:
```
postgresql://myuser:mypass@oregon-postgres.render.com:5432/managed_care
```

## Step 2: Deploy Dashboard to Render (5 min)

### 2.1 Create Web Service
1. Render Dashboard → **New** → **Web Service**
2. Connect your `managed-care` GitHub repo
3. Name: `managed-care-dashboard`
4. Runtime: **Docker**
5. Click **Create Web Service**

### 2.2 Add Database URL to Environment
1. Service Dashboard → **Environment**
2. Add variable:
   ```
   DATABASE_URL = postgresql://user:pass@host:5432/managed_care
   ```
   (Paste the External Database URL from Step 1.3)

3. Add Trino credentials:
   ```
   TRINO_HOST=your-trino-host
   TRINO_PORT=443
   TRINO_USERNAME=your-username
   TRINO_PASSWORD=your-password
   TRINO_CATALOG=iceberg
   TRINO_SCHEMA=managed_care
   ```

4. Click **Save** → Render redeploys (~3 min)

### 2.3 Get Public Dashboard URL
Once deployed:
- Service shows: `https://managed-care-dashboard-xxxx.onrender.com`
- This is your public dashboard URL

## Step 3: Update Local Scripts to Use PostgreSQL (10 min)

### 3.1 Copy Database Config
```bash
cp db_config.example.py db_config.py
```

### 3.2 Set Database URL
Edit `db_config.py`:
```python
DATABASE_URL = "postgresql://user:pass@host:5432/managed_care"
# (Same as the one you set in Render)
```

Or use environment variable:
```bash
export DATABASE_URL="postgresql://user:pass@host:5432/managed_care"
```

### 3.3 Update Script 01 (Example)
In `01_raw_data_program_allocation.py`, replace:
```python
# OLD: df.to_csv("Data/program_allocation.csv", index=False)

# NEW:
from db_layer import save_dataframe
save_dataframe(df, "programme_allocation")
```

Do the same for scripts 02, 03, 04 (replace `to_csv()` with `save_dataframe()`).

### 3.4 Test Locally
```bash
python 01_raw_data_program_allocation.py
# Should show: "✓ Saved X rows to programme_allocation"
```

## Step 4: Schedule Daily Runs (5 min)

Your scripts now write to Render PostgreSQL instead of local CSVs.

**Task Scheduler** (Windows):
1. Open Task Scheduler
2. Create task: `ManagedCareDaily` 
3. Trigger: Daily at 6 AM
4. Action: `python C:\path\to\01_raw_data_program_allocation.py` (and 02, 03, 04)
5. Set environment: `DATABASE_URL=postgresql://...`

**Cron** (Linux/Mac):
```bash
# Run scripts daily at 6 AM
0 6 * * * cd /path && python 01_raw_data_program_allocation.py && python 02_comparison_retest_analysis.py && python 03b_device_eligibility_2026.py && python 04_claude_analysis.py
```

## Step 5: Verify Live Dashboard

### 5.1 Access Dashboard
- URL: `https://managed-care-dashboard-xxxx.onrender.com`
- Should load instantly (no "Loading CSV data" message)
- Click "↻ Reload Data" to refresh from latest database

### 5.2 Check Data Flow
1. Run scripts locally (manually for testing)
2. Dashboard updates within 10 seconds
3. Repeat daily automatically via Task Scheduler

## Troubleshooting

### Dashboard shows "Error connecting"
- Check PostgreSQL connection string in Render environment
- Verify DATABASE_URL format: `postgresql://user:pass@host:5432/db`
- Test connection locally: `psql <DATABASE_URL>`

### Scripts fail with "database not found"
- Verify DATABASE_URL environment variable is set
- Check PostgreSQL is online: `pg_isready -h host`
- Check network access (Render PostgreSQL must be accessible from your machine)

### Data not updating
- Check Task Scheduler is running scripts
- Verify scripts output: "✓ Saved X rows to table"
- Check Render logs for Flask errors

### Dashboard still shows old data
- Click "↻ Reload Data" to refresh browser cache
- Verify scripts ran: Check Render PostgreSQL `updated_at` timestamp

## Going Further

**Backup Data**:
```bash
# Backup from Render PostgreSQL
pg_dump <DATABASE_URL> > backup.sql

# Restore
psql <DATABASE_URL> < backup.sql
```

**Monitor Database**:
```bash
# Connect to Render PostgreSQL
psql <DATABASE_URL>

# View tables
\dt

# Check data
SELECT COUNT(*) FROM programme_allocation;
```

**Upgrade Storage** (if needed):
- Render Free: 100MB
- Render Starter: 1GB+ ($7/month)

