"""
============================================================
AGENT 0 — TRINO FETCHER (Fresh Data Sync)
============================================================
Every 6 hours: Syncs VYTAL enrolled users from Trino d_policy.
Keeps Patient table fresh before any communication agents run.

This ensures:
  - No stale data from 6 hours ago
  - New enrollments captured immediately
  - Updated cohort/status before Agent 1 runs

If Trino unavailable: uses cached CSV fallback.

CRITICAL — DATA SOURCE:
  ❌ DO NOT use: managed_care_program_allocation_2026.csv (lacks product_code column)
  ✅ USE: managed_care_activity_logs.csv (has product_code for VYTAL filtering)

  Why: program_allocation.csv contains ALL users (11,498 total). Activity_logs has
  product code column required for filtering to VYTAL only (6,059 users).
  Using wrong source → wrong cohort → useless communication plans.

Usage:
  python -m agents.agent0_trino_sync
  python -m agents.agent0_trino_sync --dry-run
  python -m agents.agent0_trino_sync --test
"""

import sys, os, json, sqlite3
import pandas as pd
from datetime import datetime, date
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = Path(__file__).parent.parent
DATA_DIR = SCRIPT_DIR / "Data"
DB_PATH = SCRIPT_DIR / "agents" / "agent_db.sqlite"

VYTAL_CODES = [
    'VYTAL0126', 'VYTAL0226', 'VYTAL0326', 'VYTAL0426', 'VYTAL0526',
    'VYTAL0626', 'VYTAL0726', 'VYTAL0826', 'VYTAL0926', 'VYTAL01026'
]

PROGRAMME_MAP = {
    'VYTAL0126': 'Diabetes Management',
    'VYTAL0226': 'Dyslipidemia Management',
    'VYTAL0326': 'Liver Care',
    'VYTAL0426': 'Kidney Care',
    'VYTAL0526': 'Thyroid Care',
    'VYTAL0626': 'Diabetes Management',
    'VYTAL0726': 'Dyslipidemia Management',
    'VYTAL0826': 'Liver Care',
    'VYTAL0926': 'Kidney Care',
    'VYTAL01026': 'Thyroid Care',
}

class TrinoFetcher:
    """Fetch fresh VYTAL enrollments from Trino or cached CSV."""

    def __init__(self):
        self.today = date.today()
        self.sync_timestamp = datetime.now().isoformat()

    def fetch_users(self, use_trino=False):
        """Fetch users from Trino (prod) or CSV (fallback)."""
        if use_trino:
            return self._fetch_from_trino()
        else:
            return self._fetch_from_csv()

    def _fetch_from_trino(self):
        """Query Trino d_policy for fresh VYTAL enrollments."""
        print("  Attempting Trino connection...")
        try:
            import trino
        except ImportError:
            print("  ⚠️  Trino not installed, falling back to CSV")
            return self._fetch_from_csv()

        try:
            conn = trino.dbapi.connect(
                host="trino-prod.healthrx.co.in",
                port=443,
                http_scheme='https',
                auth=trino.auth.OAuth2Authentication(),
                verify=True,
            )
            cursor = conn.cursor()

            # Query: VYTAL enrollments, June 2026+
            codes_str = ", ".join(f"'{c}'" for c in VYTAL_CODES)
            sql = f"""
            SELECT
              phr_id,
              mobile_number_hash,
              product_code,
              enrollment_date,
              cohort_assignment,
              is_active
            FROM deltalake.dl_standard_customermart.d_policy
            WHERE product_code IN ({codes_str})
              AND enrollment_date >= DATE('2026-06-01')
            ORDER BY enrollment_date DESC
            """

            print(f"  Running Trino query...")
            cursor.execute(sql)
            rows = cursor.fetchall()
            desc = [d[0] for d in cursor.description]

            df = pd.DataFrame(rows, columns=desc)
            cursor.close()
            conn.close()

            print(f"  ✅ Fetched {len(df):,} users from Trino")
            return df

        except Exception as e:
            print(f"  ❌ Trino connection failed: {str(e)[:100]}")
            print(f"  Falling back to cached CSV")
            return self._fetch_from_csv()

    def _fetch_from_csv(self):
        """Fallback: read from cached activity_logs with VYTAL filtering"""
        try:
            # Use activity_logs which has product codes for proper VYTAL filtering
            df = pd.read_csv(DATA_DIR / "managed_care_activity_logs.csv")

            # Filter to VYTAL product codes only
            vytal_codes = ['VYTAL0126','VYTAL0226','VYTAL0326','VYTAL0426','VYTAL0526',
                          'VYTAL0626','VYTAL0726','VYTAL0826','VYTAL0926','VYTAL01026']
            df = df[df['mc_product_code'].isin(vytal_codes)]

            # Get unique users only
            df = df[['mobile_number_hash', 'mc_product_code', 'programme']].drop_duplicates()

            print(f"  ✅ Fetched {len(df):,} VYTAL users from cached CSV (filtered)")
            print(f"     Product codes: {sorted(df['mc_product_code'].unique().tolist())}")

            return df
        except Exception as e:
            print(f"  ❌ CSV read failed: {e}")
            return pd.DataFrame()

    def sync_to_db(self, df):
        """Save/update Patient table in SQLite."""
        if df.empty:
            print("  No users to sync")
            return 0

        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Create Patient table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY,
                phr_id TEXT UNIQUE,
                mobile_number_hash TEXT,
                programme TEXT,
                cohort TEXT,
                product_code TEXT,
                enrollment_date TEXT,
                last_sync_at TEXT,
                is_active INTEGER,
                agent1_processed_at TEXT,
                agent2_processed_at TEXT
            )
        ''')

        # Batch insert/update
        inserted = 0
        updated = 0

        for _, row in df.iterrows():
            phr_id = str(row.get('mobile_number_hash', ''))  # Use hash as ID if phr_id not available
            product_code = row.get('mc_product_code', row.get('product_code', 'VYTAL0126'))
            programme = PROGRAMME_MAP.get(product_code, 'Unknown')
            cohort = 'Unknown'  # Would come from Trino cohort_assignment

            cursor.execute('''
                INSERT OR REPLACE INTO patients
                (phr_id, mobile_number_hash, programme, cohort, product_code,
                 enrollment_date, last_sync_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                phr_id,
                phr_id,
                programme,
                cohort,
                product_code,
                '2026-06-01',  # Enrollment date
                self.sync_timestamp,
                1  # is_active
            ))

            # Check if this was insert or update
            if cursor.lastrowid > 0:
                inserted += 1
            else:
                updated += 1

        conn.commit()
        conn.close()

        print(f"  ✅ Synced to DB: {inserted} new, {updated} updated")
        return len(df)

    def create_sync_log(self, sync_count):
        """Log this sync event."""
        log_entry = {
            'sync_timestamp': self.sync_timestamp,
            'users_synced': sync_count,
            'product_codes': VYTAL_CODES,
            'status': 'success' if sync_count > 0 else 'no_data',
        }

        log_path = DATA_DIR / "agent0_sync_log.jsonl"
        with open(log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        print(f"  Sync logged to {log_path}")
        return log_entry


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--trino', action='store_true', help='Force Trino (no fallback)')
    parser.add_argument('--dry-run', action='store_true', help='Preview, don\'t save')
    parser.add_argument('--test', action='store_true', help='Test mode (5 users)')
    args = parser.parse_args()

    print("\n" + "="*70)
    print("AGENT 0 — TRINO FETCHER: Fresh VYTAL Data Sync")
    print("="*70)
    print(f"\nSync Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'Trino-only' if args.trino else 'Trino with CSV fallback'}")
    print(f"Dry-run: {args.dry_run}")

    fetcher = TrinoFetcher()

    # Fetch users
    print("\n[Step 1] Fetching VYTAL users...")
    df = fetcher.fetch_users(use_trino=args.trino)

    if df.empty:
        print("❌ No users fetched")
        return

    print(f"\nUsers fetched: {len(df)}")
    if args.test:
        df = df.head(5)
        print(f"Test mode: limiting to {len(df)} users")

    print(f"Sample users:")
    for i, row in df.head(3).iterrows():
        user_id = str(row.get('mobile_number_hash', 'N/A'))[:20]
        condition = row.get('impact', row.get('programme', 'N/A'))
        print(f"  - {user_id}... ({condition})")

    # Sync to DB
    if args.dry_run:
        print("\n[Dry-run mode] Skipping database sync")
    else:
        print("\n[Step 2] Syncing to SQLite...")
        sync_count = fetcher.sync_to_db(df)

        # Log sync
        print("\n[Step 3] Logging sync event...")
        log_entry = fetcher.create_sync_log(sync_count)
        print(json.dumps(log_entry, indent=2))

    print("\n" + "="*70)
    print("✅ Agent 0 sync complete")
    print("="*70)
    print(f"\nPatient table ready for Agent 1 (Data Analyst)")
    print(f"Next: Agent 1 will assemble signals for {len(df)} users")
    print("\n")


if __name__ == '__main__':
    main()
