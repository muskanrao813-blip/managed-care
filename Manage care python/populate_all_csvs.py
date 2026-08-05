#!/usr/bin/env python3
"""Populate Neon with ALL local CSV files for complete dashboard"""

import os
import pandas as pd
from pathlib import Path
from db_layer import save_dataframe

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

# CSV file to table name mapping
csv_mappings = {
    "managed_care_program_allocation.csv": "programme_allocation",
    "managed_care_comparison.csv": "comparison_retest",
    "managed_care_device_eligibility_2026.csv": "device_eligibility",
    "managed_care_policy_data.csv": "policy_data",
    "vytal_appt_flat.csv": "vytal_appointments",
    "managed_care_appt_utilization.csv": "appointment_utilization",
    "managed_care_camp_monthly.csv": "camp_monthly",
    "managed_care_engagement_activities.csv": "engagement_activities",
    "managed_care_engagement_daily.csv": "engagement_daily",
    "managed_care_engagement_effect.csv": "engagement_effect",
    "managed_care_hra_stats.csv": "hra_stats",
    "managed_care_benefit_assignments_2026.csv": "benefit_assignments",
    "managed_care_appt_source.csv": "appointment_source",
    "managed_care_device_delivered_2025.csv": "device_delivered",
    "managed_care_device_impact_2025.csv": "device_impact",
    "managed_care_impact_scores.csv": "impact_scores",
}

# Find CSV folder (could be Data/ or data/)
data_dirs = [
    Path(__file__).parent / "Data",
    Path(__file__).parent / "data",
    Path("D:/OneDrive - Bajaj Finserv Health Limited/Documents/manage care/Manage care python/data"),
]

csv_folder = None
for d in data_dirs:
    if d.exists():
        csv_folder = d
        break

if not csv_folder:
    print("ERROR: Could not find Data folder")
    exit(1)

print("=" * 70)
print(f"Populating Neon from {csv_folder}")
print("=" * 70)

total_rows = 0
for csv_file, table_name in csv_mappings.items():
    csv_path = csv_folder / csv_file

    if csv_path.exists():
        print(f"\n[1] Reading {csv_file}...")
        df = pd.read_csv(csv_path, low_memory=False)
        print(f"    {len(df):,} rows, {len(df.columns)} columns")

        print(f"[2] Saving to {table_name}...")
        try:
            save_dataframe(df, table_name, if_exists="replace")
            total_rows += len(df)
            print(f"    [OK] Saved {len(df):,} rows")
        except Exception as e:
            print(f"    [ERROR] {e}")
    else:
        print(f"\n[SKIP] {csv_file} not found")

print("\n" + "=" * 70)
print(f"Complete! Loaded {total_rows:,} total rows")
print("=" * 70)
print("\nDashboard sections that will now display:")
print("  - Overview (all KPIs)")
print("  - Programme Outcomes (improvement rates)")
print("  - Cohort Analysis (risk stratification)")
print("  - Devices & Lifestyle (device allocation)")
print("  - Appointments (utilization, booking sources)")
print("  - Engagement Activities (engagement data)")
print("  - YoY Comparison (historical trends)")
print("  - Recommendations (AI recommendations)")
