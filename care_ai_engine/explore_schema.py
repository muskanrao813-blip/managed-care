"""
Run this once. Paste the full output back to Claude.
It will resolve the 3 remaining unknowns:
  1. d_policy exact columns (cohort, status, enrollment date)
  2. f_claim consultation type column name + actual values
  3. Whether separate HRA / engagement tables exist

Usage:
    pip install sqlalchemy trino pandas python-dotenv
    cd care_ai_engine
    python explore_schema.py
"""

import os, urllib.parse, pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

USER = os.getenv("TRINO_USER", "vasu.verma")
PASS = urllib.parse.quote_plus(os.getenv("TRINO_PASSWORD", "vvaass6543"))
URL  = f"trino://{USER}:{PASS}@trino-prod.healthrx.co.in:443/system?http_scheme=https"
VYTAL = "'VYTAL0126','VYTAL0626'"


def q(sql):
    engine = create_engine(URL)
    with engine.begin() as con:
        df = pd.read_sql(text(sql), con)
    engine.dispose()
    return df


def section(title):
    print(f"\n{'='*65}\n  {title}\n{'='*65}")


# ── 1. d_policy — full column list ───────────────────────────────────────────
section("1. d_policy — ALL COLUMNS")
try:
    df = q("DESCRIBE deltalake.dl_standard_customermart.d_policy")
    print(df.to_string(index=False))
except Exception as e:
    print(f"ERROR: {e}")

# ── 2. d_policy — sample VYTAL row (types only, no real values) ──────────────
section("2. d_policy — VYTAL SAMPLE ROW (column names + value types)")
try:
    df = q(f"""
        SELECT * FROM deltalake.dl_standard_customermart.d_policy
        WHERE product_code IN ({VYTAL})
        LIMIT 1
    """)
    print("Columns:", list(df.columns))
    print("\nColumn → sample value:")
    for col in df.columns:
        print(f"  {col:35s} = {repr(str(df[col].iloc[0]))[:60]}")
except Exception as e:
    print(f"ERROR: {e}")

# ── 3. d_policy — VYTAL user count ───────────────────────────────────────────
section("3. d_policy — USER COUNT BY PRODUCT CODE")
try:
    df = q(f"""
        SELECT product_code, COUNT(DISTINCT phr_id) as patients
        FROM deltalake.dl_standard_customermart.d_policy
        WHERE product_code IN ({VYTAL})
        GROUP BY product_code
    """)
    print(df.to_string(index=False))
except Exception as e:
    print(f"ERROR: {e}")

# ── 4. f_claim — ALL COLUMNS ─────────────────────────────────────────────────
section("4. f_claim — ALL COLUMNS")
try:
    df = q("DESCRIBE deltalake.dl_standard_customermart.f_claim")
    print(df.to_string(index=False))
except Exception as e:
    print(f"ERROR: {e}")

# ── 5. f_claim — sample VYTAL row ────────────────────────────────────────────
section("5. f_claim — VYTAL SAMPLE ROW")
try:
    df = q(f"""
        SELECT * FROM deltalake.dl_standard_customermart.f_claim
        WHERE product_code IN ({VYTAL})
        LIMIT 1
    """)
    print("Columns:", list(df.columns))
    for col in df.columns:
        print(f"  {col:35s} = {repr(str(df[col].iloc[0]))[:60]}")
except Exception as e:
    print(f"ERROR: {e}")

# ── 6. f_claim — ALL DISTINCT CLAIM / SERVICE TYPE VALUES ────────────────────
section("6. f_claim — DISTINCT VALUES IN LIKELY TYPE COLUMNS")
for col in ["service_type", "claim_type", "benefit_type",
            "sub_product_code", "category", "consultation_type",
            "order_type", "claim_category"]:
    try:
        df = q(f"""
            SELECT '{col}' as col_name, {col}, COUNT(*) as cnt
            FROM deltalake.dl_standard_customermart.f_claim
            WHERE product_code IN ({VYTAL})
            GROUP BY {col}
            ORDER BY cnt DESC
            LIMIT 15
        """)
        print(f"\n  Column '{col}' found:")
        print(df.to_string(index=False))
    except Exception:
        pass   # column doesn't exist, try next

# ── 7. customers table — all columns ─────────────────────────────────────────
section("7. customers (dl_central_hrxlabs) — ALL COLUMNS")
try:
    df = q("DESCRIBE deltalake.dl_central_hrxlabs.customers")
    print(df.to_string(index=False))
except Exception as e:
    print(f"ERROR: {e}")

# ── 8. All schemas in deltalake catalog ──────────────────────────────────────
section("8. ALL SCHEMAS IN deltalake CATALOG")
try:
    df = q("SHOW SCHEMAS IN deltalake")
    for _, r in df.iterrows():
        print(" ", r.iloc[0])
except Exception as e:
    print(f"ERROR: {e}")

# ── 9. Look for HRA / engagement / wellness tables ───────────────────────────
section("9. LOOKING FOR HRA / ENGAGEMENT / WELLNESS TABLES")
schemas_to_check = [
    "dl_standard_customermart",
    "dl_central_hrxlabs",
    "dl_central_health_vault",
    "dl_standard_hdimart",
]
keywords = ["hra", "engagement", "wellness", "activity", "step",
            "meal", "mood", "log", "vytal", "managed"]

for schema in schemas_to_check:
    try:
        df = q(f"SHOW TABLES IN deltalake.{schema}")
        matches = [r.iloc[0] for _, r in df.iterrows()
                   if any(kw in str(r.iloc[0]).lower() for kw in keywords)]
        if matches:
            print(f"\n  deltalake.{schema}:")
            for m in matches:
                print(f"    {m}")
    except Exception as e:
        print(f"  {schema}: {e}")

# ── 10. HbA1c data check for one VYTAL user ──────────────────────────────────
section("10. HbA1c LAB DATA — ONE VYTAL USER")
try:
    # Get one VYTAL phr_id
    pid_df = q(f"""
        SELECT DISTINCT phr_id
        FROM deltalake.dl_standard_customermart.d_policy
        WHERE product_code IN ({VYTAL})
        LIMIT 1
    """)
    if not pid_df.empty:
        sample_phr = pid_df.iloc[0]["phr_id"]
        print(f"  Sample phr_id: {sample_phr[:8]}***  (truncated for privacy)")

        df = q(f"""
            SELECT
                l.loinc_id,
                l.test_name,
                l.value,
                l.units,
                c.created_at
            FROM deltalake.dl_standard_customermart.f_claim a
            LEFT JOIN deltalake.dl_central_hrxlabs.customers c ON a.orderid = c.order_id
            LEFT JOIN deltalake.dl_central_health_vault.phr_lab_parsed_data_parsed_data_results_readings l
                   ON a.orderid = l.transaction_id
            WHERE c.phr_id = '{sample_phr}'
              AND a.product_code IN ({VYTAL})
              AND l.loinc_id IN ('4548-4','59261-8')
            ORDER BY c.created_at DESC
            LIMIT 5
        """)
        if df.empty:
            print("  No HbA1c results found for this user.")
        else:
            print(df.to_string(index=False))
except Exception as e:
    print(f"ERROR: {e}")

print("\n\nDONE — paste this entire output back to Claude.")
