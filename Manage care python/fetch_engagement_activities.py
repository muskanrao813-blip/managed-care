#!/usr/bin/env python3
"""
Fetch Engagement Activity Data from Trino/Delta Lake
Queries: Sleep, Steps, Weight, Meal logs for VYTAL users (2026)
Exports: CSV files for dashboard integration

Data mapping strategy:
  - Meal logs: has phr_id directly
  - Weight tracker: has phr_id directly
  - Sleep tracker: has hrx_id → JOIN d_policy.hrxid to get phr_id
  - Steps tracker: has hrx_id → JOIN d_policy.hrxid to get phr_id
"""

import sys
import csv
from datetime import datetime
import trino

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 80)
print("FETCHING ENGAGEMENT ACTIVITY DATA FROM TRINO (OAuth2)")
print("=" * 80)

# Connect to Trino with OAuth2
print("\n[Connecting] Trino via OAuth2...")
print("→ A browser window will open for login. Please authenticate.")
print()

try:
    from config import TRINO_HOST
    conn = trino.dbapi.connect(
        host=TRINO_HOST,
        port=443,
        http_scheme='https',
        auth=trino.auth.OAuth2Authentication(),
        verify=True,
    )
    cur = conn.cursor()
    print("✓ Connected successfully!\n")
except Exception as e:
    print(f"✗ Connection failed: {e}")
    sys.exit(1)

# d_policy table location
d_policy_path = 'deltalake.dl_standard_customermart.d_policy'
print(f"[Using] d_policy from: {d_policy_path}")
print(f"  Maps: hrx_id → phr_id for sleep/steps/weight activity tracking\n")

# Define queries for each activity type
# Note: d_policy JOIN may require special permissions; using direct columns when available
# sleep & steps: Include hrx_id for later mapping to phr_id if needed
# weight: Has phr_id directly (and hrx_id)
# meal: Has phr_id directly
queries = {
    'sleep': """
        SELECT hrx_id, etldate as activity_date, count as sleep_minutes, deep, rem, core, awake, createdat
        FROM deltalake.dl_central_activity_tracker.activity_sleep_trackers
        WHERE etldate >= CAST('2026-04-01' AS DATE)
        ORDER BY hrx_id, etldate DESC
    """,
    'steps': """
        SELECT hrx_id, etldate as activity_date, count as step_count, createdat
        FROM deltalake.dl_central_activity_tracker.activity_steps
        WHERE etldate >= CAST('2026-04-01' AS DATE)
        ORDER BY hrx_id, etldate DESC
    """,
    'weight': """
        SELECT phr_id, hrx_id, etldate as activity_date, start_weight, target_weight, height, start as start_time, "end" as end_time, createdat
        FROM deltalake.dl_central_activity_tracker.weight_progresses
        WHERE etldate >= CAST('2026-04-01' AS DATE)
        ORDER BY phr_id, etldate DESC
    """,
    'meal': """
        SELECT phr_id, date as activity_date, break_fast, mid_morning, lunch, tea_time, dinner, post_dinner, created_at
        FROM deltalake.dl_central_phrservice.meallogs
        WHERE SUBSTR(date, 1, 7) >= '2026-04'
        ORDER BY phr_id, date DESC
    """
}

# Fetch data for each activity type
results = {}
for activity_type, query in queries.items():
    print(f"[Querying] {activity_type.upper()} data...")
    try:
        cur.execute(query)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        results[activity_type] = {'columns': cols, 'rows': rows}
        print(f"  ✓ Retrieved {len(rows):,} records")

        if len(rows) > 0:
            print(f"    Sample: {rows[0]}")
    except Exception as e:
        print(f"  ✗ Query failed: {e}")
        print(f"    → This table may not exist or query needs adjustment")
        results[activity_type] = {'columns': [], 'rows': []}

print()

# Export to CSV files
print("=" * 80)
print("EXPORTING TO CSV")
print("=" * 80)

for activity_type, data in results.items():
    filename = f"Data/activity_{activity_type}_logs.csv"
    cols = data['columns']
    rows = data['rows']

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            if rows:
                writer = csv.writer(f)
                writer.writerow(cols)
                writer.writerows(rows)
                print(f"\n✓ {activity_type.upper()}: {len(rows):,} records → {filename}")
            else:
                print(f"\n⚠ {activity_type.upper()}: No data found (table may not exist or empty for 2026-04+)")
    except Exception as e:
        print(f"\n✗ {activity_type.upper()}: Export failed - {e}")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)

total_records = sum(len(data['rows']) for data in results.values())
print(f"\nTotal records fetched: {total_records:,}")
print("\nFiles created:")
for activity_type, data in results.items():
    if len(data['rows']) > 0:
        print(f"  ✓ activity_{activity_type}_logs.csv ({len(data['rows']):,} records)")
    else:
        print(f"  ⚠ activity_{activity_type}_logs.csv (empty or table not found)")

print("\n[Next Step]")
print("  1. Check Data/ folder for CSV files")
print("  2. If tables don't exist, verify Delta Lake table names and availability")
print("  3. Dashboard will auto-load these files on next reload")

conn.close()
print("\nDone.\n")
