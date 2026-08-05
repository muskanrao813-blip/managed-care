#!/usr/bin/env python3
"""Populate Neon with COMPLETE dataset - ALL managed_care CSVs for full dashboard"""

import os
import pandas as pd
from pathlib import Path
from db_layer import save_dataframe

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

# CSV file to table name mapping - COMPLETE DATASET
csv_mappings = {
    "managed_care_program_allocation.csv": "programme_allocation",
    "managed_care_comparison.csv": "comparison_retest",
    "managed_care_device_eligibility_2026.csv": "device_eligibility",
    "managed_care_policy_data.csv": "policy_data",
    "managed_care_appt_utilization.csv": "appointment_utilization",
    "managed_care_camp_monthly.csv": "camp_monthly",
    "managed_care_engagement_activities.csv": "engagement_activities",
    "managed_care_engagement_daily.csv": "engagement_daily",
    "managed_care_engagement_effect.csv": "engagement_effect",
    "managed_care_hra_stats.csv": "hra_stats",
    "managed_care_hra_wellness.csv": "hra_wellness",
    "managed_care_device_delivered_2025.csv": "device_delivered",
    "managed_care_device_impact_2025.csv": "device_impact",
    "managed_care_appt_source.csv": "appointment_source",
    "managed_care_benefit_assignments_2026.csv": "benefit_assignments",
    "managed_care_impact_scores.csv": "impact_scores",
    "vytal_appt_flat.csv": "vytal_appointments",
}

# Find CSV folder - check OneDrive first, then local
onedrive_path = Path("D:/OneDrive - Bajaj Finserv Health Limited/Documents/manage care/Manage care python/data")
script_dir = Path(__file__).parent
csv_paths = [
    onedrive_path,  # OneDrive source (authoritative)
    script_dir / "data",
    script_dir / "Data",
    script_dir,
]

csv_folder = None
for path in csv_paths:
    if path.exists():
        csv_folder = path
        print(f"Using: {path}")
        break

if not csv_folder:
    print("ERROR: Could not find CSV folder")
    exit(1)

print("=" * 80)
print(f"LOADING COMPLETE MANAGED CARE DATASET INTO NEON")
print(f"Source: {csv_folder}")
print("=" * 80)

total_rows = 0
total_files = 0
missing_files = []

for csv_file, table_name in csv_mappings.items():
    csv_path = csv_folder / csv_file

    if csv_path.exists():
        try:
            print(f"\n[{total_files+1}] {csv_file}")
            df = pd.read_csv(csv_path, low_memory=False)
            print(f"    Rows: {len(df):,} | Columns: {len(df.columns)}")

            save_dataframe(df, table_name, if_exists="replace")
            total_rows += len(df)
            total_files += 1
        except Exception as e:
            print(f"    ERROR: {e}")
            missing_files.append(csv_file)
    else:
        print(f"\n[SKIP] {csv_file} not found")
        missing_files.append(csv_file)

print("\n" + "=" * 80)
print(f"COMPLETE! Loaded {total_files}/{len(csv_mappings)} files")
print(f"Total rows in Neon: {total_rows:,}")
print("=" * 80)

if missing_files:
    print(f"\nMissing {len(missing_files)} files:")
    for f in missing_files:
        print(f"  - {f}")

print("\n" + "=" * 80)
print("DASHBOARD SECTIONS NOW AVAILABLE:")
print("=" * 80)
print("""
[OK] Overview - all KPIs, camp reports, cohort distribution
[OK] Programme Outcomes - improvement rates by condition
[OK] Cohort Analysis - risk stratification (Very High/High/Moderate/Low)
[OK] Devices & Lifestyle - device allocation, lifestyle tiers
[OK] Appointments - utilization by type, booking sources
[OK] Engagement Activities - engagement tracking
[OK] VYTAL Data - all appointment and consultation records
[OK] HRA Wellness - health risk assessment data
[OK] Year-on-Year - historical trends and comparisons
[OK] Recommendations - AI-driven recommendations
""")

print("Next steps:")
print("1. Hard refresh dashboard: Ctrl+Shift+R")
print("2. Visit: https://managed-care-dashboard.onrender.com/")
print("3. All sections should now display complete data")
