"""
Trino Schema Explorer for AI Care Coordinator
Run this once to understand d_policy and f_claims structure.
Paste the full output back to Claude.

Usage:
    pip install trino python-dotenv
    python explore_trino_schema.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

TRINO_HOST     = os.getenv("TRINO_HOST", "")          # FILL THIS IN
TRINO_PORT     = int(os.getenv("TRINO_PORT", "443"))
TRINO_USER     = os.getenv("TRINO_USER", "vasu.verma")
TRINO_PASSWORD = os.getenv("TRINO_PASSWORD", "")       # put in .env, not here
TRINO_CATALOG  = os.getenv("TRINO_CATALOG", "")        # FILL THIS IN
TRINO_SCHEMA   = os.getenv("TRINO_SCHEMA",  "")        # FILL THIS IN

# ─────────────────────────────────────────────────────────────────────────────

try:
    from trino.dbapi import connect
    from trino.auth import BasicAuthentication
except ImportError:
    print("Run: pip install trino")
    exit(1)

def get_conn():
    return connect(
        host        = TRINO_HOST,
        port        = TRINO_PORT,
        user        = TRINO_USER,
        auth        = BasicAuthentication(TRINO_USER, TRINO_PASSWORD),
        catalog     = TRINO_CATALOG,
        schema      = TRINO_SCHEMA,
        http_scheme = "https",
    )

def run(cursor, sql):
    cursor.execute(sql)
    cols = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    return cols, rows

def print_table(title, cols, rows):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(" | ".join(str(c).ljust(25) for c in cols))
    print("-" * 60)
    for row in rows:
        print(" | ".join(str(v)[:25].ljust(25) for v in row))


conn   = get_conn()
cursor = conn.cursor()

# ── 1. List all available schemas ────────────────────────────────────────────
print("\n[1] AVAILABLE SCHEMAS")
cols, rows = run(cursor, "SHOW SCHEMAS")
for r in rows:
    print(" ", r[0])

# ── 2. List all tables in current schema ─────────────────────────────────────
print("\n[2] TABLES IN SCHEMA:", TRINO_SCHEMA)
cols, rows = run(cursor, "SHOW TABLES")
for r in rows:
    print(" ", r[0])

# ── 3. d_policy — full column structure ──────────────────────────────────────
print("\n[3] d_policy COLUMNS")
cols, rows = run(cursor, "DESCRIBE d_policy")
print_table("d_policy schema", cols, rows)

# ── 4. d_policy — VYTAL diabetes users count ─────────────────────────────────
print("\n[4] VYTAL DIABETES USER COUNT")
cols, rows = run(cursor, """
    SELECT
        product_code,
        COUNT(DISTINCT phr_id) AS user_count
    FROM d_policy
    WHERE product_code IN ('VYTAL0126', 'VYTAL0626')
    GROUP BY product_code
    ORDER BY product_code
""")
print_table("Diabetes programme users", cols, rows)

# ── 5. d_policy — sample 3 rows (structure check, no real PHI printed) ───────
print("\n[5] d_policy SAMPLE ROWS (structure only)")
cols, rows = run(cursor, """
    SELECT *
    FROM d_policy
    WHERE product_code IN ('VYTAL0126', 'VYTAL0626')
    LIMIT 3
""")
print("Columns found:", cols)
print("Row count returned:", len(rows))
print("Sample first row values (types):")
if rows:
    for col, val in zip(cols, rows[0]):
        print(f"  {col}: {type(val).__name__} = {repr(val)[:60]}")

# ── 6. d_policy — all column names with data types ───────────────────────────
# Already done via DESCRIBE above, but also check for cohort/risk fields
print("\n[6] d_policy — COLUMNS CONTAINING 'cohort', 'risk', 'score', 'status'")
cols, rows = run(cursor, "DESCRIBE d_policy")
for row in rows:
    col_name = str(row[0]).lower()
    if any(kw in col_name for kw in ['cohort', 'risk', 'score', 'status', 'phr', 'member', 'enroll', 'start', 'end', 'product']):
        print(f"  {row[0]}  [{row[1]}]")

# ── 7. f_claims — full column structure ──────────────────────────────────────
print("\n[7] f_claims COLUMNS")
cols, rows = run(cursor, "DESCRIBE f_claims")
print_table("f_claims schema", cols, rows)

# ── 8. f_claims — distinct claim / service types ─────────────────────────────
print("\n[8] f_claims — DISTINCT SERVICE / CLAIM TYPES")
# Try multiple likely column names for claim type
for col_candidate in ['claim_type', 'service_type', 'consultation_type', 'benefit_type', 'category', 'sub_category', 'procedure_type']:
    try:
        cols, rows = run(cursor, f"""
            SELECT {col_candidate}, COUNT(*) as cnt
            FROM f_claims
            GROUP BY {col_candidate}
            ORDER BY cnt DESC
            LIMIT 20
        """)
        print(f"\n  Found column: {col_candidate}")
        print_table(f"f_claims.{col_candidate} values", cols, rows)
        break
    except Exception:
        pass

# ── 9. f_claims — sample join with d_policy for one VYTAL user ───────────────
print("\n[9] f_claims — JOIN WITH d_policy (1 diabetes user, all their claims)")
try:
    cols, rows = run(cursor, """
        SELECT
            f.phr_id,
            f.*
        FROM f_claims f
        INNER JOIN (
            SELECT phr_id FROM d_policy
            WHERE product_code IN ('VYTAL0126','VYTAL0626')
            LIMIT 1
        ) p ON f.phr_id = p.phr_id
        LIMIT 10
    """)
    print("Columns in f_claims:", cols)
    print(f"Rows returned for this user: {len(rows)}")
    if rows:
        print("First row sample (types only):")
        for col, val in zip(cols, rows[0]):
            print(f"  {col}: {type(val).__name__} = {repr(val)[:60]}")
except Exception as e:
    print(f"  Join failed: {e}")
    print("  Trying to find PHR ID column in f_claims...")
    cols, rows = run(cursor, "DESCRIBE f_claims")
    for row in rows:
        if 'phr' in str(row[0]).lower() or 'member' in str(row[0]).lower() or 'patient' in str(row[0]).lower():
            print(f"  Possible ID column: {row[0]} [{row[1]}]")

# ── 10. f_claims — doctor, diet, lab consultation counts for VYTAL users ─────
print("\n[10] CONSULTATION COUNTS FOR VYTAL DIABETES USERS")
print("  (Trying common column patterns for claim type...)")

consultation_queries = [
    # Pattern A: claim_type column
    """
    SELECT
        f.claim_type,
        COUNT(DISTINCT f.phr_id) AS unique_patients,
        COUNT(*) AS total_claims
    FROM f_claims f
    WHERE f.phr_id IN (
        SELECT phr_id FROM d_policy
        WHERE product_code IN ('VYTAL0126','VYTAL0626')
    )
    GROUP BY f.claim_type
    ORDER BY total_claims DESC
    """,
    # Pattern B: service_type column
    """
    SELECT
        f.service_type,
        COUNT(DISTINCT f.phr_id) AS unique_patients,
        COUNT(*) AS total_claims
    FROM f_claims f
    WHERE f.phr_id IN (
        SELECT phr_id FROM d_policy
        WHERE product_code IN ('VYTAL0126','VYTAL0626')
    )
    GROUP BY f.service_type
    ORDER BY total_claims DESC
    """,
    # Pattern C: benefit_type column
    """
    SELECT
        f.benefit_type,
        COUNT(DISTINCT f.phr_id) AS unique_patients,
        COUNT(*) AS total_claims
    FROM f_claims f
    WHERE f.phr_id IN (
        SELECT phr_id FROM d_policy
        WHERE product_code IN ('VYTAL0126','VYTAL0626')
    )
    GROUP BY f.benefit_type
    ORDER BY total_claims DESC
    """,
]

for q in consultation_queries:
    try:
        cols, rows = run(cursor, q)
        print_table("Consultation type breakdown", cols, rows)
        break
    except Exception as e:
        print(f"  Query pattern failed: {e}")
        continue

# ── 11. Summary stats ─────────────────────────────────────────────────────────
print("\n[11] SUMMARY — WHAT WE NEED FOR THE AI ENGINE")
print("""
From this output, share back:
  a) The exact column names for:
     - PHR ID in both tables
     - Product code in d_policy
     - Cohort / risk level in d_policy
     - Policy start date / enrollment date in d_policy
     - Claim / consultation type in f_claims
     - Claim date in f_claims
     - Claim status in f_claims

  b) Whether there are separate tables for:
     - Lab results
     - HRA / health risk assessment answers
     - Engagement events (steps, meal logs, mood logs)

  c) The actual values used for doctor, diet, lab consultation types
     in f_claims (e.g., is it 'DOCTOR_CONSULT' or 'OPD' or 'Teleconsult'?)
""")

print("\nDONE — paste this full output back to Claude.")
cursor.close()
conn.close()
