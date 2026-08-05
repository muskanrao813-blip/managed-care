#!/usr/bin/env python3
"""
Claude CLI wrapper for daily Managed Care pipeline
Run via: claude --tool python -c "exec(open('cli_daily_runner.py').read())"

Or setup alias in ~/.bashrc or PowerShell:
  alias claude-mc-daily="python C:\path\to\cli_daily_runner.py"
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path("D:/OneDrive - Bajaj Finserv Health Limited/Documents/manage care/Manage care python")
REPO_DIR = Path("C:/Users/muskan.rao/Documents/managed-care-platform")

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

def run_cmd(cmd, desc):
    """Run command and log output"""
    print(f"\n{'='*70}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {desc}")
    print(f"{'='*70}")
    result = subprocess.run(cmd, shell=True, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print(f"✗ {desc} FAILED")
        return False
    print(f"✓ {desc} SUCCESS")
    return True

def main():
    print("\n" + "="*70)
    print("MANAGED CARE 3.0 — DAILY PIPELINE (Claude CLI)")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    os.chdir(SCRIPT_DIR)

    # Step 1: Run scripts
    if not run_cmd("python run_scripts_clean.py", "Step 1: Run scripts 01-04"):
        sys.exit(1)

    # Step 2: Populate Neon
    if not run_cmd("python populate_complete_data.py", "Step 2: Load data to Neon"):
        print("⚠ Warning: Data population failed, continuing...")

    # Step 3: Generate insights
    if not run_cmd("python generate_insights.py", "Step 3: Generate insights"):
        print("⚠ Warning: Insights generation failed, continuing...")

    # Step 3b: Generate Claude recommendations (if API key available)
    if os.getenv("ANTHROPIC_API_KEY"):
        if not run_cmd("python generate_recommendations_claude.py", "Step 3b: Generate Claude recommendations"):
            print("⚠ Warning: Claude recommendations failed, continuing...")
    else:
        print("ⓘ Skipping Claude recommendations (ANTHROPIC_API_KEY not set)")

    # Step 4: Git commit
    os.chdir(REPO_DIR)
    print(f"\n{'='*70}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Step 4: Git commit + push")
    print(f"{'='*70}")

    subprocess.run("git add -A", shell=True)
    subprocess.run(f'git commit -m "Daily MC update — {datetime.now().strftime("%Y-%m-%d %H:%M")}"', shell=True)
    subprocess.run("git push origin main", shell=True)

    print("\n" + "="*70)
    print(f"✓ COMPLETE — {datetime.now().strftime('%H:%M:%S')}")
    print("✓ Dashboard: https://managed-care-dashboard.onrender.com/")
    print("="*70)

if __name__ == "__main__":
    main()
