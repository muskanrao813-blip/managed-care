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
    "01_raw_data_program_allocation.py",
    "02_comparison_retest_analysis.py",
    "03b_device_eligibility_2026.py",
    "04_claude_analysis.py"
]

print(f"[{datetime.now()}] Starting Managed Care pipeline...")
print(f"[{datetime.now()}] Database: Neon PostgreSQL (managed_care schema)\n")

failed = False
for i, script in enumerate(scripts, 1):
    print(f"[{datetime.now()}] Running Script {i}: {script}")
    result = subprocess.run([sys.executable, script], capture_output=True, text=True)

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
    print(f"\n[{datetime.now()}] SUCCESS - All scripts completed")
    print(f"[{datetime.now()}] Data pushed to Neon PostgreSQL")
    print(f"[{datetime.now()}] Dashboard will update within 10 seconds")
    print(f"[{datetime.now()}] Visit: https://managed-care-dashboard.onrender.com/")
    sys.exit(0)
else:
    print(f"\n[{datetime.now()}] FAILED - Check error above")
    sys.exit(1)
