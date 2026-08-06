#!/usr/bin/env python3
"""
FAST Managed Care Daily Pipeline (Option A)
1. Run all 8 scripts locally (15-20 min) — save CSVs only
2. Batch upload to Neon (5 min)
3. Git commit + push (5 min)
4. Render auto-deploy
Total: ~25 minutes

This replaces the slow version that wrote to Neon per-script.
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Don't set DATABASE_URL here — scripts save to CSVs only
# DATABASE_URL set only for batch upload at the end

def run_cmd(cmd, desc):
    """Run command and log output"""
    print(f"\n{'='*70}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {desc}")
    print(f"{'='*70}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"[FAIL] {desc} FAILED")
        return False
    print(f"[OK] {desc} SUCCESS")
    return True

def main():
    print("\n" + "="*70)
    print("MANAGED CARE 3.0 — FAST DAILY PIPELINE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    print("\nPhase 1: Run scripts locally (CSVs only, no DB writes)")
    print("Phase 2: Batch upload to Neon")
    print("Phase 3: Git commit + Render deploy")
    print("Expected time: ~25 minutes")
    print()

    start_time = datetime.now()

    # ===============================================
    # PHASE 1: Run 8 scripts locally (CSVs only)
    # ===============================================
    print(f"\n{'='*70}")
    print("PHASE 1: RUNNING 8 SCRIPTS LOCALLY")
    print(f"{'='*70}\n")

    scripts = [
        "01_raw_data_program_allocation.py",
        "02_comparison_retest_analysis.py",
        "03b_device_eligibility_2026.py",
        "04_claude_analysis.py",
        "fetch_hra_wellness.py",
        "05_combined_engagement_effect.py",
        "fetch_voicebot_appt_source.py",
        "process_device_delivered_2025.py",
    ]

    failed = False
    for i, script in enumerate(scripts, 1):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [{i}/8] {script}")
        result = subprocess.run([sys.executable, script], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"  [FAIL] Error in {script}")
            print(result.stderr[-200:] if result.stderr else "")
            failed = True
            break
        else:
            # Show last line of output
            lines = result.stdout.strip().split('\n')
            if lines:
                print(f"  {lines[-1]}")

    if failed:
        print(f"\n[FAIL] Script failed, stopping pipeline")
        sys.exit(1)

    phase1_duration = (datetime.now() - start_time).total_seconds()
    print(f"\n[OK] Phase 1 complete: {phase1_duration:.0f}s ({phase1_duration/60:.1f} min)")

    # ===============================================
    # PHASE 2: Batch upload all CSVs to Neon
    # ===============================================
    print(f"\n{'='*70}")
    print("PHASE 2: BATCH UPLOAD TO NEON")
    print(f"{'='*70}\n")

    os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

    if not run_cmd("python populate_complete_data.py", "Batch upload CSVs to Neon"):
        print("[FAIL] Could not upload to Neon")
        sys.exit(1)

    phase2_duration = (datetime.now() - start_time - phase1_duration).total_seconds()
    print(f"\n[OK] Phase 2 complete: {phase2_duration:.0f}s ({phase2_duration/60:.1f} min)")

    # ===============================================
    # PHASE 3: Generate insights & recommendations
    # ===============================================
    print(f"\n{'='*70}")
    print("PHASE 3: GENERATE INSIGHTS")
    print(f"{'='*70}\n")

    if not run_cmd("python generate_insights.py", "Generate data insights"):
        print("[WARNING] Insights generation failed, continuing...")

    # Optional: Gemini recommendations (if API key set)
    if os.getenv("GEMINI_API_KEY"):
        if not run_cmd("python generate_recommendations_gemini.py", "Generate Gemini recommendations"):
            print("[WARNING] Gemini recommendations failed, continuing...")
    else:
        print("[INFO] GEMINI_API_KEY not set - skipping AI recommendations")

    # ===============================================
    # PHASE 4: Git commit + push
    # ===============================================
    print(f"\n{'='*70}")
    print("PHASE 4: GIT COMMIT + PUSH")
    print(f"{'='*70}\n")

    subprocess.run("git add -A", shell=True)
    subprocess.run(f'git commit -m "Daily MC update — {datetime.now().strftime("%Y-%m-%d %H:%M")}"', shell=True)
    subprocess.run("git push origin main", shell=True)

    # ===============================================
    # COMPLETE
    # ===============================================
    total_duration = (datetime.now() - start_time).total_seconds()

    print("\n" + "="*70)
    print(f"[OK] COMPLETE — {datetime.now().strftime('%H:%M:%S')}")
    print(f"[OK] Total time: {total_duration/60:.1f} minutes")
    print(f"[OK] Dashboard: https://managed-care-dashboard.onrender.com/")
    print("="*70 + "\n")

    sys.exit(0)

if __name__ == "__main__":
    main()
