# Dashboard Setup on Render (Neon PostgreSQL)

## Overview

**Architecture**:
- ✅ Neon PostgreSQL (shared with Dietician QA project)
- ✅ `managed_care` schema (separate from QA data)
- ✅ Flask dashboard server (reads from schema, serves UI)
- ✅ Public URL (anyone can access live dashboard)
- ✅ Data always fresh (scripts push updates daily)

## Architecture

```
Your Machine (Local - Task Scheduler)
  → Scripts 01-04 run with your auth
  → Process data
  → Push to Neon PostgreSQL (managed_care schema)
           ↓
Neon PostgreSQL (shared database)
  └─ neondb/managed_care schema ← Managed Care data
  └─ neondb/public schema ← Dietician QA data
           ↓
Render Flask Dashboard (reads managed_care schema)
           ↓
Browser: https://managed-care-dashboard-xxxx.onrender.com
```

**For local setup**: See `LOCAL_SETUP.md`

## ✅ Database Already Ready

The Neon PostgreSQL connection is already configured:
- Database: `neondb` (shared with Dietician QA)
- Schema: `managed_care` (separate, isolated)
- Connection: Pre-configured in `db_layer.py` and `db_config.py`

**No database creation needed.**

## Step 1: Deploy Dashboard to Render (5 min)

### 1.1 Create Web Service
1. Go to: https://dashboard.render.com
2. Click **New** → **Web Service**
3. Connect your `managed-care` GitHub repo
4. Name: `managed-care-dashboard`
5. Runtime: **Docker**
6. Click **Create Web Service**

### 1.2 Set Environment Variable
1. Service Dashboard → **Environment**
2. Add variable:
   ```
   DATABASE_URL = postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require
   ```
3. Click **Save** → Render redeploys (~3 min)

### 1.3 Get Public Dashboard URL
Once deployed:
- Render shows: `https://managed-care-dashboard-xxxx.onrender.com`
- **This is your public dashboard**
- Share this URL with stakeholders

## Step 2: Setup Local Scripts

See `LOCAL_SETUP.md` for:
- Initialize `managed_care` schema (one-time)
- Copy `db_config.py`
- Update scripts 01-04 to push data
- Set up Task Scheduler

## Verification

### Test Data Push
1. Run scripts locally (see `LOCAL_SETUP.md`)
2. Scripts output: `✓ Saved X rows to managed_care.table`
3. Dashboard auto-refreshes within 10 seconds

### Monitor Data
```bash
# Connect to Neon PostgreSQL
psql "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

# View managed_care schema tables
\dt managed_care.*

# Check data
SELECT COUNT(*) FROM managed_care.programme_allocation;
```

## Troubleshooting

**Dashboard shows "Error connecting"**
- Verify DATABASE_URL in Render environment is correct
- Check Neon PostgreSQL is running
- Test locally: `psql $DATABASE_URL`

**Data not appearing**
- Check local scripts ran (look for "✓ Saved" output)
- Verify schema initialized: Run `python init_neon_schema.py` locally
- Check Render Flask logs for errors

**Schema doesn't exist**
- Run `python init_neon_schema.py` once (creates managed_care schema)
- This should be done before running scripts

## Next Steps

1. ✅ Deploy dashboard to Render (Step 1 above)
2. → Initialize managed_care schema locally (Step 0 in `LOCAL_SETUP.md`)
3. → Setup local scripts (see `LOCAL_SETUP.md`)
4. → Schedule daily Task Scheduler job
5. → Share public dashboard URL

