"""
Run this to find the exact column name for benefit/claim type in f_claim.
Paste the full output back to Claude.

Usage:
    cd care_ai_engine
    python discover_fclaim_columns.py
"""

import urllib.parse, pandas as pd
from sqlalchemy import create_engine, text

USER = "vasu.verma"
PASS = urllib.parse.quote_plus("vvaass6543")
URL  = f"trino://{USER}:{PASS}@trino-prod.healthrx.co.in:443/system?http_scheme=https"

def q(sql):
    engine = create_engine(URL)
    with engine.begin() as con:
        df = pd.read_sql(text(sql), con)
    engine.dispose()
    return df

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# ── 1. All columns in f_claim ─────────────────────────────────────────────────
section("1. ALL COLUMNS IN f_claim")
try:
    df = q("DESCRIBE deltalake.dl_standard_customermart.f_claim")
    print(df.to_string(index=False))
except Exception as e:
    print(f"ERROR: {e}")

# ── 2. One VYTAL row — see all values ─────────────────────────────────────────
section("2. SAMPLE VYTAL ROW (all column values)")
try:
    df = q("""
        SELECT * FROM deltalake.dl_standard_customermart.f_claim
        WHERE product_code IN ('VYTAL0126','VYTAL0626')
        LIMIT 1
    """)
    print("Columns:", list(df.columns))
    if not df.empty:
        for col in df.columns:
            print(f"  {col:45s} = {repr(str(df[col].iloc[0]))[:70]}")
except Exception as e:
    print(f"ERROR: {e}")

# ── 3. Try common benefit/claim type column candidates ────────────────────────
section("3. DISTINCT VALUES — CANDIDATE COLUMNS")
candidates = [
    "benefit_type", "benefittype", "claim_type", "claimtype",
    "service_type", "servicetype", "benefit_category", "claim_category",
    "benefit_name", "benefit_code", "sub_product_code", "claim_subtype",
    "order_type", "ordertype", "transaction_type",
    "vlocity_ins_fsc__benefittype__c", "vlocity_ins_fsc__claimtype__c",
    "vlocity_ins_fsc__servicetype__c",
]
found = []
for col in candidates:
    try:
        df = q(f"""
            SELECT '{col}' AS col_name, CAST({col} AS VARCHAR) AS val, COUNT(*) AS cnt
            FROM deltalake.dl_standard_customermart.f_claim
            WHERE product_code IN ('VYTAL0126','VYTAL0626')
            GROUP BY {col}
            ORDER BY cnt DESC
            LIMIT 10
        """)
        if not df.empty:
            print(f"\n  FOUND: '{col}'")
            print(df.to_string(index=False))
            found.append(col)
    except Exception:
        pass   # column doesn't exist

if not found:
    print("\n  None of the candidates matched. Printing full column list again:")
    try:
        df = q("DESCRIBE deltalake.dl_standard_customermart.f_claim")
        for _, row in df.iterrows():
            print(f"  {row.iloc[0]:45s}  [{row.iloc[1]}]")
    except Exception as e:
        print(f"  ERROR: {e}")

# ── 4. f_appointmentflattable columns ─────────────────────────────────────────
section("4. f_appointmentflattable — ALL COLUMNS + SAMPLE ROW")
try:
    df = q("DESCRIBE deltalake.dl_standard_pbireporting.f_appointmentflattable")
    print(df.to_string(index=False))
except Exception as e:
    print(f"ERROR: {e}")

try:
    df = q("""
        SELECT * FROM deltalake.dl_standard_pbireporting.f_appointmentflattable
        LIMIT 1
    """)
    print("\nSample row:")
    if not df.empty:
        for col in df.columns:
            print(f"  {col:45s} = {repr(str(df[col].iloc[0]))[:70]}")
except Exception as e:
    print(f"ERROR: {e}")

# ── 5. Distinct appointment_type values ───────────────────────────────────────
section("5. f_appointmentflattable — DISTINCT appointment_type VALUES")
for col in ["appointment_type", "appointmentcategory", "appointmenttype", "type"]:
    try:
        df = q(f"""
            SELECT {col}, COUNT(*) AS cnt
            FROM deltalake.dl_standard_pbireporting.f_appointmentflattable
            GROUP BY {col}
            ORDER BY cnt DESC
            LIMIT 15
        """)
        print(f"\n  Column '{col}' found:")
        print(df.to_string(index=False))
        break
    except Exception:
        pass

# ── 6. HRA table confirmation ─────────────────────────────────────────────────
section("6. HRA TABLE — WHICH PATH IS CORRECT?")
hra_tables = [
    '"phr service".healthriskassessments',
    "deltalake.dl_central_hra.user_health_risk_assessments",
]
for tbl in hra_tables:
    try:
        df = q(f"SELECT * FROM {tbl} LIMIT 1")
        print(f"\n  EXISTS: {tbl}")
        print(f"  Columns: {list(df.columns)}")
        break
    except Exception as e:
        print(f"\n  NOT FOUND: {tbl} → {e}")

print("\n\nDONE — paste this entire output back to Claude.")
