#!/bin/bash
# Claude CLI wrapper for daily Managed Care pipeline
# Usage: claude-daily
# Or: ./claude-daily.sh

cd "D:/OneDrive - Bajaj Finserv Health Limited/Documents/manage care/Manage care python"

echo "=================================="
echo "Managed Care Daily Pipeline"
echo "Started: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=================================="

export DATABASE_URL="postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

echo ""
echo "[1] Running scripts 01-04..."
python run_scripts_clean.py || echo "⚠ Scripts failed"

echo ""
echo "[2] Loading data to Neon..."
python populate_complete_data.py || echo "⚠ Data load failed"

echo ""
echo "[3] Generating insights..."
python generate_insights.py || echo "⚠ Insights failed"

echo ""
echo "[4] Committing to GitHub..."
cd "C:/Users/muskan.rao/Documents/managed-care-platform"
git add -A
git commit -m "Daily MC update — $(date '+%Y-%m-%d %H:%M')"
git push origin main

echo ""
echo "✓ Complete!"
echo "Dashboard: https://managed-care-dashboard.onrender.com/"
