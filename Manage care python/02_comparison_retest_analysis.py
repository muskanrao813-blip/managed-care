?"""
============================================================
MANAGED CARE 3.0 ??" SCRIPT 2: Year-on-Year Retest Comparison
============================================================
Comparison logic (updated):
  Retested = previous year PURELIFE policyholders who attended current year camp.

  2025 base year:
    - Previous policyholders : PURELIFE1-5, d_policy Jun 2024 ??" Apr 2025
    - Previous camp tests     : BFLPL codes  Feb 2024 ??" Mar 2025
    - Current camp tests      : BPC01/02/03 + BFLPURE01/02  Apr 2025 ??" Mar 2026
    - Retested                : intersection of prev policyholders ??? current camp attendees

  2026 base year:
    - Previous policyholders : PURELIFE1-5, d_policy May 2025 ??" Apr 2026
    - Previous camp tests    : BPC01/02/03 + BFLPURE01/02  Apr 2025 ??" Mar 2026
    - Current camp tests     : BPC01/02/03  Apr 2026 ??" present
    - Retested               : intersection of prev policyholders ??? current camp attendees

Output:
  data/managed_care_comparison.csv
  data/managed_care_comparison_raw_data.csv
============================================================
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import urllib
from db_layer import save_dataframe

from config import TRINO_HOST, TRINO_USER, TRINO_PASSWORD
TRINO_CONFIG = {
    "user":     TRINO_USER,
    "password": TRINO_PASSWORD,
    "env":      "Prod"
}

LOOKUP_FILE = r"D:\OneDrive - Bajaj Finserv Health Limited\Documents\manage care\Manage care python\Final_BFL_Lookup_THR 5.xlsx"

OUTPUT_DIR = r"D:\OneDrive - Bajaj Finserv Health Limited\Documents\manage care\Manage care python\data"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "managed_care_comparison.csv")

# ?"??"? CAMP YEAR CONFIG ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
# Change SELECTED_CAMP_YEAR to switch between 2025 and 2026 analysis.
SELECTED_CAMP_YEAR = "2026"

PURELIFE_CODES = ["PURELIFE1", "PURELIFE2", "PURELIFE3", "PURELIFE4", "PURELIFE5"]

COMPARISON_CONFIG = {
    "2025": {
        # d_policy: 2024 policyholders (PURELIFE, Jun 2024 ??" Mar 2025)
        "prev_policy_date_from": "2024-06",
        "prev_policy_date_to":   "2025-03",
        # f_claim: 2024 camp tests (BFLPL codes, Apr 2024 ??" Mar 2025)
        "prev_camp_codes":  ["BFLPL01","BFLPL02","BFLPL03","BFLPLH01","BFLPLH02","BFLPL04"],
        "prev_date_from":   "2024-04",
        "prev_date_to":     "2025-03",
        # f_claim: 2025 camp tests (BPC + BFLPURE, Apr 2025 ??" Mar 2026)
        "curr_camp_codes":  ["BPC01","BPC02","BPC03","BFLPURE01","BFLPURE02"],
        "curr_date_from":   "2025-04",
        "curr_date_to":     "2026-03",
    },
    "2026": {
        # d_policy: 2025 policyholders (PURELIFE, May 2025 ??" Apr 2026)
        "prev_policy_date_from": "2025-05",
        "prev_policy_date_to":   "2026-04",
        # f_claim: 2025 camp tests (BPC + BFLPURE, Apr 2025 ??" Mar 2026)
        "prev_camp_codes":  ["BPC01","BPC02","BPC03","BFLPURE01","BFLPURE02"],
        "prev_date_from":   "2025-04",
        "prev_date_to":     "2026-03",
        # f_claim: 2026 camp tests (BPC, Apr 2026 ??" present)
        "curr_camp_codes":  ["BPC01","BPC02","BPC03"],
        "curr_date_from":   "2026-04",
        "curr_date_to":     None,
    },
}

_cfg = COMPARISON_CONFIG[SELECTED_CAMP_YEAR]
_prev_codes_sql = ", ".join(f"'{c}'" for c in _cfg["prev_camp_codes"])
_curr_codes_sql = ", ".join(f"'{c}'" for c in _cfg["curr_camp_codes"])
_prev_date_filter = (
    f"AND substring(cast(d.created_at AS VARCHAR),1,7) >= '{_cfg['prev_date_from']}'"
    f" AND substring(cast(d.created_at AS VARCHAR),1,7) <= '{_cfg['prev_date_to']}'"
)
_curr_upper = (
    f"AND substring(cast(d.created_at AS VARCHAR),1,7) <= '{_cfg['curr_date_to']}'"
    if _cfg["curr_date_to"] else ""
)
_curr_date_filter = (
    f"AND substring(cast(d.created_at AS VARCHAR),1,7) >= '{_cfg['curr_date_from']}'"
    f" {_curr_upper}"
)

print(f"\n{'='*60}")
pass
print(f"  Camp year   : {SELECTED_CAMP_YEAR}")
pass
pass
pass
print(f"{'='*60}")


# ?"??"? EXACT get_trino_engine from comparison notebook ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
def run_trino_query(query: str, config: dict, retry: int = 1):
    """Execute query on Trino ??" same pattern as Script 1 (trino_query) which works."""

    user     = config.get("user")
    password = config.get("password")
    env      = config.get("env", "Prod")

    try:
        if not password:
            print("ERR", "Trino pass is None!")
        if not user:
            print("ERR", "Trino user is None!")

        password_encoded = urllib.parse.quote_plus(str(password))

        connection_url = (
            f"trino://{user}:{password_encoded}@trino-prod.healthrx.co.in:443/system?http_scheme=https"
            if env == "Prod"
            else f"trino://{user}:{password_encoded}@trino-dev.healthrx.co.in:443/system?http_scheme=https"
        )

        engine = create_engine(connection_url)

        with engine.connect() as conn:
            result = conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        engine.dispose()
        return df

    except Exception as e:
        print(f"ERR Failed while executing Trino query: {e}")

        if retry > 0:
            print("INF Attempting to rerun query --")
            return run_trino_query(query, config, retry - 1)

        return None


# ?"??"? Step 1a: Current year camp tests (date-filtered) ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
CURR_QUERY = f"""
SELECT DISTINCT
    d.mobile_number_hash,
    d.order_id,
    a.product_code,
    d.phr_id,
    d.created_at,
    substring(cast(d.created_at as VARCHAR),1,7) as MT,
    b.loinc_id, b.test_name, b.value, b.units, b.provider, d.gender,
    1 as rnk
FROM deltalake.dl_standard_customermart.f_claim a
LEFT JOIN deltalake.dl_central_hrxlabs.customers d ON a.orderid = d.order_id
LEFT JOIN deltalake.dl_central_health_vault.phr_lab_parsed_data_parsed_data_results_readings b
    ON a.orderid = b.transaction_id
WHERE a.product_code IN ({_curr_codes_sql})
  AND b.transaction_id IS NOT NULL
  AND d.report_url IS NOT NULL
  AND d.mobile_number_hash IS NOT NULL
  AND b.loinc_id IS NOT NULL
  {_curr_date_filter}

UNION ALL

SELECT * FROM (
    SELECT DISTINCT
        d.mobile_number_hash, d.order_id, a.product_code, d.phr_id, d.created_at,
        substring(cast(d.created_at as VARCHAR),1,7) as MT,
        p.loinc_id, p.test_name, p.value, p.report_unit as units,
        p.provider_name as provider, d.gender,
        row_number() OVER (PARTITION BY d.order_id, p.loinc_id ORDER BY d.created_at DESC) as rnk
    FROM deltalake.dl_standard_customermart.f_claim a
    LEFT JOIN deltalake.dl_central_hrxlabs.customers d ON a.orderid = d.order_id
    LEFT JOIN deltalake.dl_central_health_vault.phr_lab_parsed_data_parsed_data_results_readings b
        ON a.orderid = b.transaction_id
    LEFT JOIN deltalake.dl_standard_hdimart.labs_severity_model_p01_consolidated p
        ON p.transaction_id = a.orderid
    WHERE a.product_code IN ({_curr_codes_sql})
      AND d.report_url IS NOT NULL AND d.mobile_number_hash IS NOT NULL
      AND b.transaction_id IS NULL AND p.loinc_id IS NOT NULL
      {_curr_date_filter}
) x1 WHERE rnk = 1
"""

# ?"??"? Step 1b: Previous year camp tests (date-filtered) ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
PREV_QUERY = f"""
SELECT DISTINCT
    d.mobile_number_hash,
    d.order_id,
    a.product_code,
    d.phr_id,
    d.created_at,
    substring(cast(d.created_at as VARCHAR),1,7) as MT,
    b.loinc_id, b.test_name, b.value, b.units, b.provider, d.gender,
    1 as rnk
FROM deltalake.dl_standard_customermart.f_claim a
LEFT JOIN deltalake.dl_central_hrxlabs.customers d ON a.orderid = d.order_id
LEFT JOIN deltalake.dl_central_health_vault.phr_lab_parsed_data_parsed_data_results_readings b
    ON a.orderid = b.transaction_id
WHERE a.product_code IN ({_prev_codes_sql})
  AND b.transaction_id IS NOT NULL
  AND d.report_url IS NOT NULL
  AND d.mobile_number_hash IS NOT NULL
  AND b.loinc_id IS NOT NULL
  {_prev_date_filter}

UNION ALL

SELECT * FROM (
    SELECT DISTINCT
        d.mobile_number_hash, d.order_id, a.product_code, d.phr_id, d.created_at,
        substring(cast(d.created_at as VARCHAR),1,7) as MT,
        p.loinc_id, p.test_name, p.value, p.report_unit as units,
        p.provider_name as provider, d.gender,
        row_number() OVER (PARTITION BY d.order_id, p.loinc_id ORDER BY d.created_at DESC) as rnk
    FROM deltalake.dl_standard_customermart.f_claim a
    LEFT JOIN deltalake.dl_central_hrxlabs.customers d ON a.orderid = d.order_id
    LEFT JOIN deltalake.dl_central_health_vault.phr_lab_parsed_data_parsed_data_results_readings b
        ON a.orderid = b.transaction_id
    LEFT JOIN deltalake.dl_standard_hdimart.labs_severity_model_p01_consolidated p
        ON p.transaction_id = a.orderid
    WHERE a.product_code IN ({_prev_codes_sql})
      AND d.report_url IS NOT NULL AND d.mobile_number_hash IS NOT NULL
      AND b.transaction_id IS NULL AND p.loinc_id IS NOT NULL
      {_prev_date_filter}
) x1 WHERE rnk = 1
"""

pass
df_curr = run_trino_query(CURR_QUERY, TRINO_CONFIG)
if df_curr is None:
    pass
pass

pass
df_prev = run_trino_query(PREV_QUERY, TRINO_CONFIG)
if df_prev is None:
    pass
pass

# ?"??"? Step 1c: Fetch previous year PURELIFE policyholders from d_policy ?"??"??"??"??"??"??"??"?
_pl_codes_sql = ", ".join(f"'{c}'" for c in PURELIFE_CODES)
POLICY_QUERY = f"""
SELECT DISTINCT
    personmobilephone_hash          AS mobile_number_hash,
    vlocity_ins_fsc__productcode__c AS mc_product_code
FROM deltalake.dl_standard_customermart.d_policy
WHERE vlocity_ins_fsc__productcode__c IN ({_pl_codes_sql})
  AND personmobilephone_hash IS NOT NULL
  AND (is_test_policy__c = FALSE OR is_test_policy__c IS NULL)
  AND substring(cast(createddate AS VARCHAR), 1, 7) >= '{_cfg["prev_policy_date_from"]}'
  AND substring(cast(createddate AS VARCHAR), 1, 7) <= '{_cfg["prev_policy_date_to"]}'
"""
pass
df_prev_policy = run_trino_query(POLICY_QUERY, TRINO_CONFIG)
if df_prev_policy is None or df_prev_policy.empty:
    pass

prev_policy_hashes = set(df_prev_policy["mobile_number_hash"].dropna()) if not df_prev_policy.empty else set()
pass

# ?"??"? Step 1d: Identify retested users ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?

# Total retested = users who attended BOTH previous camp AND current camp
#                  (these are the population with before/after biomarker data)

# MC retested   = total retested ??? prev year PURELIFE policyholders
#                 (tagged in Step 5b via d_policy lookup)

# Non-MC retested = total retested ??' MC retested
#                   (comparison group for the improvement pivot)

curr_hashes      = set(df_curr["mobile_number_hash"].dropna())
prev_camp_hashes = set(df_prev["mobile_number_hash"].dropna())
retested_hashes  = curr_hashes & prev_camp_hashes

mc_in_policy     = retested_hashes & prev_policy_hashes
non_mc           = retested_hashes - prev_policy_hashes

print(f"\n  Current camp attendees             : {len(curr_hashes):,}")
print(f"  Previous camp attendees            : {len(prev_camp_hashes):,}")
print(f"  Total retested (both camps)        : {len(retested_hashes):,}")
print(f"  Prev year PURELIFE policyholders   : {len(prev_policy_hashes):,}")
pass
print(f"  Non-MC retested                    : {len(non_mc):,}")

if not retested_hashes:
    pass

# ?"??"? Step 1e: Build combined biomarker dataset ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
df_curr_retested = df_curr[df_curr["mobile_number_hash"].isin(retested_hashes)].copy()
df_prev_retested = df_prev[df_prev["mobile_number_hash"].isin(retested_hashes)].copy()
df = pd.concat([df_prev_retested, df_curr_retested], ignore_index=True)
print(f"\n[Step 1e] Combined dataset for retested users:")
print(f"  {len(df):,} rows | {df['mobile_number_hash'].nunique():,} unique retested users")


# ?"??"? CELL 3: Load Lookups ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
pass
print(f"  Camp year : {SELECTED_CAMP_YEAR}")

LOOKUP_FILE_PATH = LOOKUP_FILE

SHEETS = {
    "redcliffe": "Redcliffe",
    "thyrocare": "Thyrocare",
    "healthians": "Healthians",
    "apollo":    "Apollo",
    "jehangir":  "Jehangir"
}

STANDARD_COLUMNS = [
    'impact', 'test_name', 'cos', 'loinc_id',
    'inclusion_considered_for_plan_stamping',
    'value', 'gender', 'lower_bound', 'upper_bound',
    'operator', 'lower_bound.1', 'upper_bound.1',
    'outcome', 'outcome_value', 'units'
]

FINAL_COLUMNS = [
    'impact', 'test_name', 'cos', 'loinc_id',
    'value', 'gender', 'operator',
    'lower_bound.1', 'upper_bound.1',
    'outcome', 'outcome_value', 'units'
]

RENAME_MAP = {
    'test_name':     'lkp_test_name',
    'value':         'lkp_value',
    'gender':        'lkp_gender',
    'lower_bound.1': 'lower_bound',
    'upper_bound.1': 'upper_bound',
    'units':         'lkp_units'
}


def load_lookup(sheet_name: str) -> pd.DataFrame:
    """Load and standardize a single lookup sheet"""

    df = pd.read_excel(LOOKUP_FILE_PATH, sheet_name=sheet_name)

    # Standardize column names
    df.columns = STANDARD_COLUMNS

    # Select required columns
    df = df[FINAL_COLUMNS]

    # Rename columns
    df = df.rename(columns=RENAME_MAP)

    return df


lookups = {}
for key, sheet in SHEETS.items():
    lookups[key] = load_lookup(sheet)

lkp_r = lookups["redcliffe"]
lkp_t = lookups["thyrocare"]
lkp_h = lookups["healthians"]
lkp_a = lookups["apollo"]
lkp_j = lookups["jehangir"]

pass


# ?"??"? CELL 5: Provider Mapping + Merge ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
pass

PROVIDER_MAP = {
    "{'name': 'Thyrocare'}": "thyrocare",
    "{'name': 'Thyrocare Technologies Limited'}": "thyrocare",
    "{'name': 'Healthians'}": "healthians",
    "Apollo Health and Lifestyle Limited": "apollo",
    "Jehangir Hospital": "jehangir"
}

DEFAULT_PROVIDER = "redcliffe"


def assign_provider(df: pd.DataFrame) -> pd.DataFrame:
    """Map raw provider names to standardized provider keys"""

    df = df.copy()
    df["provider_clean"] = df["provider"].map(PROVIDER_MAP).fillna(DEFAULT_PROVIDER)

    return df


def merge_with_lookup(df: pd.DataFrame, lookups: dict) -> pd.DataFrame:
    """Merge dataframe with respective lookup based on provider"""

    merged_dfs = []

    for provider_key, lkp_df in lookups.items():

        df_subset = df[df["provider_clean"] == provider_key]

        if df_subset.empty:
            continue

        merged = df_subset.merge(
            lkp_df,
            left_on=["loinc_id", "gender"],
            right_on=["loinc_id", "lkp_gender"],
            how="inner"
        )

        merged_dfs.append(merged)

    return pd.concat(merged_dfs, ignore_index=True)


df = assign_provider(df)
df_merged = merge_with_lookup(df, lookups)

# Data Type Cleaning
NUMERIC_COLS = ["value", "lower_bound", "upper_bound"]
for col in NUMERIC_COLS:
    df_merged[col] = pd.to_numeric(df_merged[col], errors="coerce")

# Range Filtering
df_filtered = df_merged[
    df_merged["value"].notna() &
    df_merged["lower_bound"].notna() &
    df_merged["upper_bound"].notna() &
    (df_merged["value"] >= df_merged["lower_bound"]) &
    (df_merged["value"] <= df_merged["upper_bound"])
]
pass


# ?"??"? CELL 8: Retest Filter + Earliest/Latest Extraction ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
pass
# Retested users were already identified in Step 1d (prev policy ??? curr camp).
# Here we additionally require they have the same loinc in BOTH year periods
# so we can compute a meaningful biomarker comparison.
df_retests = df_filtered[
    df_filtered.groupby(["mobile_number_hash", "loinc_id"])["loinc_id"]
    .transform("count") > 1
].copy()

pass

# Earliest & Latest
df_sorted = df_retests.sort_values(by="created_at")

df_earliest = df_sorted.drop_duplicates(
    subset=["mobile_number_hash", "loinc_id"], keep="first"
).copy()

df_latest = df_sorted.drop_duplicates(
    subset=["mobile_number_hash", "loinc_id"], keep="last"
).copy()

# Rename Columns ??" Earliest
df_earliest = df_earliest.rename(columns={
    "value":         "earliest_value",
    "order_id":      "earliest_order_id",
    "created_at":    "earliest_created_at",
    "outcome":       "earliest_outcome",
    "outcome_value": "earliest_outcome_value"
})

# Rename Columns ??" Latest
df_latest = df_latest.rename(columns={
    "value":         "latest_value",
    "order_id":      "latest_order_id",
    "created_at":    "latest_created_at",
    "lower_bound":   "latest_lower_bound",
    "upper_bound":   "latest_upper_bound",
    "outcome":       "latest_outcome",
    "outcome_value": "latest_outcome_value"
})

# Merge Earliest + Latest
df_final = df_earliest.merge(
    df_latest[[
        "mobile_number_hash", "loinc_id",
        "latest_value", "latest_order_id", "latest_created_at",
        "latest_lower_bound", "latest_upper_bound",
        "latest_outcome", "latest_outcome_value"
    ]],
    on=["mobile_number_hash", "loinc_id"],
    how="inner"
)

# Format Dates
df_final["earliest_created_at"] = pd.to_datetime(df_final["earliest_created_at"]).dt.strftime("%Y-%m-%d")
df_final["latest_created_at"]   = pd.to_datetime(df_final["latest_created_at"]).dt.strftime("%Y-%m-%d")

# Calculations ??" updated outcome
def calc_updated(value, outcome, outcome_value, lower_bound, upper_bound):

    if pd.isna(value):
        return None

    if outcome in ['Low', 'Borderline Low']:
        return outcome_value + ((upper_bound - value) / upper_bound)

    elif outcome in ['High', 'Borderline High']:
        return outcome_value + ((value - lower_bound) / lower_bound)

    else:
        return outcome_value


# Earliest (uses earliest bounds)
df_final["earliest_updated_outcome"] = df_final.apply(
    lambda row: calc_updated(
        row["earliest_value"],
        row["earliest_outcome"],
        row["earliest_outcome_value"],
        row["lower_bound"],
        row["upper_bound"]
    ),
    axis=1
)

# Latest (uses latest bounds ??" FIXED from notebook)
df_final["latest_updated_outcome"] = df_final.apply(
    lambda row: calc_updated(
        row["latest_value"],
        row["latest_outcome"],
        row["latest_outcome_value"],
        row["latest_lower_bound"],
        row["latest_upper_bound"]
    ),
    axis=1
)

# COS Calculations
df_final["earliest_Outcome_COS"] = df_final["earliest_updated_outcome"] * df_final["cos"]
df_final["latest_Outcome_COS"]   = df_final["latest_updated_outcome"]   * df_final["cos"]

# Final Columns ??" exactly as notebook
df_final = df_final[[
    'mobile_number_hash', 'product_code', 'phr_id',
    'loinc_id', 'test_name', 'units', 'gender', 'rnk',
    'impact', 'lkp_test_name', 'cos', 'operator',

    # Earliest bounds
    'lower_bound', 'upper_bound',

    # Latest bounds
    'latest_lower_bound', 'latest_upper_bound',

    'lkp_units',

    'earliest_created_at',
    'latest_created_at',

    'earliest_order_id',
    'latest_order_id',

    'earliest_value',
    'latest_value',

    'earliest_outcome',
    'latest_outcome',

    'earliest_outcome_value',
    'latest_outcome_value',

    'earliest_updated_outcome',
    'latest_updated_outcome',

    'earliest_Outcome_COS',
    'latest_Outcome_COS'
]]
pass


# ?"??"? CELL 9: Row-level Improvement Flag ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
pass

df_final["improvement_flag"] = np.where(
    # Special case: no signal at all
    (df_final["earliest_updated_outcome"] == 0) &
    (df_final["latest_updated_outcome"] == 0),
    "No Risk",

    # Improved (lower is better)
    np.where(
        df_final["latest_updated_outcome"] < df_final["earliest_updated_outcome"],
        "Improved",

        # Worsened
        np.where(
            df_final["latest_updated_outcome"] > df_final["earliest_updated_outcome"],
            "Worsened",

            # Same but non-zero
            "No Change"
        )
    )
)


# ?"??"? STEP 5b: Managed Care Programme Flag ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
# Out of all retested users, check who had a managed care policy in:

#   2025 (PURELIFE codes):
#     PURELIFE1 ??' Diabetes Management
#     PURELIFE2 ??' Dyslipidemia Management
#     PURELIFE3 ??' Thyroid Care
#     PURELIFE4 ??' Liver Care
#     PURELIFE5 ??' Kidney Care

#   2026 (VYTAL codes):
#     VYTAL0126 ??' Diabetes Management
#     VYTAL0226 ??' Dyslipidemia Management
#     VYTAL0326 ??' Thyroid Care
#     VYTAL0426 ??' Liver Care
#     VYTAL0526 ??' Kidney Care

# A user is tagged managed_care_flag = Y if they had a policy in EITHER year.
# managed_care_year tells us which year (2025 / 2026 / Both).
pass

# ?"??"? Product ??' Programme mapping ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
PRODUCT_PROGRAM_MAP = {
    # 2025 policies
    'PURELIFE1': 'Diabetes Management',
    'PURELIFE2': 'Dyslipidemia Management',
    'PURELIFE3': 'Thyroid Care',
    'PURELIFE4': 'Liver Care',
    'PURELIFE5': 'Kidney Care',
    # 2026 policies - codes 01-05 (VYTAL0326=Liver, VYTAL0426=Kidney, VYTAL0526=Thyroid)
    'VYTAL0126': 'Diabetes Management',
    'VYTAL0226': 'Dyslipidemia Management',
    'VYTAL0326': 'Liver Care',
    'VYTAL0426': 'Kidney Care',
    'VYTAL0526': 'Thyroid Care',
    # 2026 policies - codes 06-10
    'VYTAL0626': 'Diabetes Management',
    'VYTAL0726': 'Dyslipidemia Management',
    'VYTAL0826': 'Liver Care',
    'VYTAL0926': 'Kidney Care',
    'VYTAL1026': 'Thyroid Care',
}

# Check managed care using retested users mobile hashes directly
# We already have all retested users in df_final with their mobile_number_hash.
# Query d_policy directly using mobile hashes ??" no orderid join needed.
# d_policy has mobile_number_hash for managed care product purchases.

retest_hashes = df_final['mobile_number_hash'].dropna().unique().tolist()
print(f'  Checking {len(retest_hashes):,} retested mobile hashes in d_policy...')

CHUNK_SIZE = 1000
mc_chunks  = []

for i in range(0, len(retest_hashes), CHUNK_SIZE):
    chunk         = retest_hashes[i : i + CHUNK_SIZE]
    hash_list     = ', '.join(f"'{h}'" for h in chunk)
    batch_num     = i // CHUNK_SIZE + 1
    total_batches = -(-len(retest_hashes) // CHUNK_SIZE)

    # Source: d_policy table ??" has mobile_number_hash for managed care products
    # Columns used:
    #   mobile_number_hash  ??" user identifier (same hash used in camp data)
    #   vlocity_ins_fsc__productcode__c ??" PURELIFE1-5 (2025) or VYTAL0126-0526 (2026)
    #   created_at          ??" policy purchase date (used to extract year)
    # If column names differ in d_policy, update them here only.
    # Tag using PREVIOUS year policy dates so the programme reflects last year's enrolment
    mc_q = (
        f"SELECT DISTINCT "
        f"personmobilephone_hash AS mobile_number_hash, "
        f"vlocity_ins_fsc__productcode__c AS mc_product_code, "
        f"substring(cast(createddate AS VARCHAR), 1, 4) AS mc_year "
        f"FROM deltalake.dl_standard_customermart.d_policy "
        f"WHERE personmobilephone_hash IN ({hash_list}) "
        f"AND vlocity_ins_fsc__productcode__c IN ({_pl_codes_sql}) "
        f"AND personmobilephone_hash IS NOT NULL "
        f"AND (is_test_policy__c = FALSE OR is_test_policy__c IS NULL) "
        f"AND substring(cast(createddate AS VARCHAR), 1, 7) >= '{_cfg['prev_policy_date_from']}' "
        f"AND substring(cast(createddate AS VARCHAR), 1, 7) <= '{_cfg['prev_policy_date_to']}'"
    )


    df_chunk = run_trino_query(mc_q, TRINO_CONFIG)
    rows = len(df_chunk) if df_chunk is not None else 0
    print(f'  Batch {batch_num}/{total_batches} - {rows} rows found')
    if df_chunk is not None and not df_chunk.empty:
        mc_chunks.append(df_chunk)

if mc_chunks:
    df_mc = pd.concat(mc_chunks, ignore_index=True)

    df_mc['managed_care_program'] = df_mc['mc_product_code'].map(PRODUCT_PROGRAM_MAP)

    mc_years = (
        df_mc.groupby('mobile_number_hash')['mc_year']
        .apply(lambda x: sorted(x.unique().tolist()))
        .reset_index()
        .rename(columns={'mc_year': 'mc_years_list'})
    )
    mc_years['managed_care_year'] = mc_years['mc_years_list'].apply(
        lambda yrs: 'Both' if ('2025' in yrs and '2026' in yrs)
                    else ('2025' if '2025' in yrs else '2026')
    )

    mc_latest = (
        df_mc.sort_values('mc_year', ascending=False)
        .drop_duplicates('mobile_number_hash', keep='first')
        [['mobile_number_hash', 'mc_product_code', 'managed_care_program']]
    )

    df_mc_final = mc_latest.merge(
        mc_years[['mobile_number_hash', 'managed_care_year']],
        on='mobile_number_hash', how='left'
    )
    df_mc_final['managed_care_flag'] = 'Y'

    df_mc_final['policy_cohort'] = None  # Cohort__c not available in d_policy

    df_final = df_final.merge(
        df_mc_final[['mobile_number_hash', 'managed_care_flag',
                     'managed_care_program', 'mc_product_code', 'managed_care_year',
                     'policy_cohort']],
        on='mobile_number_hash', how='left'
    )
    df_final['managed_care_flag']    = df_final['managed_care_flag'].fillna('N')
    df_final['managed_care_program'] = df_final['managed_care_program'].fillna('None')
    df_final['mc_product_code']      = df_final['mc_product_code'].fillna('None')
    df_final['managed_care_year']    = df_final['managed_care_year'].fillna('None')

    mc_users     = df_final[df_final['managed_care_flag'] == 'Y']['mobile_number_hash'].nunique()
    total_retest = df_final['mobile_number_hash'].nunique()

    print(f'\n  Results:')
    print(f'    Total retested users        : {total_retest:,}')
    print(f'    Had managed care (any year) : {mc_users:,} ({mc_users/total_retest*100:.1f}%)')
    print(f'    No managed care             : {total_retest - mc_users:,} ({(total_retest-mc_users)/total_retest*100:.1f}%)')
    print('\n  Programme breakdown (retested + managed care):')
    print(df_final[df_final['managed_care_flag']=='Y']['managed_care_program'].value_counts().to_string())
    print('\n  Year breakdown (retested + managed care):')
    print(df_final[df_final['managed_care_flag']=='Y']['managed_care_year'].value_counts().to_string())

else:
    print('  No retested users found with PURELIFE/VYTAL in d_policy')
    df_final['managed_care_flag']    = 'N'
    df_final['managed_care_program'] = 'None'
    df_final['mc_product_code']      = 'None'
    df_final['managed_care_year']    = 'None'






# ?"??"? STEP 5c: Appointment Count (non-critical ??" wrapped so CSV always saves) ?"??"??"?
LAST_YEAR_START = "2025-05-01"
LAST_YEAR_END   = "2026-05-31"
THIS_YEAR_START = "2026-06-01"
APPT_CHUNK_SIZE = 1000


def fetch_appts_for_period(hashes_list, start_date, end_date=None):
    end_filter_appt = f"AND SUBSTR(CAST(appointmentdate AS VARCHAR), 1, 10) <= '{end_date}'" if end_date else ""
    end_filter_lab  = f"AND CAST(d.created_at AS DATE) <= DATE '{end_date}'" if end_date else ""
    chunks = []
    total_batches = -(-len(hashes_list) // APPT_CHUNK_SIZE)
    for i in range(0, len(hashes_list), APPT_CHUNK_SIZE):
        chunk      = hashes_list[i : i + APPT_CHUNK_SIZE]
        hashes_sql = ", ".join(f"'{h}'" for h in chunk)
        batch_num  = i // APPT_CHUNK_SIZE + 1
        q = f"""
SELECT
    encodedphonenumber                              AS mobile_number_hash,
    appointmentid                                   AS appt_id,
    appointmentcategory                             AS appt_type,
    SUBSTR(CAST(appointmentdate AS VARCHAR), 1, 10) AS appt_date,
    appointmentstatus                               AS appt_status,
    'appointment'                                   AS appt_source
FROM deltalake.dl_standard_pbireporting.f_appointmentflattable
WHERE encodedphonenumber IN ({hashes_sql})
  AND SUBSTR(CAST(appointmentdate AS VARCHAR), 1, 10) >= '{start_date}' {end_filter_appt}
  AND appointmentstatus != 'Cancelled'
UNION ALL
SELECT
    d.mobile_number_hash                            AS mobile_number_hash,
    d.order_id                                      AS appt_id,
    'Lab Test'                                      AS appt_type,
    CAST(CAST(d.created_at AS DATE) AS VARCHAR)     AS appt_date,
    'Completed'                                     AS appt_status,
    'lab'                                           AS appt_source
FROM deltalake.dl_central_hrxlabs.customers d
WHERE d.mobile_number_hash IN ({hashes_sql})
  AND d.mobile_number_hash IS NOT NULL
  AND CAST(d.created_at AS DATE) >= DATE '{start_date}' {end_filter_lab}
"""
        df_chunk = run_trino_query(q, TRINO_CONFIG)
        rows = len(df_chunk) if df_chunk is not None else 0
        pass
        if df_chunk is not None and not df_chunk.empty:
            chunks.append(df_chunk)
    if chunks:
        result = pd.concat(chunks, ignore_index=True)
        result['appt_date'] = pd.to_datetime(result['appt_date'], errors='coerce')
        return result
    return None


def agg_appts(df_appts, suffix):
    if df_appts is None or df_appts.empty:
        return pd.DataFrame(columns=["mobile_number_hash"])
    agg = df_appts.groupby("mobile_number_hash").agg(
        **{f"total_appts_{suffix}":     ("appt_id",     "count")},
        **{f"appts_completed_{suffix}": ("appt_status", lambda x: (x == "Completed").sum())},
        **{f"lab_tests_{suffix}":       ("appt_source", lambda x: (x == "lab").sum())},
        **{f"clinic_appts_{suffix}":    ("appt_source", lambda x: (x == "appointment").sum())},
    ).reset_index()
    agg[f"had_appt_{suffix}"] = (agg[f"total_appts_{suffix}"] > 0).map({True:"Y", False:"N"})
    return agg


pass
try:
    retest_hashes_for_appt = df_final["mobile_number_hash"].dropna().unique().tolist()

    pass
    df_appts_ly = fetch_appts_for_period(retest_hashes_for_appt, LAST_YEAR_START, LAST_YEAR_END)
    appt_agg_ly = agg_appts(df_appts_ly, suffix="ly")

    pass
    df_appts_ty = fetch_appts_for_period(retest_hashes_for_appt, THIS_YEAR_START)
    appt_agg_ty = agg_appts(df_appts_ty, suffix="ty")

    df_final = df_final.merge(appt_agg_ly, on="mobile_number_hash", how="left")
    df_final = df_final.merge(appt_agg_ty, on="mobile_number_hash", how="left")

    for col in ["total_appts_ly","appts_completed_ly","lab_tests_ly","clinic_appts_ly",
                "total_appts_ty","appts_completed_ty","lab_tests_ty","clinic_appts_ty"]:
        if col in df_final.columns:
            df_final[col] = df_final[col].fillna(0).astype(int)
    for col in ["had_appt_ly","had_appt_ty"]:
        if col in df_final.columns:
            df_final[col] = df_final[col].fillna("N")
    if 'policy_cohort' in df_final.columns:
        df_final['policy_cohort'] = df_final['policy_cohort'].fillna('None')

    mc_total  = df_final[df_final["managed_care_flag"]=="Y"]["mobile_number_hash"].nunique()
    non_total = df_final[df_final["managed_care_flag"]=="N"]["mobile_number_hash"].nunique()
    if mc_total > 0 and "had_appt_ly" in df_final.columns and "had_appt_ty" in df_final.columns:
        mc_ly = df_final[(df_final["managed_care_flag"]=="Y") & (df_final["had_appt_ly"]=="Y")]["mobile_number_hash"].nunique()
        mc_ty = df_final[(df_final["managed_care_flag"]=="Y") & (df_final["had_appt_ty"]=="Y")]["mobile_number_hash"].nunique()
        print(f"  MC: last year appt {mc_ly:,}/{mc_total:,} | this year {mc_ty:,}/{mc_total:,}")
    if non_total > 0 and "had_appt_ly" in df_final.columns and "had_appt_ty" in df_final.columns:
        nm_ly = df_final[(df_final["managed_care_flag"]=="N") & (df_final["had_appt_ly"]=="Y")]["mobile_number_hash"].nunique()
        nm_ty = df_final[(df_final["managed_care_flag"]=="N") & (df_final["had_appt_ty"]=="Y")]["mobile_number_hash"].nunique()
        print(f"  Non-MC: last year {nm_ly:,}/{non_total:,} | this year {nm_ty:,}/{non_total:,}")

except Exception as _appt_err:
    pass
    for col in ["total_appts_ly","appts_completed_ly","lab_tests_ly","clinic_appts_ly",
                "total_appts_ty","appts_completed_ty","lab_tests_ty","clinic_appts_ty"]:
        if col not in df_final.columns:
            df_final[col] = 0
    for col in ["had_appt_ly","had_appt_ty"]:
        if col not in df_final.columns:
            df_final[col] = "N"


# ?"??"? CELL 12: Grouped Scores per (user ?- impact) ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
pass

grouped = df_final.groupby(['mobile_number_hash', 'impact']).agg(
    total_score_latest=('latest_Outcome_COS', 'sum'),
    num_tests_latest=('latest_Outcome_COS', 'count'),

    total_score_earliest=('earliest_Outcome_COS', 'sum'),
    num_tests_earliest=('earliest_Outcome_COS', 'count')
).reset_index()

# Add latest_camp_date (YYYY-MM from df_curr) ??" dashboard filters by this
_date_map = (
    df_curr_retested.groupby('mobile_number_hash')['created_at']
                    .max().reset_index()
)
_date_map['latest_camp_date'] = (
    pd.to_datetime(_date_map['created_at'], errors='coerce')
      .dt.strftime('%Y-%m')
)
grouped = grouped.merge(
    _date_map[['mobile_number_hash', 'latest_camp_date']],
    on='mobile_number_hash', how='left'
)

# Normalize
grouped['normalized_latest'] = np.where(
    grouped['num_tests_latest'] > 0,
    grouped['total_score_latest'] / np.log1p(grouped['num_tests_latest']),
    0
)

grouped['normalized_earliest'] = np.where(
    grouped['num_tests_earliest'] > 0,
    grouped['total_score_earliest'] / np.log1p(grouped['num_tests_earliest']),
    0
)

# Score Change
grouped['score_change'] = (
    grouped['normalized_latest'] - grouped['normalized_earliest']
)

# Group-level Improvement Flag
grouped['improvement_flag'] = np.where(
    # Special case: No risk at all
    (grouped['normalized_earliest'] == 0) & (grouped['normalized_latest'] == 0),
    "No Risk",

    # Improved (lower is better)
    np.where(
        grouped['normalized_latest'] < grouped['normalized_earliest'],
        "Improved",

        # Worsened
        np.where(
            grouped['normalized_latest'] > grouped['normalized_earliest'],
            "Worsened",

            # Same but non-zero
            "No Change"
        )
    )
)

# Add managed care flag + appointment columns to grouped (per-user columns, take first)
APPT_COLS = [
    'total_appts_ly','appts_completed_ly','lab_tests_ly','clinic_appts_ly','had_appt_ly',
    'total_appts_ty','appts_completed_ty','lab_tests_ty','clinic_appts_ty','had_appt_ty',
]
mc_col_list = ['mobile_number_hash','managed_care_flag',
               'managed_care_program','mc_product_code','managed_care_year']
if 'policy_cohort' in df_final.columns:
    mc_col_list.append('policy_cohort')
# Add only those appt columns that exist in df_final
for _ac in APPT_COLS:
    if _ac in df_final.columns:
        mc_col_list.append(_ac)

managed_care_cols = (
    df_final[mc_col_list]
    .drop_duplicates('mobile_number_hash')
)
grouped = grouped.merge(managed_care_cols, on='mobile_number_hash', how='left')

# Ensure all appointment columns exist (fill 0/N if missing after merge)
for _ac in APPT_COLS:
    if _ac not in grouped.columns:
        grouped[_ac] = 0 if 'had' not in _ac else 'N'
if 'policy_cohort' not in grouped.columns:
    grouped['policy_cohort'] = None

# Final output columns
final_scores = grouped[[
    'mobile_number_hash',
    'impact',
    'managed_care_flag',
    'managed_care_program',
    'mc_product_code',
    'managed_care_year',
    'policy_cohort',
    'total_appts_ly','appts_completed_ly','lab_tests_ly','clinic_appts_ly','had_appt_ly',
    'total_appts_ty','appts_completed_ty','lab_tests_ty','clinic_appts_ty','had_appt_ty',
    'normalized_earliest',
    'normalized_latest',
    'score_change',
    'improvement_flag',
    'latest_camp_date'
]]

pass
print("\n  Improvement flag breakdown:")
print(final_scores['improvement_flag'].value_counts().to_string())


# ?"??"? Save Outputs ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
pass

# Output 1: RAW DATA
# df_final = one row per user ?- loinc_id (test)
# Columns: mobile_number_hash, product_code, phr_id,
#          loinc_id, test_name, units, gender, rnk,
#          impact, lkp_test_name, cos, operator,
#          lower_bound, upper_bound, latest_lower_bound, latest_upper_bound,
#          lkp_units,
#          earliest_created_at, latest_created_at,
#          earliest_order_id, latest_order_id,
#          earliest_value, latest_value,
#          earliest_outcome, latest_outcome,
#          earliest_outcome_value, latest_outcome_value,
#          earliest_updated_outcome, latest_updated_outcome,
#          earliest_Outcome_COS, latest_Outcome_COS,
#          improvement_flag
raw_data_file = os.path.join(OUTPUT_DIR, "managed_care_comparison_raw_data.csv")
df_final.to_csv(raw_data_file, index=False)
pass
pass  # print skipped

# Output 2: GROUPED SCORES
# final_scores = one row per user ?- impact
# Columns: mobile_number_hash, impact,
#          normalized_earliest, normalized_latest,
#          score_change, improvement_flag
# Save current year file (e.g. managed_care_comparison_2026.csv)
year_file = os.path.join(OUTPUT_DIR, f"managed_care_comparison_{SELECTED_CAMP_YEAR}.csv")
final_scores.to_csv(year_file, index=False)
save_dataframe(final_scores, "comparison_retest", if_exists="replace")
pass
pass

# Merge all available year files into managed_care_comparison.csv (dashboard master)
year_dfs = []
for yr in ["2025", "2026"]:
    yf = os.path.join(OUTPUT_DIR, f"managed_care_comparison_{yr}.csv")
    if os.path.exists(yf):
        _yd = pd.read_csv(yf, low_memory=False)
        year_dfs.append(_yd)
        print(f"  Including {yr} data: {_yd['mobile_number_hash'].nunique():,} users")

if year_dfs:
    master = pd.concat(year_dfs, ignore_index=True)
    master.to_csv(OUTPUT_FILE, index=False)
    pass
    print(f"     Total: {master['mobile_number_hash'].nunique():,} unique users across all camp years")
else:
    final_scores.to_csv(OUTPUT_FILE, index=False)
    pass

pass  # print skipped


# ?"??"? CELL 16: User counts at each step (debug helper) ?"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"??"?
def count_users(df, name):
    print(f"  {name}: {df['mobile_number_hash'].nunique():,} unique users")

print("\n[Debug] User counts at each pipeline step:")
count_users(df,            "Step 0: Raw Data")
count_users(df_merged,     "Step 1: After Lookup Merge")
count_users(df_filtered,   "Step 2: After Range Filter")
count_users(df_retests,    "Step 3: After Retest Filter")
count_users(df_final,      "Step 4: After Earliest/Latest + COS Filter")
count_users(final_scores,  "Step 5: Final Scores")
















