#!/usr/bin/env python3
"""Populate Neon with existing CSV data"""

import os
import pandas as pd
from pathlib import Path
from db_layer import save_dataframe

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

data_dir = Path(__file__).parent / "Data"

csv_mappings = {
    "programme_allocation": "managed_care_program_allocation.csv",
    "comparison_retest": "managed_care_comparison.csv",
    "device_eligibility": "managed_care_device_eligibility_2026.csv",
}

print("=" * 70)
print("Populating Neon from local CSV files")
print("=" * 70)

for table_name, csv_file in csv_mappings.items():
    csv_path = data_dir / csv_file

    if csv_path.exists():
        print(f"\n[1] Reading {csv_file}...")
        df = pd.read_csv(csv_path, low_memory=False)
        print(f"    {len(df):,} rows, {len(df.columns)} columns")

        print(f"[2] Saving to {table_name}...")
        try:
            save_dataframe(df, table_name, if_exists="replace")
            print(f"    [OK] Saved {len(df):,} rows")
        except Exception as e:
            print(f"    [ERROR] {e}")
    else:
        print(f"\n[SKIP] {csv_file} not found")

print("\n" + "=" * 70)
print("Done! Check dashboard now: https://managed-care-dashboard.onrender.com/")
print("=" * 70)
