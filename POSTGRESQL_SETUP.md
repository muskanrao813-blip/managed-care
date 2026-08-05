# PostgreSQL & Dashboard Setup (Render)

## Overview

**Backend & Frontend on Render**:
- ✅ PostgreSQL database (receives data from your local scripts)
- ✅ Flask dashboard server (reads from DB, serves UI)
- ✅ Public URL (anyone can access live dashboard)
- ✅ Data always fresh (scripts push updates daily)

## Architecture

```
Your Machine (Local - Task Scheduler)
  → Scripts 01-04 run with your auth
  → Process data
  → Push to Render PostgreSQL
           ↓
Render PostgreSQL (stores pushed data)
           ↓
Render Flask Dashboard (reads & serves UI)
           ↓
Browser: https://managed-care-dashboard-xxxx.onrender.com
```

**For local setup**: See `LOCAL_SETUP.md`

## Step 1: Create PostgreSQL on Render (2 min)

### 1.1 Go to Render Dashboard
- https://dashboard.render.com

### 1.2 Create PostgreSQL Database
1. Click **New** → **PostgreSQL**
2. Name: `managed-care-db`
3. Database: `managed_care`
4. Region: Singapore
5. Pricing: **Free** 
6. Click **Create Database**

### 1.3 Get Connection String
Once created:
1. Dashboard shows connection URLs
2. Copy the **External Database URL**

Example:
```
postgresql://myuser:mypass@oregon-postgres.render.com:5432/managed_care
```

**Save this URL** - you'll need it for:
- Local scripts (db_config.py)
- Render dashboard (environment variable)

## Step 2: Deploy Dashboard to Render (5 min)

### 2.1 Create Web Service
1. Render Dashboard → **New** → **Web Service**
2. Connect your `managed-care` GitHub repo
3. Name: `managed-care-dashboard`
4. Runtime: **Docker**
5. Click **Create Web Service**

### 2.2 Set Database URL
1. Service Dashboard → **Environment**
2. Add variable:
   ```
   DATABASE_URL = postgresql://myuser:mypass@oregon-postgres.render.com:5432/managed_care
   ```
   (Use the URL from Step 1.3)
3. Click **Save** → Render redeploys (~3 min)

### 2.3 Get Public Dashboard URL
Once deployed:
- Render shows: `https://managed-care-dashboard-xxxx.onrender.com`
- **This is your public dashboard**
- Share this URL with stakeholders

## Step 3: Setup Local Scripts

See `LOCAL_SETUP.md` for:
- Configuring `db_config.py` with PostgreSQL URL
- Updating scripts 01-04 to push data
- Setting up Task Scheduler

## Verification

### Test Data Push
1. Run scripts locally (see `LOCAL_SETUP.md`)
2. Scripts output: `✓ Saved X rows to table`
3. Dashboard auto-refreshes within 10 seconds

### Monitor Data
```bash
# Connect to Render PostgreSQL
psql <DATABASE_URL>

# View tables
\dt

# Check data
SELECT COUNT(*) FROM programme_allocation;
```

## Troubleshooting

**Dashboard shows "Error connecting"**
- Verify DATABASE_URL in Render environment is correct
- Check Render PostgreSQL is running
- Test locally: `psql $DATABASE_URL`

**Data not appearing**
- Check local scripts ran (look for "✓ Saved" output)
- Verify DATABASE_URL is same in local `db_config.py` and Render environment
- Check Render Flask logs for errors

**PostgreSQL storage full**
- Render Free: 100MB limit
- Upgrade to Starter: 1GB+ ($7/month)

## Next Steps

1. ✅ Create PostgreSQL on Render (this page, Step 1)
2. ✅ Deploy dashboard to Render (this page, Step 2)
3. → Setup local scripts (see `LOCAL_SETUP.md`)
4. → Schedule daily Task Scheduler job
5. → Share public dashboard URL

