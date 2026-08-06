#!/usr/bin/env python3
"""
Clean runner for Managed Care scripts
Executes scripts and pushes data to Neon PostgreSQL
No Unicode/encoding issues
"""

import os
import sys
import subprocess
from datetime import datetime

# Set Neon connection
os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

scripts = [
    ("01_raw_data_program_allocation.py", "Program allocation, normalized scores", 900),
    ("02_comparison_retest_analysis.py", "Retest analysis, improvement flags", 1800),
    ("03b_device_eligibility_2026.py", "Device eligibility scoring", 1800),
    ("04_claude_analysis.py", "Analysis and insights", 1200),
    ("fetch_hra_wellness.py", "HRA wellness data (OAuth2)", 1200),
    ("05_combined_engagement_effect.py", "Combined engagement analysis", 1200),
    ("fetch_voicebot_appt_source.py", "Voicebot appointment classification", 1200),
    ("process_device_delivered_2025.py", "Device delivery impact analysis", 1200),
]

print(f"[{datetime.now()}] Starting COMPLETE Managed Care pipeline...")
print(f"[{datetime.now()}] Database: Neon PostgreSQL (managed_care schema)")
print(f"[{datetime.now()}] Running {len(scripts)} scripts for complete data update\n")

failed = False
for i, (script, description, timeout) in enumerate(scripts, 1):
    print(f"[{datetime.now()}] [{i}/{len(scripts)}] {script}")
    print(f"           {description}")

    # Explicitly pass environment so DATABASE_URL is available
    env = os.environ.copy()
    result = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=timeout, env=env, cwd=os.getcwd())

    if result.returncode != 0:
        print(f"[{datetime.now()}] ERROR in Script {i}")
        print(result.stderr)
        failed = True
        break
    else:
        # Show last 5 lines of output
        lines = result.stdout.strip().split('\n')
        for line in lines[-5:]:
            if line.strip():
                print(f"  {line}")

if not failed:
    print(f"\n[{datetime.now()}] ✓ SUCCESS - All {len(scripts)} scripts completed")
    print(f"[{datetime.now()}] ✓ Complete data updated in Neon PostgreSQL")
    print(f"[{datetime.now()}] ✓ Ready for populate_complete_data.py")
    print(f"[{datetime.now()}] Dashboard: https://managed-care-dashboard.onrender.com/")
    sys.exit(0)
else:
    print(f"\n[{datetime.now()}] ✗ FAILED at script {i} - Check error above")
    print(f"[{datetime.now()}] Partial data may be in Neon")
    sys.exit(1)
