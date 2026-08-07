"""
Update Pipeline Status Metadata
Called at start and end of daily pipeline to track execution times
Usage: python update_pipeline_status.py start|end
"""
import sys
import os
import pandas as pd
from datetime import datetime
from db_layer import save_dataframe, read_table

if len(sys.argv) < 2:
    print("Usage: python update_pipeline_status.py start|end")
    sys.exit(1)

status = sys.argv[1].lower()
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

print(f"[PIPELINE] {status.upper()} — {now}")

# Create or update status table
df_status = pd.DataFrame([{
    "event": status,
    "timestamp": now,
    "pipeline_date": datetime.now().strftime("%Y-%m-%d")
}])

save_dataframe(df_status, "pipeline_status", if_exists="append")
print(f"[OK] Pipeline status saved to Neon")
