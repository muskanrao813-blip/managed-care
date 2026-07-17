#!/usr/bin/env python3
"""
Generate Daily Engagement Metrics for VYTAL Users (Post-June 1, 2026)
Creates a CSV with daily breakdown: date | activity_type | unique_users | % of enrolled

This allows dashboard to filter by Care Operations date range and show engagement for selected period.
"""
import sys
import csv
import trino
from datetime import datetime, timedelta
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 100)
print("DAILY ENGAGEMENT METRICS GENERATION FOR VYTAL USERS")
print("=" * 100)

VYTAL_START = '2026-06-01'
VYTAL_END = '2026-12-31'

# Load VYTAL enrolled users
print("\n[Step 1] Loading VYTAL enrolled users...")
vytal_phrs = set()
try:
    with open('Data/managed_care_policy_data.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mc_code = (row.get('mc_product_code') or '').strip()
            phr_id = (row.get('phr_id') or '').strip()
            if mc_code.startswith('VYTAL') and phr_id:
                vytal_phrs.add(phr_id)

    enrolled_count = len(vytal_phrs)
    print(f"OK: {enrolled_count:,} VYTAL enrolled users\n")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

# Get hrx_id mapping
print("[Step 2] Mapping PHR to HRX IDs...")
phr_to_hrx = {}
try:
    from config import TRINO_HOST, TRINO_USER, TRINO_PASSWORD
    conn = trino.dbapi.connect(
        host=TRINO_HOST,
        port=443,
        http_scheme='https',
        user=TRINO_USER,
        auth=trino.auth.BasicAuthentication(TRINO_USER, TRINO_PASSWORD),
        verify=False,
    )
    cur = conn.cursor()

    phr_list = list(vytal_phrs)
    for batch_idx in range(0, len(phr_list), 5000):
        batch = phr_list[batch_idx:batch_idx + 5000]
        phr_str = "','".join(batch)
        query = f"""
        SELECT DISTINCT masterphrid, hrxid
        FROM deltalake.dl_standard_customermart.d_policy
        WHERE masterphrid IN ('{phr_str}')
          AND hrxid IS NOT NULL
        """
        cur.execute(query)
        for phr, hrx in cur.fetchall():
            if phr and hrx:
                phr_to_hrx[phr] = hrx

    print(f"OK: {len(phr_to_hrx):,} users mapped\n")
    conn.close()

except Exception as e:
    print(f"ERROR: {e}")

hrx_ids = set(phr_to_hrx.values())

# Step 3: Generate daily metrics
print("=" * 100)
print("STEP 3: GENERATING DAILY ENGAGEMENT METRICS")
print("=" * 100)

# Dictionary to store daily counts: date -> activity_type -> set of users
daily_metrics = defaultdict(lambda: defaultdict(set))

# Process meal logs (by phr_id)
print("\n[Meal Logs] Reading daily breakdown...")
try:
    with open('Data/activity_meal_logs.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            phr = (row.get('phr_id') or '').strip()
            activity_date = (row.get('activity_date') or '').strip()
            if phr in vytal_phrs and activity_date >= VYTAL_START:
                daily_metrics[activity_date]['meal'].add(phr)
                count += 1
    print(f"OK: {count:,} meal log records processed")
except Exception as e:
    print(f"Error: {e}")

# Process weight logs (by phr_id)
print("\n[Weight Logs] Reading daily breakdown...")
try:
    with open('Data/activity_weight_logs.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            phr = (row.get('phr_id') or '').strip()
            activity_date = (row.get('activity_date') or '').strip()
            if phr in vytal_phrs and activity_date >= VYTAL_START:
                daily_metrics[activity_date]['weight'].add(phr)
                count += 1
    print(f"OK: {count:,} weight log records processed")
except Exception as e:
    print(f"Error: {e}")

# Process steps logs (by hrx_id) - ONLY count VYTAL mapped hrx_ids
print("\n[Steps Logs] Reading daily breakdown (VYTAL enrolled only)...")
try:
    with open('Data/activity_steps_logs.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            hrx = (row.get('hrx_id') or '').strip()
            activity_date = (row.get('activity_date') or '').strip()
            # IMPORTANT: Only count if hrx is in our VYTAL mapped set (hrx_ids)
            if hrx in hrx_ids and activity_date >= VYTAL_START:
                daily_metrics[activity_date]['steps'].add(hrx)
                count += 1
    print(f"OK: {count:,} step log records processed (VYTAL enrolled only)")
except Exception as e:
    print(f"Error: {e}")

# Process sleep logs (by hrx_id)
print("\n[Sleep Logs] Reading daily breakdown...")
try:
    with open('Data/activity_sleep_logs.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            hrx = (row.get('hrx_id') or '').strip()
            activity_date = (row.get('activity_date') or '').strip()
            if hrx in hrx_ids and activity_date >= VYTAL_START:
                daily_metrics[activity_date]['sleep'].add(hrx)
                count += 1
    print(f"OK: {count:,} sleep log records processed")
except Exception as e:
    print(f"Error: {e}")

# Process app activity (by hrx_id, query for logins/launches post-June)
print("\n[App Activity] Querying daily logins/launches...")
app_daily = defaultdict(set)
try:
    from config import TRINO_HOST, TRINO_USER, TRINO_PASSWORD
    conn = trino.dbapi.connect(
        host=TRINO_HOST,
        port=443,
        http_scheme='https',
        user=TRINO_USER,
        auth=trino.auth.BasicAuthentication(TRINO_USER, TRINO_PASSWORD),
        verify=False,
    )
    cur = conn.cursor()

    hrx_list = list(hrx_ids)
    for batch_idx in range(0, len(hrx_list), 1000):
        batch = hrx_list[batch_idx:batch_idx + 1000]
        hrx_str = "','".join(batch)

        query = f"""
        SELECT DISTINCT hrxid, first_login, first_launch
        FROM deltalake.dl_standard_customermart.customer_first_app_activity
        WHERE hrxid IN ('{hrx_str}')
          AND (
            (first_login IS NOT NULL AND first_login >= timestamp '2026-06-01')
            OR (first_launch IS NOT NULL AND first_launch >= timestamp '2026-06-01')
          )
        """

        cur.execute(query)
        for hrx, login_date, launch_date in cur.fetchall():
            if hrx:
                if login_date:
                    date_str = str(login_date).split()[0]
                    if date_str >= VYTAL_START:
                        app_daily[date_str].add(hrx)
                if launch_date:
                    date_str = str(launch_date).split()[0]
                    if date_str >= VYTAL_START:
                        app_daily[date_str].add(hrx)

    print(f"OK: {len(app_daily):,} days with app activity\n")
    conn.close()

except Exception as e:
    print(f"Error: {e}")

# Add app activity to daily_metrics
for date_str, users in app_daily.items():
    daily_metrics[date_str]['app_activity'] = users

# Step 4: Write to CSV
print("=" * 100)
print("STEP 4: WRITING DAILY ENGAGEMENT CSV")
print("=" * 100)

try:
    with open('Data/managed_care_engagement_daily.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'activity_type', 'unique_users', 'pct_of_enrolled', 'programme', 'data_source'])

        # Iterate through all dates and activity types
        for date_str in sorted(daily_metrics.keys()):
            for activity_type in ['meal', 'weight', 'steps', 'sleep', 'app_activity']:
                user_count = len(daily_metrics[date_str][activity_type])
                pct = (user_count / enrolled_count * 100) if enrolled_count > 0 else 0

                writer.writerow([
                    date_str,
                    activity_type,
                    user_count,
                    f'{pct:.2f}',
                    'VYTAL',
                    'activity_logs'
                ])

    print(f"OK: Written Data/managed_care_engagement_daily.csv\n")

except Exception as e:
    print(f"ERROR writing CSV: {e}")

# Summary
print("=" * 100)
print("SUMMARY")
print("=" * 100)

total_records = len(daily_metrics)
print(f"\nDaily engagement CSV created:")
print(f"  Date range: {VYTAL_START} to {VYTAL_END}")
print(f"  Days with activity: {total_records}")
print(f"  Total enrolled: {enrolled_count:,}")
print(f"  Format: date | activity_type | unique_users | pct_of_enrolled")
print(f"\nUsage in dashboard:")
print(f"  1. Load this CSV in dashboard")
print(f"  2. Filter by Care Operations date range: DATE_FROM to DATE_TO")
print(f"  3. Display metrics for selected period")

# Show sample data
print("\n" + "=" * 100)
print("SAMPLE DATA (First 20 rows)")
print("=" * 100)

with open('Data/managed_care_engagement_daily.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for i, row in enumerate(reader):
        if i < 21:
            print(" | ".join(row))

print("\n" + "=" * 100)
print("DONE")
print("=" * 100)
