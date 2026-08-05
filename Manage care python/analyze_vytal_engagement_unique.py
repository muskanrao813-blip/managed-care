#!/usr/bin/env python3
"""
VYTAL Engagement Analysis - UNIQUE USERS ONLY
Counts distinct users (not records), filters for post-June 1, 2026
"""
import sys
import csv
import trino
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 100)
print("VYTAL ENGAGEMENT ANALYSIS - UNIQUE USERS (Post June 1, 2026)")
print("=" * 100)

VYTAL_START = '2026-06-01'

# Step 1: Load VYTAL enrolled users
print("\n[Step 1] Loading VYTAL enrolled users from policy_data.csv...")
vytal_phrs = set()
vytal_test_count = 0
try:
    with open('Data/managed_care_policy_data.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mc_code = (row.get('mc_product_code') or '').strip()
            phr_id = (row.get('phr_id') or '').strip()
            is_test = (row.get('is_test_policy') or '').strip().lower()

            if mc_code.startswith('VYTAL') and phr_id:
                if is_test in ['true', '1', 'yes']:
                    vytal_test_count += 1
                else:
                    vytal_phrs.add(phr_id)

    enrolled_count = len(vytal_phrs)
    print(f"OK: Found {enrolled_count:,} VYTAL enrolled users (excluded {vytal_test_count} test policies)\n")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

# Step 2: Get hrx_id mapping
print("=" * 100)
print("STEP 2: FETCHING HRX_ID MAPPING FROM D_POLICY")
print("=" * 100)

phr_to_hrx = {}
try:
    print("\n[Connecting] Trino...")
    conn = trino.dbapi.connect(
        host='trino-prod.healthrx.co.in',
        port=443,
        http_scheme='https',
        user='vasu.verma',
        auth=trino.auth.BasicAuthentication('vasu.verma', 'vvaass6543'),
        verify=False,
    )
    cur = conn.cursor()
    print("OK: Connected\n")

    phr_list = list(vytal_phrs)
    batch_size = 5000
    num_batches = (len(phr_list) + batch_size - 1) // batch_size

    for batch_idx in range(num_batches):
        batch = phr_list[batch_idx * batch_size:(batch_idx + 1) * batch_size]
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

    print(f"OK: Mapped {len(phr_to_hrx):,} users to hrx_ids\n")
    conn.close()

except Exception as e:
    print(f"ERROR: {e}")

# Step 3: Count UNIQUE users with activities (post-June 1)
print("=" * 100)
print("STEP 3: COUNTING UNIQUE USERS WITH ACTIVITIES (Post June 1, 2026)")
print("=" * 100)

hrx_ids = set(phr_to_hrx.values())

# Meal logs - UNIQUE phr_ids
print("\n[Meal Logs] Unique users matching by phr_id (>=June 1)...")
meal_users = set()
try:
    with open('Data/activity_meal_logs.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            phr = (row.get('phr_id') or '').strip()
            activity_date = (row.get('activity_date') or '').strip()
            if phr in vytal_phrs and activity_date >= VYTAL_START:
                meal_users.add(phr)
    meal_pct = (len(meal_users) / enrolled_count * 100) if enrolled_count > 0 else 0
    print(f"OK: {len(meal_users):,} UNIQUE users ({meal_pct:.2f}%)")
except Exception as e:
    print(f"Error: {e}")

# Weight logs - UNIQUE phr_ids
print("\n[Weight Logs] Unique users matching by phr_id (>=June 1)...")
weight_users = set()
try:
    with open('Data/activity_weight_logs.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            phr = (row.get('phr_id') or '').strip()
            activity_date = (row.get('activity_date') or '').strip()
            if phr in vytal_phrs and activity_date >= VYTAL_START:
                weight_users.add(phr)
    weight_pct = (len(weight_users) / enrolled_count * 100) if enrolled_count > 0 else 0
    print(f"OK: {len(weight_users):,} UNIQUE users ({weight_pct:.2f}%)")
except Exception as e:
    print(f"Error: {e}")

# Steps logs - UNIQUE hrx_ids
print("\n[Steps Logs] Unique users matching by hrx_id (>=June 1)...")
steps_users = set()
try:
    with open('Data/activity_steps_logs.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            hrx = (row.get('hrx_id') or '').strip()
            activity_date = (row.get('activity_date') or '').strip()
            if hrx in hrx_ids and activity_date >= VYTAL_START:
                steps_users.add(hrx)
    steps_pct = (len(steps_users) / enrolled_count * 100) if enrolled_count > 0 else 0
    print(f"OK: {len(steps_users):,} UNIQUE users ({steps_pct:.2f}%)")
except Exception as e:
    print(f"Error: {e}")

# Sleep logs - UNIQUE hrx_ids
print("\n[Sleep Logs] Unique users matching by hrx_id (>=June 1)...")
sleep_users = set()
try:
    with open('Data/activity_sleep_logs.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            hrx = (row.get('hrx_id') or '').strip()
            activity_date = (row.get('activity_date') or '').strip()
            if hrx in hrx_ids and activity_date >= VYTAL_START:
                sleep_users.add(hrx)
    sleep_pct = (len(sleep_users) / enrolled_count * 100) if enrolled_count > 0 else 0
    print(f"OK: {len(sleep_users):,} UNIQUE users ({sleep_pct:.2f}%)")
except Exception as e:
    print(f"Error: {e}")

# App activity - UNIQUE hrx_ids with actual app actions post-June
print("\n[App Activity] Unique users with logins/launches (>=June 1)...")
app_users = set()
try:
    conn = trino.dbapi.connect(
        host='trino-prod.healthrx.co.in',
        port=443,
        http_scheme='https',
        user='vasu.verma',
        auth=trino.auth.BasicAuthentication('vasu.verma', 'vvaass6543'),
        verify=False,
    )
    cur = conn.cursor()

    hrx_list = list(hrx_ids)
    for batch_idx in range(0, len(hrx_list), 1000):
        batch = hrx_list[batch_idx:batch_idx + 1000]
        hrx_str = "','".join(batch)

        query = f"""
        SELECT DISTINCT hrxid
        FROM deltalake.dl_standard_customermart.customer_first_app_activity
        WHERE hrxid IN ('{hrx_str}')
          AND (
            (first_login IS NOT NULL AND first_login >= timestamp '2026-06-01')
            OR (first_launch IS NOT NULL AND first_launch >= timestamp '2026-06-01')
            OR (first_web_login_date IS NOT NULL AND first_web_login_date >= timestamp '2026-06-01')
            OR (first_web_launch_date IS NOT NULL AND first_web_launch_date >= timestamp '2026-06-01')
          )
        """

        cur.execute(query)
        for (hrx,) in cur.fetchall():
            if hrx:
                app_users.add(hrx)

    app_pct = (len(app_users) / enrolled_count * 100) if enrolled_count > 0 else 0
    print(f"OK: {len(app_users):,} UNIQUE users ({app_pct:.2f}%)")
    conn.close()

except Exception as e:
    print(f"Error: {e}")

# Summary
print("\n" + "=" * 100)
print("SUMMARY - VYTAL ENGAGEMENT (Post-June 1, 2026 Only - UNIQUE USERS)")
print("=" * 100)

print(f"\nProgram: VYTAL")
print(f"Total Enrolled: {enrolled_count:,}")
print(f"Test Policies Excluded: {vytal_test_count}")
print(f"Start Date: {VYTAL_START}")

print(f"\n{'Activity':<20} {'Unique Users':<15} {'% of Total':<15}")
print("-" * 50)
print(f"{'Meal Logs':<20} {len(meal_users):<15} {(len(meal_users) / enrolled_count * 100):5.2f}%")
print(f"{'Weight Logs':<20} {len(weight_users):<15} {(len(weight_users) / enrolled_count * 100):5.2f}%")
print(f"{'Steps Logs':<20} {len(steps_users):<15} {(len(steps_users) / enrolled_count * 100):5.2f}%")
print(f"{'Sleep Logs':<20} {len(sleep_users):<15} {(len(sleep_users) / enrolled_count * 100):5.2f}%")
print(f"{'App Activity':<20} {len(app_users):<15} {(len(app_users) / enrolled_count * 100):5.2f}%")

# Coverage
all_users = meal_users | weight_users | steps_users | sleep_users | app_users
coverage_pct = (len(all_users) / enrolled_count * 100) if enrolled_count > 0 else 0
print(f"\n{'Any Activity':<20} {len(all_users):<15} {coverage_pct:5.2f}%")

# Write corrected CSV
print("\n" + "=" * 100)
print("WRITING CORRECTED ENGAGEMENT CSV")
print("=" * 100)

try:
    meal_pct = (len(meal_users) / enrolled_count * 100) if enrolled_count > 0 else 0
    weight_pct = (len(weight_users) / enrolled_count * 100) if enrolled_count > 0 else 0
    steps_pct = (len(steps_users) / enrolled_count * 100) if enrolled_count > 0 else 0
    sleep_pct = (len(sleep_users) / enrolled_count * 100) if enrolled_count > 0 else 0
    app_pct = (len(app_users) / enrolled_count * 100) if enrolled_count > 0 else 0

    with open('Data/managed_care_engagement_activities.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'programme', 'product_code', 'total_enrolled',
            'meal_logged', 'meal_pct', 'weight_logged', 'weight_pct',
            'steps_logged', 'steps_pct', 'sleep_logged', 'sleep_pct',
            'app_activity_users', 'app_pct', 'data_month', 'last_updated'
        ])
        writer.writerow([
            'VYTAL', 'VYTAL0126-01026', enrolled_count,
            len(meal_users), f'{meal_pct:.2f}',
            len(weight_users), f'{weight_pct:.2f}',
            len(steps_users), f'{steps_pct:.2f}',
            len(sleep_users), f'{sleep_pct:.2f}',
            len(app_users), f'{app_pct:.2f}',
            '2026-06', datetime.now().strftime('%Y-%m-%d')
        ])
    print("OK: Updated Data/managed_care_engagement_activities.csv")
except Exception as e:
    print(f"Error writing CSV: {e}")

print("\n" + "=" * 100)
print("DONE")
print("=" * 100)
