# Render Deployment Guide

## What Gets Deployed

The Managed Care skill scheduler + FastAPI server runs on Render:
- **Skill**: `care_ai_engine/main.py` 
- **Scheduler**: APScheduler runs daily orchestrator job at 9 AM
- **API**: FastAPI webhook server for webhooks/monitoring
- **Database**: Optional PostgreSQL for persistent state

## One-Time Setup (5 min)

### 1. Create Render Account
Go to [render.com](https://render.com), sign up, and connect GitHub.

### 2. Create New Web Service
1. Dashboard → New → Web Service
2. Select repository: `muskanrao813-blip/managed-care`
3. Name: `managed-care-skill`
4. Runtime: Docker
5. Build Command: (leave empty, uses Dockerfile)
6. Start Command: (leave empty, runs CMD from Dockerfile)

### 3. Set Environment Variables
In Render dashboard → Environment:
```
ANTHROPIC_API_KEY=sk-ant-...
TRINO_HOST=your-trino-host
TRINO_PORT=443
TRINO_USERNAME=your-trino-user
TRINO_PASSWORD=your-trino-password
TRINO_CATALOG=iceberg
TRINO_SCHEMA=managed_care
DATABASE_URL=postgresql://user:pass@host/db  (optional)
```

### 4. Deploy
Click "Deploy" → Render builds and starts the service (~3 min)

## Daily Operation

- **9 AM daily**: Scheduler automatically runs orchestrator for all VYTAL patients
- **Logs**: View in Render dashboard → Logs tab
- **Webhooks**: API endpoints available at `https://<your-url>/...` for integrations

## Monitoring

Check Render dashboard for:
- ✅ Service status (should be "Live")
- 📊 Logs: Watch for scheduler runs
- 🔴 Errors: Check if orchestrator jobs fail

## Scaling

Render free tier: 750 hours/month (always-on service)
- Upgrade to Paid if you need guaranteed uptime

## Database (Optional)

If you need persistent state (patient progress, results storage):
1. Render → Create PostgreSQL
2. Set `DATABASE_URL` env var to connection string
3. Service auto-connects

