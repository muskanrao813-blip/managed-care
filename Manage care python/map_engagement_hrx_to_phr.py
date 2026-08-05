#!/usr/bin/env python3
"""
Map hrx_id to phr_id for sleep/steps activity logs using d_policy table
Enhances activity_sleep_logs.csv and activity_steps_logs.csv with phr_id column
for cohort-based analysis in the dashboard
"""

import sys
import csv
import trino

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 80)
print("MAPPING HRX_ID TO PHR_ID FOR ENGAGEMENT ACTIVITIES")
print("=" * 80)

# Connect to Trino
print("\n[Connecting] Trino via OAuth2...")
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

# Fetch unique hrx_ids from sleep and steps logs
print("[Step 1] Extracting unique hrx_ids from activity logs...")
sleep_file = "Data/activity_sleep_logs.csv"
steps_file = "Data/activity_steps_logs.csv"

hrx_ids = set()
try:
    with open(sleep_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('hrx_id'):
                hrx_ids.add(row['hrx_id'])
    print(f"  ✓ Sleep logs: {len(hrx_ids)} unique hrx_ids")
except Exception as e:
    print(f"  ✗ Error reading sleep logs: {e}")

try:
    with open(steps_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('hrx_id'):
                hrx_ids.add(row['hrx_id'])
    print(f"  ✓ Steps logs: {len(hrx_ids)} total unique hrx_ids (combined)")
except Exception as e:
    print(f"  ✗ Error reading steps logs: {e}")

# Query weight_progresses table for hrx_id to phr_id mapping (since both are available there)
print("\n[Step 2] Querying weight_progresses for hrx_id → phr_id mapping...")
hrx_to_phr = {}
try:
    # Convert hrx_ids to a list for SQL IN clause
    hrx_ids_list = list(hrx_ids)
    chunk_size = 1000  # Query in chunks to avoid very long IN clauses

    for i in range(0, len(hrx_ids_list), chunk_size):
        chunk = hrx_ids_list[i:i+chunk_size]
        # Create IN clause
        in_clause = "','".join(chunk)

        query = f"""
        SELECT DISTINCT hrx_id, phr_id
        FROM deltalake.dl_central_activity_tracker.weight_progresses
        WHERE hrx_id IN ('{in_clause}')
          AND phr_id IS NOT NULL
        """

        try:
            cur.execute(query)
            rows = cur.fetchall()
            for hrx_id, phr_id in rows:
                if hrx_id and phr_id:
                    hrx_to_phr[hrx_id] = phr_id
            print(f"  ✓ Chunk {i//chunk_size + 1}: Mapped {len(rows)} hrx_ids")
        except Exception as e:
            print(f"  ✗ Chunk query failed: {e}")

    print(f"  Total mapped: {len(hrx_to_phr)}/{len(hrx_ids)} hrx_ids")
    print(f"  (Note: Only hrx_ids present in weight_progresses can be mapped)")
except Exception as e:
    print(f"  ✗ Mapping failed: {e}")
    print("  → Will continue with available mappings")

# Enhance activity logs with phr_id
print("\n[Step 3] Enhancing activity logs with phr_id...")

for activity_type, input_file in [('sleep', sleep_file), ('steps', steps_file)]:
    output_file = input_file.replace('.csv', '_with_phr.csv')

    try:
        rows_enhanced = 0
        rows_no_mapping = 0

        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

            # Add phr_id column if not present
            if 'phr_id' not in fieldnames:
                fieldnames = ['phr_id'] + list(fieldnames)

            with open(output_file, 'w', newline='', encoding='utf-8') as out_f:
                writer = csv.DictWriter(out_f, fieldnames=fieldnames)
                writer.writeheader()

                for row in reader:
                    hrx_id = row.get('hrx_id', '')
                    phr_id = hrx_to_phr.get(hrx_id, '')

                    if phr_id:
                        row['phr_id'] = phr_id
                        rows_enhanced += 1
                    else:
                        row['phr_id'] = ''
                        rows_no_mapping += 1

                    writer.writerow(row)

        print(f"\n  ✓ {activity_type.upper()}:")
        print(f"    - Enhanced: {rows_enhanced} records with phr_id")
        print(f"    - No mapping: {rows_no_mapping} records")
        print(f"    - Output: {output_file}")

    except Exception as e:
        print(f"  ✗ Error processing {activity_type}: {e}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"\nHRX_ID → PHR_ID Mapping Results:")
print(f"  • Unique hrx_ids in activity logs: {len(hrx_ids)}")
print(f"  • Successfully mapped: {len(hrx_to_phr)}")
print(f"  • Mapping rate: {(len(hrx_to_phr)/len(hrx_ids)*100):.1f}% (if > 0)")
print(f"\nNew files with phr_id column:")
print(f"  • Data/activity_sleep_logs_with_phr.csv")
print(f"  • Data/activity_steps_logs_with_phr.csv")
print(f"\nNext: Rename _with_phr files to replace original files when ready for production use.")

conn.close()
print("\nDone.\n")
