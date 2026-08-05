#!/usr/bin/env python3
"""Quick test: Does save_dataframe actually work?"""

import os
import pandas as pd
from db_layer import save_dataframe, read_table

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

print("Testing database write & read...\n")

# Create test data
test_df = pd.DataFrame({
    "id": [1, 2, 3],
    "name": ["Alice", "Bob", "Charlie"],
    "score": [95.5, 87.2, 92.1]
})

print(f"[1] Test data:\n{test_df}\n")

# Try to save
try:
    print("[2] Calling save_dataframe()...")
    save_dataframe(test_df, "test_table", if_exists="replace")
    print("[OK] save_dataframe succeeded\n")
except Exception as e:
    print(f"[ERROR] save_dataframe failed: {e}\n")
    exit(1)

# Try to read back
try:
    print("[3] Calling read_table()...")
    result_df = read_table("test_table")
    print(f"[OK] read_table returned {len(result_df)} rows\n")
    print(f"Data:\n{result_df}\n")
except Exception as e:
    print(f"[ERROR] read_table failed: {e}\n")
    exit(1)

print("[SUCCESS] Database connection working!")
