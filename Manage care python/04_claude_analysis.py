"""
============================================================
MANAGED CARE 3.0  SCRIPT 4: Claude AI Analysis
============================================================
Reads CSVs + queries d_policy  computes KPIs  generates
insights  saves data/claude_insights.json

AI provider (tries in order, uses first that works):
  1. Groq     pip install groq  + set GROQ_API_KEY
  2. Gemini   pip install google-generativeai + set GEMINI_API_KEY
  3. Rule-based  always works, no API key needed

Run: python 04_claude_analysis.py
============================================================
"""

import sys
import os
import json
import pandas as pd
import numpy as np

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError for emoji/arrows)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import urllib
from datetime import datetime
from sqlalchemy import create_engine, text
from db_layer import save_dataframe

#  CONFIG 
from config import TRINO_HOST, TRINO_USER, TRINO_PASSWORD
TRINO_CONFIG = {
    "user":     TRINO_USER,
    "password": TRINO_PASSWORD,
    "env":      "Prod"
}

# Auto-detect data folder (handles data/ Data/ DATA/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = None
for _d in ["data", "Data", "DATA"]:
    _p = os.path.join(SCRIPT_DIR, _d)
    if os.path.isdir(_p):
        DATA_DIR = _p
        break
if DATA_DIR is None:
    DATA_DIR = os.path.join(SCRIPT_DIR, "data")
    os.makedirs(DATA_DIR, exist_ok=True)

print(f"Data folder: {DATA_DIR}")

#  SELECTED CAMP YEAR  single control knob 
# "2025"  fiscal year Apr 2025  Mar 2026  |  f_claim: BFLPL*  |  d_policy: PURELIFE
# "2026"  fiscal year Apr 2026  present   |  f_claim: BPC*    |  d_policy: VYTAL
SELECTED_CAMP_YEAR = "2026"

#  CAMP PRODUCT CODES (f_claim)  by fiscal year 
CAMP_CODES_BY_YEAR = {
    "2024": ["BFLPL01","BFLPL02","BFLPL03","BFLPLH01","BFLPLH02","BFLPLH03","BFLPL04"],  # Feb-Jul 2024
    "2025": ["BPC01","BPC02","BPC03","BFLPURE01","BFLPURE02"],                            # Apr 2025  Mar 2026
    "2026": ["BPC01","BPC02","BPC03"],                                                    # Apr 2026 onwards
}

#  FISCAL YEAR DATE RANGES  April to March 
CAMP_DATE_RANGES = {
    "2024": {"from": "2024-02", "to": "2024-07"},
    "2025": {"from": "2025-04", "to": "2026-03"},
    "2026": {"from": "2026-04", "to": None},      # None = no upper limit
}

# Derived constants  change SELECTED_CAMP_YEAR above, not these
_yr_range           = CAMP_DATE_RANGES[SELECTED_CAMP_YEAR]
DATE_FROM           = _yr_range["from"]
DATE_TO             = _yr_range["to"] or "2099-12"
CAMP_CODES_CURRENT  = CAMP_CODES_BY_YEAR[SELECTED_CAMP_YEAR]
CAMP_CODES_PREVIOUS = CAMP_CODES_BY_YEAR["2025"] if SELECTED_CAMP_YEAR == "2026" else []

#  ENROLLMENT DATE RANGES (d_policy)  by fiscal year 
# Distinct from camp dates: enrollment window is when policies were created
ENROLLMENT_DATE_RANGES = {
    "2025": {"from": "2025-06", "to": "2026-05"},   # PURELIFE: Jun 2025  May 2026 (programme assigned Jun 2025)
    "2026": {"from": "2026-06", "to": "2027-05"},   # VYTAL:    Jun 2026  May 2027
}

# Enrollment year follows the selected camp year automatically
ENROLLED_YEAR = SELECTED_CAMP_YEAR

#  POLICY CODES (d_policy)  Total Enrolled 
YEAR_CODES = {
    "2025": ["PURELIFE1","PURELIFE2","PURELIFE3","PURELIFE4","PURELIFE5"],
    "2026": ["VYTAL0126","VYTAL0226","VYTAL0326","VYTAL0426","VYTAL0526",
             "VYTAL0626","VYTAL0726","VYTAL0826","VYTAL0926","VYTAL01026"],
}
SELECTED_YEAR = ENROLLED_YEAR

PRODUCT_PROGRAM = {
    # PURELIFE (2025 policies)
    "PURELIFE1":"Diabetes Management",    "PURELIFE2":"Dyslipidemia Management",
    "PURELIFE3":"Thyroid Care",           "PURELIFE4":"Liver Care",
    "PURELIFE5":"Kidney Care",
    # VYTAL (2026 policies)  codes 0105 per programme
    "VYTAL0126":"Diabetes Management",    "VYTAL0226":"Dyslipidemia Management",
    "VYTAL0326":"Liver Care",             "VYTAL0426":"Kidney Care",
    "VYTAL0526":"Thyroid Care",
    # VYTAL (2026 policies)  codes 0610 per programme
    "VYTAL0626":"Diabetes Management",    "VYTAL0726":"Dyslipidemia Management",
    "VYTAL0826":"Liver Care",             "VYTAL0926":"Kidney Care",
    "VYTAL01026":"Thyroid Care",
    # Programme names (CSV may store names not raw codes)
    "Diabetes Management":"Diabetes Management",
    "Dyslipidemia Management":"Dyslipidemia Management",
    "Thyroid Care":"Thyroid Care",
    "Liver Care":"Liver Care",
    "Kidney Care":"Kidney Care",
}

ALL_MC_IDENTIFIERS = [
    "PURELIFE1","PURELIFE2","PURELIFE3","PURELIFE4","PURELIFE5",
    "VYTAL0126","VYTAL0226","VYTAL0326","VYTAL0426","VYTAL0526",
    "VYTAL0626","VYTAL0726","VYTAL0826","VYTAL0926","VYTAL01026",
    "Diabetes Management","Dyslipidemia Management",
    "Thyroid Care","Liver Care","Kidney Care",
]

PROGRAM_IMPACT_MAP = {
    "Diabetes Management":    ["Diabetes","Diabetes mellitus"],
    "Dyslipidemia Management":["Dyslipidemia"],
    "Thyroid Care":           ["Thyroid dysfunction","Thyroid dsyfunction"],
    "Liver Care":             ["Liver dysfunction"],
    "Kidney Care":            ["Kidney dysfunction"],
}

# Reverse map: impact  programme name (for grouping)
IMPACT_PROGRAM_MAP = {
    "Diabetes":"Diabetes Management",
    "Diabetes mellitus":"Diabetes Management",
    "Dyslipidemia":"Dyslipidemia Management",
    "Thyroid dysfunction":"Thyroid Care",
    "Thyroid dsyfunction":"Thyroid Care",
    "Liver dysfunction":"Liver Care",
    "Kidney dysfunction":"Kidney Care",
}

DEVICE_2025_FILE = os.path.join(SCRIPT_DIR, "2025_device_recipients.xlsx")


#  TRINO 
def run_trino_query(query, retry=1):
    try:
        pw  = urllib.parse.quote_plus(str(TRINO_CONFIG["password"]))
        env = TRINO_CONFIG["env"]
        url = (
            f"trino://{TRINO_CONFIG['user']}:{pw}@trino-prod.healthrx.co.in:443/systemxhttp_scheme=https"
            if env == "Prod"
            else f"trino://{TRINO_CONFIG['user']}:{pw}@trino-dev.healthrx.co.in:443/systemxhttp_scheme=https"
        )
        engine = create_engine(url, connect_args={"verify": False})
        with engine.connect() as conn:
            result = conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        engine.dispose()
        return df
    except Exception as e:
        print(f"  ERR: {e}")
        if retry > 0:
            return run_trino_query(query, retry - 1)
        return None


# 
# TOTAL CAMP REPORTS COUNT  (f_claim + customers join)
# Returns {"total_reports": N, "total_users": N}
# 
def fetch_camp_reports_count(date_from, date_to, camp_codes):
    codes_sql = ", ".join(f"'{c}'" for c in camp_codes)
    date_filter = ""
    if date_from:
        date_filter += f"\n  AND substring(cast(d.created_at AS VARCHAR), 1, 7) >= '{date_from}'"
    if date_to:
        date_filter += f"\n  AND substring(cast(d.created_at AS VARCHAR), 1, 7) <= '{date_to}'"
    query = f"""
    SELECT
        count(DISTINCT a.orderid)            AS total_reports,
        count(DISTINCT d.mobile_number_hash) AS total_users
    FROM deltalake.dl_standard_customermart.f_claim a
    LEFT JOIN deltalake.dl_central_hrxlabs.customers d
        ON a.orderid = d.order_id
    WHERE a.product_code IN ({codes_sql})
      AND d.mobile_number_hash IS NOT NULL
      AND d.report_url IS NOT NULL{date_filter}
    """
    print(f"  Querying f_claim camp counts ({', '.join(camp_codes)}) [{date_from} -> {date_to}]...")
    df = run_trino_query(query)
    if df is None or df.empty:
        print("  WARNING: Camp count query returned nothing")
        return {"total_reports": 0, "total_users": 0, "source": "unavailable"}
    total_reports = int(df.iloc[0]["total_reports"]) if "total_reports" in df.columns else 0
    total_users   = int(df.iloc[0]["total_users"])   if "total_users"   in df.columns else 0
    print(f"  Camp reports: {total_reports:,}  |  Unique users: {total_users:,}")
    return {"total_reports": total_reports, "total_users": total_users, "source": "f_claim"}


#  CSV LOADER 
def load_csv(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(f"    Not found: {filename}")
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False)
    print(f"   {filename}: {len(df):,} rows, {df['mobile_number_hash'].nunique():,} unique users")
    return df


# 
# KPI 1: TOTAL CAMP
# 
def compute_total_camp(impact_scores):
    return int(impact_scores["mobile_number_hash"].nunique()) if not impact_scores.empty else 0


# 
# KPI 2 + 7: FETCH POLICY DATA (d_policy fresh query)
# 
def fetch_policy_data(year, codes):
    """
    Fetch enrolled users from d_policy.
    SELECT * is blocked  only specific columns.
    Cohort__c: auto-discovered if exists, else fallback to normalized scores.
    """
    codes_sql = ", ".join(f"'{c}'" for c in codes)
    print(f"\n  Querying d_policy for {year} ({', '.join(codes)})")

    # lob__c holds Moderate/High/Very High risk tier for VYTAL users
    cohort_col = "lob__c" if year == "2026" else None

    cohort_select = f"{cohort_col} AS policy_cohort," if cohort_col else ""

    dr           = ENROLLMENT_DATE_RANGES.get(year, {"from": "2025-05", "to": "2026-04"})
    enroll_from  = dr["from"]
    enroll_to    = dr["to"]

    q = f"""
    SELECT DISTINCT
        personmobilephone_hash          AS mobile_number_hash,
        vlocity_ins_fsc__productcode__c AS mc_product_code,
        {cohort_select}
        substring(cast(createddate AS VARCHAR), 1, 7) AS policy_year_month,
        substring(cast(createddate AS VARCHAR), 1, 4) AS policy_year
    FROM deltalake.dl_standard_customermart.d_policy
    WHERE vlocity_ins_fsc__productcode__c IN ({codes_sql})
      AND personmobilephone_hash IS NOT NULL
      AND (is_test_policy__c = FALSE OR is_test_policy__c IS NULL)
      AND substring(cast(createddate AS VARCHAR), 1, 7) >= '{enroll_from}'
      AND substring(cast(createddate AS VARCHAR), 1, 7) <= '{enroll_to}'
    """
    df = run_trino_query(q)
    if df is None or df.empty:
        print("    No policy data returned")
        return pd.DataFrame()

    df["managed_care_program"] = df["mc_product_code"].map(PRODUCT_PROGRAM).fillna("Unknown")
    if "policy_cohort" not in df.columns:
        df["policy_cohort"] = None
    print(f"   {df['mobile_number_hash'].nunique():,} enrolled users")
    return df


# 
# KPI 7b: COHORT SPLIT
# 
def compute_cohort_split(policy_df, impact_scores=None):
    """
    Step 1: Use policy_cohort from d_policy (Cohort__c) if available.
    Step 2: Fallback  derive from normalized_score in impact_scores.
            Lower score = higher risk (more disease burden).
    """
    # Step 1: d_policy cohort column
    if not policy_df.empty and "policy_cohort" in policy_df.columns:
        uniq  = policy_df.drop_duplicates("mobile_number_hash")
        valid = uniq[uniq["policy_cohort"].notna() & (uniq["policy_cohort"].astype(str).str.strip() != "")]
        if len(valid) > 0:
            counts = valid["policy_cohort"].value_counts().to_dict()
            result = {
                "Very High": int(counts.get("Very High", 0)),
                "High":      int(counts.get("High",      0)),
                "Moderate":  int(counts.get("Moderate",  0)),
                "Low":       int(counts.get("Low",        0)),
                "source":    "d_policy Cohort__c"
            }
            if sum(v for k,v in result.items() if k != "source") > 0:
                print(f"   Cohort from d_policy: {result}")
                return result

    # Step 2: Fallback  normalized_score from impact_scores
    print("    Cohort column empty  deriving from normalized_score (lower = higher risk)")
    if impact_scores is None or impact_scores.empty:
        return {"Very High":0,"High":0,"Moderate":0,"Low":0,"source":"unavailable"}

    enrolled_hashes = set(policy_df["mobile_number_hash"].dropna()) if not policy_df.empty else set()

    score_col = None
    for col in ["normalized_score","scaled_score","normalized_earliest","normalized_latest"]:
        if col in impact_scores.columns:
            score_col = col
            break

    if not score_col:
        return {"Very High":0,"High":0,"Moderate":0,"Low":0,"source":"no score column"}

    df_s = impact_scores.copy()
    if enrolled_hashes:
        df_s = df_s[df_s["mobile_number_hash"].isin(enrolled_hashes)]

    df_s[score_col] = pd.to_numeric(df_s[score_col], errors="coerce")
    df_s = df_s.dropna(subset=[score_col])

    # Take max score per user across all impacts
    user_scores = df_s.groupby("mobile_number_hash")[score_col].max()

    # Lower score = higher risk  quartile thresholds
    p25 = user_scores.quantile(0.25)
    p50 = user_scores.quantile(0.50)
    p75 = user_scores.quantile(0.75)

    def assign(s):
        if s <= p25:   return "Very High"
        elif s <= p50: return "High"
        elif s <= p75: return "Moderate"
        else:          return "Low"

    counts = user_scores.apply(assign).value_counts().to_dict()
    result = {
        "Very High": int(counts.get("Very High", 0)),
        "High":      int(counts.get("High",      0)),
        "Moderate":  int(counts.get("Moderate",  0)),
        "Low":       int(counts.get("Low",        0)),
        "source":    f"normalized_score quartiles ({score_col})"
    }
    print(f"   Cohort from normalized scores: {result}")
    return result


# 
# KPI 3 + 8: IMPROVEMENT PIVOT
# 
def compute_improvement_pivot(comp, year_codes):
    """
    Pivot table matching Excel output:
      Rows    = impact (Diabetes, Dyslipidemia etc.)
      Sub-row = mc_product_code (PURELIFE1 / None etc.)
      Cols    = improvement_flag counts + %

    Key rule: Programme user counted only on the impact
    matching their programme (PURELIFE1  Diabetes rows only).

    Auto-detects which year codes are actually in the CSV
    (handles mismatch between selected year and CSV content).
    """
    if comp.empty:
        return {}

    comp = comp.copy()
    comp["mc_product_code"] = comp["mc_product_code"].fillna("None").astype(str).str.strip()
    comp.loc[comp["mc_product_code"] == "", "mc_product_code"] = "None"

    # Auto-detect: find which codes are actually present in CSV
    all_codes_in_csv = set(comp["mc_product_code"].unique()) - {"None"}
    all_known_codes  = set(ALL_MC_IDENTIFIERS)
    codes_in_csv     = all_codes_in_csv & all_known_codes

    if not codes_in_csv:
        print("    No managed care product codes found in comparison CSV")
        print(f"     Unique mc_product_code values: {sorted(all_codes_in_csv)[:10]}")
        return {"total_retested":comp["mobile_number_hash"].nunique(),"mc_users":0,"non_mc_users":comp["mobile_number_hash"].nunique(),"by_programme":{},"overall_mc_improved_pct":0,"overall_non_mc_improved_pct":0}

    # Use codes actually found in CSV (not the requested year codes)
    effective_codes = list(codes_in_csv)
    if set(effective_codes) != set(year_codes):
        print(f"    Requested year codes: {year_codes}")
        print(f"    Codes found in CSV:   {effective_codes}")
        print(f"    Using codes found in CSV for pivot calculation")
    year_codes = effective_codes

    total_retested = comp["mobile_number_hash"].nunique()
    mc_hashes  = set(comp[comp["mc_product_code"].isin(year_codes)]["mobile_number_hash"])
    non_mc_n   = total_retested - len(mc_hashes)

    pivot = {
        "total_retested": int(total_retested),
        "mc_users":       int(len(mc_hashes)),
        "non_mc_users":   int(non_mc_n),
        "by_programme":   {}
    }

    mc_all_improved  = 0
    mc_all_total     = 0
    non_mc_improved  = 0
    non_mc_total_all = 0

    # Build programme-level groups from what's actually in the CSV
    # mc_product_code may contain raw codes (PURELIFE1) or names (Diabetes Management)
    # Group by resolved programme name for clean pivot rows
    prog_groups = {}
    for code in year_codes:
        prog_name = PRODUCT_PROGRAM.get(code, code)
        if prog_name not in prog_groups:
            prog_groups[prog_name] = []
        prog_groups[prog_name].append(code)

    for prog_name, codes_for_prog in prog_groups.items():
        impacts   = PROGRAM_IMPACT_MAP.get(prog_name, [prog_name])

        # Match rows: mc_product_code matches any of the codes for this programme
        # AND impact matches the programme's expected impacts
        prog_rows  = comp[(comp["mc_product_code"].isin(codes_for_prog)) & (comp["impact"].isin(impacts))]
        prog_uniq  = prog_rows.drop_duplicates("mobile_number_hash")
        code = codes_for_prog[0]  # use first code for display

        mc_n   = len(prog_uniq)
        mc_i   = int((prog_uniq["improvement_flag"] == "Improved").sum())
        mc_w   = int((prog_uniq["improvement_flag"] == "Worsened").sum())
        mc_nc  = int((prog_uniq["improvement_flag"] == "No Change").sum())
        mc_nr  = int((prog_uniq["improvement_flag"] == "No Risk").sum())

        # Non-programme users: same impact, no product
        np_rows = comp[(comp["mc_product_code"] == "None") & (comp["impact"].isin(impacts))]
        np_uniq = np_rows.drop_duplicates("mobile_number_hash")
        np_n    = len(np_uniq)
        np_i    = int((np_uniq["improvement_flag"] == "Improved").sum())
        np_w    = int((np_uniq["improvement_flag"] == "Worsened").sum())

        mc_all_improved  += mc_i
        mc_all_total     += mc_n
        non_mc_improved  += np_i
        non_mc_total_all += np_n

        adv = round((mc_i/mc_n) / (np_i/np_n), 2) if mc_n > 0 and np_n > 0 and np_i > 0 else None

        pivot["by_programme"][prog_name] = {
            "product_code":    code,
            "mc_total":        mc_n,
            "mc_improved":     mc_i,
            "mc_worsened":     mc_w,
            "mc_no_change":    mc_nc,
            "mc_no_risk":      mc_nr,
            "mc_improved_pct": round(mc_i/mc_n*100, 2) if mc_n > 0 else 0,
            "mc_worsened_pct": round(mc_w/mc_n*100, 2) if mc_n > 0 else 0,
            "np_total":        np_n,
            "np_improved":     np_i,
            "np_worsened":     np_w,
            "np_improved_pct": round(np_i/np_n*100, 2) if np_n > 0 else 0,
            "np_worsened_pct": round(np_w/np_n*100, 2) if np_n > 0 else 0,
            "advantage_x":     adv,
        }

    pivot["overall_mc_improved_pct"]    = round(mc_all_improved/mc_all_total*100, 2) if mc_all_total > 0 else 0
    pivot["overall_non_mc_improved_pct"]= round(non_mc_improved/non_mc_total_all*100, 2) if non_mc_total_all > 0 else 0

    print(f"  Pivot: {total_retested:,} retested | MC {len(mc_hashes):,} | non-MC {non_mc_n:,}")
    print(f"  Overall MC improved: {pivot['overall_mc_improved_pct']}% vs non-MC: {pivot['overall_non_mc_improved_pct']}%")
    return pivot


# 
# KPI 4: ZERO APPOINTMENT USERS
# 
def compute_zero_appt(comp, policy_df, year):
    if comp.empty:
        return {"zero_appt":0,"enrolled":0,"pct":0}

    # If policy_df is empty (d_policy returned nothing), fall back to
    # MC users in comparison CSV as enrolled population
    if policy_df.empty:
        all_known = set(YEAR_CODES["2025"] + YEAR_CODES["2026"])
        comp2 = comp.copy()
        comp2["mc_product_code"] = comp2["mc_product_code"].fillna("None").astype(str)
        codes_in_csv = set(comp2["mc_product_code"].unique()) & all_known
        enrolled = set(comp2[comp2["mc_product_code"].isin(codes_in_csv)]["mobile_number_hash"].dropna())
        print(f"    policy_df empty  using {len(enrolled):,} MC users from CSV as enrolled")
    else:
        enrolled = set(policy_df["mobile_number_hash"].dropna())
    clin_col = "clinic_appts_ty" if year == "2026" else "clinic_appts_ly"
    lab_col  = "lab_tests_ty"    if year == "2026" else "lab_tests_ly"

    ec = comp[comp["mobile_number_hash"].isin(enrolled)].drop_duplicates("mobile_number_hash").copy()

    clin = ec[clin_col].fillna(0) if clin_col in ec.columns else pd.Series(0, index=ec.index)
    lab  = ec[lab_col].fillna(0)  if lab_col  in ec.columns else pd.Series(0, index=ec.index)

    # Users with at least one appointment in comparison CSV
    has_appt = set(ec[((clin > 0) | (lab > 0))]["mobile_number_hash"].dropna())
    # All enrolled minus those with appts = zero-appt users
    # (includes enrolled users not in comparison at all  no retest = no appt record)
    enr_n  = len(enrolled)
    zero_n = enr_n - len(has_appt)

    return {
        "zero_appt": zero_n,
        "enrolled":  enr_n,
        "pct":       round(zero_n/enr_n*100, 2) if enr_n > 0 else 0
    }


# 
# KPI 5: DEVICE IMPROVEMENT
# 
def compute_device_improvement(comp, device, policy_df, year_codes, year):
    result = {
        "device_users_total":0,"device_improved":0,"device_improved_pct":0,
        "no_device_total":0,"no_device_improved":0,"no_device_improved_pct":0,
        "data_source":"Not available"
    }
    if comp.empty:
        return result

    if year == "2026":
        if device.empty:
            result["data_source"] = "device_eligibility.csv not found"
            return result
        with_dev = set(device[device["primary_device"].fillna("None") != "None"]["mobile_number_hash"])
        without_dev = set(device[device["primary_device"].fillna("None") == "None"]["mobile_number_hash"])
        result["data_source"] = "managed_care_device_eligibility.csv"
    else:
        if not os.path.exists(DEVICE_2025_FILE):
            result["data_source"] = "2025_device_recipients.xlsx  upload required"
            return result
        df_d = pd.read_excel(DEVICE_2025_FILE)
        with_dev    = set(df_d["mobile_number_hash"].dropna())
        without_dev = set(policy_df["mobile_number_hash"].dropna()) - with_dev
        result["data_source"] = "2025_device_recipients.xlsx"

    # Matched impact rows only
    comp2 = comp.copy()
    comp2["mc_product_code"] = comp2["mc_product_code"].fillna("None").astype(str)
    # Auto-detect codes in CSV for device improvement too
    all_known = set(ALL_MC_IDENTIFIERS)
    codes_present = set(comp2['mc_product_code'].unique()) & all_known
    effective = list(codes_present) if codes_present else year_codes

    mc = comp2[comp2["mc_product_code"].isin(effective)].copy()
    mc["prog"]    = mc["mc_product_code"].map(PRODUCT_PROGRAM)
    mc["impacts"] = mc["prog"].apply(lambda p: PROGRAM_IMPACT_MAP.get(str(p) if p else '', []))
    # Use list comprehension instead of apply to avoid DataFrame assignment error
    mc = mc.copy()
    matched_list = [bool(row['impact'] in row['impacts'])
                    for _, row in mc[['impact','impacts']].iterrows()]
    mc['matched'] = matched_list
    mc_matched = mc[mc["matched"] == True].drop_duplicates("mobile_number_hash")

    d_mc   = mc_matched[mc_matched["mobile_number_hash"].isin(with_dev)]
    nd_mc  = mc_matched[mc_matched["mobile_number_hash"].isin(without_dev)]

    result.update({
        "device_users_total":    int(len(d_mc)),
        "device_improved":       int((d_mc["improvement_flag"] == "Improved").sum()),
        "device_improved_pct":   round((d_mc["improvement_flag"]=="Improved").sum()/len(d_mc)*100,2) if len(d_mc)>0 else 0,
        "no_device_total":       int(len(nd_mc)),
        "no_device_improved":    int((nd_mc["improvement_flag"] == "Improved").sum()),
        "no_device_improved_pct":round((nd_mc["improvement_flag"]=="Improved").sum()/len(nd_mc)*100,2) if len(nd_mc)>0 else 0,
    })
    return result


# 
# KPI 6: APPOINTMENTS + ENGAGEMENT
# 
def compute_appt_stats(comp, policy_df, year):
    if comp.empty or policy_df.empty:
        return {"total_booked":0,"completed":0,"completion_pct":0,"lab_tests":0,"clinic_appts":0}
    enrolled = set(policy_df["mobile_number_hash"].dropna())
    ec = comp[comp["mobile_number_hash"].isin(enrolled)]
    sfx = "ty" if year == "2026" else "ly"
    def gs(col): return int(ec[col].fillna(0).sum()) if col in ec.columns else 0
    total = gs(f"total_appts_{sfx}"); done = gs(f"appts_completed_{sfx}")
    lab   = gs(f"lab_tests_{sfx}");   clin = gs(f"clinic_appts_{sfx}")
    return {"total_booked":total,"completed":done,
            "completion_pct":round(done/total*100,2) if total>0 else 0,
            "lab_tests":lab,"clinic_appts":clin}


def compute_engagement(device, policy_df):
    if device.empty or policy_df.empty:
        return {"High":{"n":0,"pct":0},"Moderate":{"n":0,"pct":0},
                "Low":{"n":0,"pct":0},"Very Low":{"n":0,"pct":0}}
    enrolled = set(policy_df["mobile_number_hash"].dropna())
    ed = device[device["mobile_number_hash"].isin(enrolled)]
    counts = ed["engagement_tier"].value_counts().to_dict()
    total  = len(ed)
    return {k: {"n":int(counts.get(k,0)), "pct":round(counts.get(k,0)/total*100,2) if total else 0}
            for k in ["High","Moderate","Low","Very Low"]}


# 
# SAVE POLICY CSV  all years, for dashboard date filtering
# 
def save_policy_csv_for_dashboard():
    """
    Fetch ALL managed care policies (both years) excluding test users
    and save to managed_care_policy_data.csv.
    Dashboard uses this to compute enrolled count for any selected date range.
    """
    all_codes = (
        YEAR_CODES["2025"] + YEAR_CODES["2026"]
    )
    codes_sql = ", ".join(f"'{c}'" for c in all_codes)
    q = f"""
    SELECT DISTINCT
        personmobilephone_hash          AS mobile_number_hash,
        masterphrid                     AS phr_id,
        vlocity_ins_fsc__productcode__c AS mc_product_code,
        substring(cast(createddate AS VARCHAR), 1, 7) AS policy_year_month,
        CASE WHEN vlocity_ins_fsc__productcode__c LIKE 'VYTAL%' THEN lob__c ELSE NULL END AS cohort
    FROM deltalake.dl_standard_customermart.d_policy
    WHERE vlocity_ins_fsc__productcode__c IN ({codes_sql})
      AND personmobilephone_hash IS NOT NULL
      AND (is_test_policy__c = FALSE OR is_test_policy__c IS NULL)
      AND substring(cast(createddate AS VARCHAR), 1, 7) >= '2025-06'
    """
    print("  Querying all policy data for dashboard CSV")
    df = run_trino_query(q)
    if df is None or df.empty:
        print("  WARNING: No policy data returned for dashboard CSV")
        return pd.DataFrame()
    df["managed_care_program"] = df["mc_product_code"].map(PRODUCT_PROGRAM).fillna("Unknown")
    path = os.path.join(DATA_DIR, "managed_care_policy_data.csv")
    df.to_csv(path, index=False)
    save_dataframe(df, "policy_data", if_exists="replace")
    print(f"  Saved managed_care_policy_data.csv  {df['mobile_number_hash'].nunique():,} unique enrolled users")
    return df


# 
# SAVE CAMP MONTHLY CSV  for dashboard date filtering
# 
def save_camp_monthly_csv():
    """
    Fetch monthly camp report counts for 2025 and 2026 camp years.
    Saves managed_care_camp_monthly.csv for dashboard date-reactive camp KPI.
    """
    results = []
    for camp_year, codes, date_from, date_to in [
        ("2025", CAMP_CODES_BY_YEAR["2025"], "2025-04", "2026-03"),
        ("2026", CAMP_CODES_BY_YEAR["2026"], "2026-04", None),
    ]:
        codes_sql  = ", ".join(f"'{c}'" for c in codes)
        date_upper = f"AND substring(cast(d.created_at AS VARCHAR), 1, 7) <= '{date_to}'" if date_to else ""
        q = f"""
        SELECT
            substring(cast(d.created_at AS VARCHAR), 1, 7) AS year_month,
            '{camp_year}'                                   AS camp_year,
            count(DISTINCT a.orderid)                       AS total_reports,
            count(DISTINCT d.mobile_number_hash)            AS unique_users
        FROM deltalake.dl_standard_customermart.f_claim a
        LEFT JOIN deltalake.dl_central_hrxlabs.customers d
            ON a.orderid = d.order_id
        WHERE a.product_code IN ({codes_sql})
          AND d.mobile_number_hash IS NOT NULL
          AND d.report_url IS NOT NULL
          AND substring(cast(d.created_at AS VARCHAR), 1, 7) >= '{date_from}'
          {date_upper}
        GROUP BY 1
        ORDER BY 1
        """
        print(f"  Querying monthly camp counts for {camp_year}")
        df = run_trino_query(q)
        if df is not None and not df.empty:
            results.append(df)
            print(f"    {len(df)} months, {int(df['total_reports'].sum()):,} total reports")

    if results:
        combined = pd.concat(results, ignore_index=True)
        path = os.path.join(DATA_DIR, "managed_care_camp_monthly.csv")
        combined.to_csv(path, index=False)
        save_dataframe(combined, "camp_monthly", if_exists="replace")
        print(f"  Saved managed_care_camp_monthly.csv  {len(combined)} month rows")
        return combined
    return pd.DataFrame()


# 
# APPOINTMENTS UTILIZATION CSV  for dashboard
# 
def fetch_appointments_utilization():
    """
    Fetch claim records from f_claim for enrolled PURELIFE/VYTAL users.
    Source of truth: d_policy (masterphrid = phr_id in f_claim).
    Avoids customers table  counts all claims for policy holders regardless
    of whether they have a lab order in customers.
    Enrollment window: 2025 = Jun 2025May 2026 | 2026 = Jun 2026May 2027
    """
    APPT_ENROLL = {
        "2025": {"from": "2025-06", "to": "2026-05"},
        "2026": {"from": "2026-06", "to": "2027-05"},
    }
    results = []

    for year, pol_codes in [("2025", YEAR_CODES["2025"]), ("2026", YEAR_CODES["2026"])]:
        ef = APPT_ENROLL[year]["from"]
        et = APPT_ENROLL[year]["to"]
        cs = ", ".join(f"'{c}'" for c in pol_codes)
        print(f"\n  [Appointments {year}] Enroll window: {ef} to {et}")

        # f_claim filtered by product_code  all claims for PURELIFE/VYTAL holders.
        # LEFT JOIN customers only to get mobile_number_hash (identity, not a filter).
        # appointment_date is the actual appointment date for correct month bucketing.
        # COUNT(DISTINCT claim_id)  unique appointments, no fan-out duplication.
        # GROUP BY phr_id (not mobile_hash) so all claims are counted even those
        # without a customers record.
        df_claims = run_trino_query(f"""
            SELECT
                fc.phr_id,
                MAX(c.mobile_number_hash)                              AS mobile_number_hash,
                fc.product_code                                        AS mc_product_code,
                fc.benefit_name,
                fc.claim_status,
                SUBSTR(CAST(fc.appointment_date AS VARCHAR), 1, 7)    AS claim_month,
                COUNT(DISTINCT fc.claim_id)                           AS claim_count,
                MAX(dp.lob__c)                                         AS cohort
            FROM deltalake.dl_standard_customermart.f_claim fc
            LEFT JOIN deltalake.dl_central_hrxlabs.customers c
                ON fc.phr_id = c.phr_id
            LEFT JOIN deltalake.dl_standard_customermart.d_policy dp
                ON fc.phr_id = dp.masterphrid
                AND dp.vlocity_ins_fsc__productcode__c IN ({cs})
                AND (dp.is_test_policy__c = FALSE OR dp.is_test_policy__c IS NULL)
            WHERE fc.product_code IN ({cs})
              AND fc.appointment_date IS NOT NULL
            GROUP BY fc.phr_id, 3, 4, 5, 6
        """)

        # Enrolled count from d_policy  used only for zero-appt denominator
        df_enr = run_trino_query(f"""
            SELECT COUNT(DISTINCT personmobilephone_hash) AS enrolled
            FROM deltalake.dl_standard_customermart.d_policy
            WHERE vlocity_ins_fsc__productcode__c IN ({cs})
              AND personmobilephone_hash IS NOT NULL
              AND (is_test_policy__c = FALSE OR is_test_policy__c IS NULL)
              AND SUBSTR(CAST(createddate AS VARCHAR), 1, 7) >= '{ef}'
              AND SUBSTR(CAST(createddate AS VARCHAR), 1, 7) <= '{et}'
        """)
        enrolled_n = int(df_enr.iloc[0]["enrolled"]) if df_enr is not None and not df_enr.empty else 0
        print(f"  Enrolled ({year}): {enrolled_n:,}")

        if df_claims is None or df_claims.empty:
            print(f"  No claims found in f_claim for {year}")
            continue

        df_claims["programme"]   = df_claims["mc_product_code"].map(PRODUCT_PROGRAM).fillna("Unknown")
        df_claims["year"]        = year
        df_claims["claim_count"] = pd.to_numeric(df_claims["claim_count"], errors="coerce").fillna(0).astype(int)

        nc_total  = int(df_claims[~df_claims["claim_status"].isin(["Cancelled"])]["claim_count"].sum())
        # Count distinct phr_ids (not mobile hashes)  correct unique user count
        # mobile_number_hash can be NULL when phr_id has no customers record
        booked    = df_claims[df_claims["claim_status"].isin(["Authorized","Redeemed","Paid"])]["phr_id"].nunique()
        redeemed  = int(df_claims[df_claims["claim_status"] == "Redeemed"]["claim_count"].sum())
        print(f"  Total claims (non-cancelled): {nc_total:,}")
        print(f"  Users with booking   : {booked:,}  |  zero-appt: {enrolled_n - booked:,}")
        print(f"  Total redeemed claims: {redeemed:,}")

        results.append(df_claims[["year","phr_id","mobile_number_hash","mc_product_code","programme",
                                   "benefit_name","claim_status","claim_month","claim_count","cohort"]])

    if not results:
        print("  No appointment data  CSV not saved")
        return pd.DataFrame()

    combined = pd.concat(results, ignore_index=True)
    path = os.path.join(DATA_DIR, "managed_care_appt_utilization.csv")
    combined.to_csv(path, index=False)
    save_dataframe(combined, "appt_utilization", if_exists="replace")
    print(f"\n  Saved managed_care_appt_utilization.csv  {len(combined):,} rows | {combined['mobile_number_hash'].nunique():,} unique users")
    return combined


# 
# BUILD SUMMARY
# 
def build_summary(year):
    # year here = ENROLLED_YEAR (d_policy year, e.g. "2025" for PURELIFE)
    codes = YEAR_CODES.get(year, YEAR_CODES["2025"])

    print("\n[1] Loading CSVs")
    impact_scores = load_csv("managed_care_impact_scores.csv")
    comp          = load_csv("managed_care_comparison.csv")
    device        = load_csv("managed_care_device_eligibility.csv")

    print("\n[2] Fetching Total Camp Reports from f_claim")
    # count(distinct order_id) = unique lab reports issued (authoritative source)
    camp_data  = fetch_camp_reports_count(DATE_FROM, DATE_TO, CAMP_CODES_CURRENT)
    camp_total = camp_data["total_reports"]
    camp_users = camp_data["total_users"]
    if camp_total == 0:
        camp_users = compute_total_camp(impact_scores)
        camp_total = camp_users
        camp_data["source"] = "impact_scores_fallback"

    print(f"\n[3] Querying d_policy for Total Enrolled (year={year}, {', '.join(codes)})")
    # Pass the ENROLLED_YEAR so d_policy is filtered by the correct policy year
    policy_df = fetch_policy_data(year, codes)

    print("\n[4] Computing KPIs")
    enrolled_policy_total = int(policy_df["mobile_number_hash"].nunique()) if not policy_df.empty else 0

    # Enrolled = policy holders who ALSO attended this camp cycle (impact_scores is the camp universe)
    if not policy_df.empty and not impact_scores.empty:
        policy_hashes = set(policy_df["mobile_number_hash"].dropna())
        camp_hashes   = set(impact_scores["mobile_number_hash"].dropna())
        enrolled_in_camp = len(policy_hashes & camp_hashes)
        print(f"  Policy holders (date-filtered):         {enrolled_policy_total:,}")
        print(f"  Enrolled who attended camp (intersect): {enrolled_in_camp:,}")
        enrolled = enrolled_in_camp
    else:
        enrolled = enrolled_policy_total

    prog_dist = {}
    if not policy_df.empty and not impact_scores.empty:
        camp_hashes = set(impact_scores["mobile_number_hash"].dropna())
        _pf = policy_df[policy_df["mobile_number_hash"].isin(camp_hashes)]
        prog_dist = _pf.groupby("managed_care_program")["mobile_number_hash"].nunique().to_dict()
    elif not policy_df.empty:
        prog_dist = policy_df.groupby("managed_care_program")["mobile_number_hash"].nunique().to_dict()

    # No fallback: if d_policy returns 0 for this year's codes, show 0.
    # Avoids cross-contaminating 2026 display with 2025 PURELIFE numbers.
    if enrolled == 0:
        print(f"    No enrolled users found in d_policy for {year} codes  displaying 0")

    def _load_hra_stats():
        try:
            _p = os.path.join(DATA_DIR, "managed_care_hra_stats.csv")
            if os.path.exists(_p):
                _df = pd.read_csv(_p)
                _d = dict(zip(_df["metric"], _df["value"].astype(int)))
                return {"completed": _d.get("enrolled_with_hra", 0),
                        "total_completed": _d.get("total_completed_all", 0)}
        except Exception:
            pass
        return {"completed": 0, "total_completed": 0}

    cohort_split = compute_cohort_split(policy_df, impact_scores)
    pivot        = compute_improvement_pivot(comp, codes)
    zero_appt    = compute_zero_appt(comp, policy_df, year)
    device_impr  = compute_device_improvement(comp, device, policy_df, codes, year)
    appt_stats   = compute_appt_stats(comp, policy_df, year)
    engagement   = compute_engagement(device, policy_df)

    print(f"\n   METRICS SUMMARY ")
    print(f"  Camp reports     : {camp_total:,}  (unique reports)")
    print(f"  Camp users       : {camp_users:,}  (unique individuals screened)")
    print(f"  Enrolled         : {enrolled:,}  (d_policy, {'VYTAL' if year=='2026' else 'PURELIFE'} codes)")
    print(f"  MC impr %        : {pivot.get('overall_mc_improved_pct',0)}%")
    print(f"  Non-MC impr %    : {pivot.get('overall_non_mc_improved_pct',0)}%")
    print(f"  Zero appt users  : {zero_appt['zero_appt']:,} ({zero_appt['pct']}%)")
    print(f"  Very High cohort : {cohort_split.get('Very High',0):,}")
    print(f"  Device impr %    : {device_impr.get('device_improved_pct',0)}%")

    return {
        "year": year,
        "date_from": DATE_FROM,
        "date_to":   DATE_TO,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        # Total Camp Reports  from f_claim count(distinct order_id)
        "camp_total":   camp_total,   # unique lab reports issued
        "camp_users":   camp_users,   # unique individuals screened (unique mobile hashes)
        "camp_source":  camp_data.get("source", "f_claim"),
        # Total Enrolled  from d_policy with PURELIFE/VYTAL codes
        "enrolled": enrolled,
        "prog_dist": prog_dist,
        "cohort_split": cohort_split,
        "improvement_pivot": pivot,
        "zero_appt": zero_appt,
        "device_impr": device_impr,
        "appt_stats": appt_stats,
        "engagement": engagement,
        "hra_stats": _load_hra_stats(),
    }


# 
# RULE-BASED INSIGHTS (no API needed)
# 
def generate_rule_based_insights(s):
    piv        = s.get("improvement_pivot", {})
    mc_pct     = piv.get("overall_mc_improved_pct", 0)
    non_pct    = piv.get("overall_non_mc_improved_pct", 0)
    advantage  = round(mc_pct / non_pct, 1) if non_pct > 0 else 0
    enrolled   = s.get("enrolled", 0)
    # keep enrolled for rest of function
    camp       = s.get("camp_total", 0)
    camp_users = s.get("camp_users", camp)
    coverage   = round(enrolled / camp_users * 100, 1) if camp_users > 0 else 0
    unenrolled = camp_users - enrolled
    zero       = s.get("zero_appt", {})
    zero_n     = zero.get("zero_appt", 0)
    zero_pct   = zero.get("pct", 0)
    coh        = s.get("cohort_split", {})
    vh         = coh.get("Very High", 0)
    high       = coh.get("High", 0)
    moderate   = coh.get("Moderate", 0)
    dev        = s.get("device_impr", {})
    dev_pct    = dev.get("device_improved_pct", 0)
    nodev_pct  = dev.get("no_device_improved_pct", 0)
    year       = s.get("year", "2026")

    progs      = piv.get("by_programme", {})
    best_prog  = max(progs, key=lambda p: progs[p].get("mc_improved_pct", 0)) if progs else ""
    worst_prog = min(progs, key=lambda p: progs[p].get("mc_improved_pct", 0)) if progs else ""
    high_worsened_progs = sorted(
        [(k, v.get("mc_worsened_pct", 0)) for k, v in progs.items()],
        key=lambda x: x[1], reverse=True
    )
    best_pct  = progs[best_prog].get("mc_improved_pct", 0) if best_prog != "" else 0
    worst_pct = progs[worst_prog].get("mc_improved_pct", 0) if worst_prog != "" else 0

    #  PM Daily Action Recommendations 
    # These are operational actions a Product Manager can take TODAY
    # based on current programme state  not historical comparisons.
    recos = []

    # Derived programme breakdown for context
    prog_dist    = s.get("prog_dist", {})
    hra_stats    = s.get("hra_stats", {})
    hra_done     = hra_stats.get("completed", 0) if isinstance(hra_stats, dict) else 0
    hra_pct      = round(hra_done / enrolled * 100, 1) if enrolled > 0 else 0
    high_risk_n  = vh + high    # Very High + High combined
    dev_alloc    = (s.get("device_impr", {}).get("device_users_total", 0) or 0)

    # 1. First Appointment Drive  {zero_n} users with no appointment
    if zero_n > 0:
        largest_prog = max(prog_dist, key=lambda k: prog_dist[k]) if prog_dist else "Dyslipidemia Management"
        largest_n    = prog_dist.get(largest_prog, 0)
        recos.append({
            "priority": 1,
            "title": f"Drive first appointment for {zero_n:,} enrolled users  0 booked so far",
            "action": (
                f"Send programme-specific booking links to all {enrolled:,} VYTAL users. "
                f"Start with {largest_prog} ({largest_n:,} users). Very High ({vh:,}) and High ({high:,}) users "
                f"should get a direct care manager call, not a self-serve link."
            ),
            "expected_impact": f"First appointment booked for at least 1,200 users within 30 days",
            "owner": "Product Manager + Care Team",
            "timeline": "This week"
        })

    # 2. Very High cohort  care manager assignment list
    if vh > 0:
        recos.append({
            "priority": 2,
            "title": f"Share {vh:,} Very High cohort list with care managers for immediate assignment",
            "action": (
                f"Export cohort list from the Cohort tab. {vh:,} Very High + {high:,} High risk users "
                f"({round(high_risk_n/enrolled*100) if enrolled else 0}% of enrolled) need active management. "
                f"Target: bi-weekly teleconsult for Very High, monthly app check-in for High."
            ),
            "expected_impact": f"100% of {vh:,} Very High users assigned to a care manager within 2 weeks",
            "owner": "Product Manager",
            "timeline": "Today"
        })

    # 3. HRA Drive  low completion rate
    if enrolled > 0 and hra_pct < 30:
        recos.append({
            "priority": 3,
            "title": f"Push HRA completion  only {hra_done} of {enrolled:,} done ({hra_pct:.1f}%)",
            "action": (
                f"Trigger in-app push + WhatsApp to all {enrolled - hra_done:,} users who haven't completed HRA. "
                f"HRA completion unlocks lifestyle assessment slots (currently 0 of 300 allocated)."
            ),
            "expected_impact": f"Increase HRA completion to 25% within 30 days; unlock lifestyle assessment allocation",
            "owner": "Product Manager",
            "timeline": "This week"
        })
    else:
        recos.append({
            "priority": 3,
            "title": f"Maintain HRA completion above 30%  currently at {hra_pct:.1f}%",
            "action": f"Weekly nudges for users who haven't completed HRA. Re-target low-completion programmes.",
            "expected_impact": "Maintain HRA completion above 30% across all programmes",
            "owner": "Product Manager",
            "timeline": "Weekly"
        })

    # 4. Device eligibility  trigger allocation (not yet delivered for 2026)
    recos.append({
        "priority": 4,
        "title": "Review device eligibility list and initiate 2026 device allocation",
        "action": (
            f"Device eligibility scoring is complete (Devices tab). "
            f"100 slots each for CGM, Glucometer, BP Monitor, Weighing Machine are scored and ranked. "
            f"Share the final allocation list with the fulfilment team to begin delivery."
        ),
        "expected_impact": "All 400 devices dispatched within 2 weeks; Day-7 activation check-in scheduled",
        "owner": "Product Manager",
        "timeline": "This week"
    })

    # 5. Weekly scorecard
    recos.append({
        "priority": 5,
        "title": f"Run weekly programme health check across {len(prog_dist) or 5} programmes",
        "action": (
            f"Review 4 metrics every Monday: first appointment rate, HRA completion %, "
            f"device activation rate, and Very High cohort assignment status. "
            f"Escalate to Programme Head if any metric declines 2 weeks in a row."
        ),
        "expected_impact": "Early drop-off signals caught before next camp cycle",
        "owner": "Product Manager",
        "timeline": "Every Monday"
    })

    return {
        "overview":{
            "headline":f"Managed Care {year}: Programme users improve at {mc_pct:.1f}% vs {non_pct:.1f}% non-programme  {advantage} advantage. {enrolled:,} of {camp:,} camp users enrolled ({coverage}% coverage).",
            "critical_flag":f"{zero_n:,} enrolled users ({zero_pct}%) have zero appointments  immediate outreach needed." if zero_pct>0 else "Appointment coverage is strong.",
            "positive_flag":f"{best_prog} leads all programmes with {best_pct:.1f}% improvement rate."
        },
        "programme_outcomes":{
            "narrative":f"Programme users improve at {mc_pct:.1f}% overall vs {non_pct:.1f}% for non-programme users  a {advantage} advantage confirming managed care efficacy. {best_prog} leads at {best_pct:.1f}% while {worst_prog} at {worst_pct:.1f}% needs attention.",
            "best_programme":best_prog,"best_programme_reason":f"{best_pct:.1f}% improvement  highest across all programmes.",
            "worst_programme":worst_prog,"worst_programme_reason":f"{worst_pct:.1f}% improvement  needs protocol review and increased touchpoints.",
            "advantage_narrative":f"Programme users are {advantage} more likely to improve than non-programme users on the same health impact."
        },
        "cohort_analysis":{
            "narrative":f"{vh:,} Very High cohort users require immediate clinical intervention. These users carry the highest disease burden and risk deterioration without active managed care.",
            "very_high_action":f"Assign dedicated care managers to all {vh:,} Very High users and schedule fortnightly check-ins within 7 days.",
            "coverage_insight":f"{coverage}% of camp attendees enrolled  {100-coverage:.1f}% remain unaddressed and represent a significant opportunity."
        },
        "devices":{
            "narrative":f"Device users with managed care improve at {dev_pct:.1f}% vs {nodev_pct:.1f}% for non-device MC users  a {round(dev_pct-nodev_pct,1)} percentage point gap confirming device efficacy.",
            "recommendation":"Implement 30-day device onboarding protocol with check-ins at day 7 and day 21 to ensure activation and consistent usage."
        },
        "appointments":{
            "narrative":f"Appointment completion stands at {zero.get('pct',0):.1f}% among enrolled users. {zero_pct:.0f}% of enrolled users have had no appointments  the largest single gap in programme engagement.",
            "zero_appt_action":f"Send personalised outreach to {zero_n:,} zero-appointment users within 2 weeks, segmented by programme type with direct specialist booking links."
        },
        "engagement":{
            "narrative":"High and Moderate engagement users consistently outperform Low tier on improvement rates, confirming engagement as a leading indicator of clinical outcomes.",
            "low_engagement_action":"Trigger automated WhatsApp reminders with booking links and personalised progress reports for Low and Very Low engagement users to re-activate them."
        },
        "recommendations": recos[:5]
    }


# 
# AI CALL (multi-provider with rule-based fallback)
# 
def call_ai(summary):
    # Build prompt
    piv  = summary.get("improvement_pivot", {})
    prg  = "\n".join([f"  {n}: {d['mc_total']} users, {d['mc_improved_pct']}% improved vs {d['np_improved_pct']}% non-MC ({d.get('advantage_x','')} adv)"
                      for n,d in piv.get("by_programme",{}).items()])
    coh  = summary.get("cohort_split", {})
    ct   = max(sum(v for k,v in coh.items() if k != "source"), 1)
    dev  = summary.get("device_impr", {})
    appt = summary.get("appt_stats", {})
    eng  = summary.get("engagement", {})
    zero = summary.get("zero_appt", {})

    camp_users = summary.get("camp_users", summary["camp_total"])
    prompt = f"""Analyse Managed Care 3.0 data for Bajaj Finserv Health ({summary['year']}, {summary.get('date_from','')}-{summary.get('date_to','')}).

METRICS:
Total Camp Reports: {summary['camp_total']:,} (unique lab reports) | Unique Screened: {camp_users:,} | Enrolled (d_policy): {summary['enrolled']:,} | Coverage: {round(summary['enrolled']/max(camp_users,1)*100,1)}%

COHORT (d_policy, source: {coh.get('source','unknown')}):
Very High: {coh.get('Very High',0):,} ({round(coh.get('Very High',0)/ct*100,1)}%) | High: {coh.get('High',0):,} | Moderate: {coh.get('Moderate',0):,} | Low: {coh.get('Low',0):,}

IMPROVEMENT (retested, matched impact):
Total retested: {piv.get('total_retested',0):,} | MC: {piv.get('mc_users',0):,} ({piv.get('overall_mc_improved_pct',0)}% improved) | Non-MC: {piv.get('non_mc_users',0):,} ({piv.get('overall_non_mc_improved_pct',0)}% improved)
{prg}

ZERO APPT: {zero.get('zero_appt',0):,} of {zero.get('enrolled',0):,} enrolled ({zero.get('pct',0)}%)
DEVICES: {dev.get('device_improved_pct',0)}% with device vs {dev.get('no_device_improved_pct',0)}% without
APPOINTMENTS: {appt.get('completed',0):,} completed ({appt.get('completion_pct',0)}%)
ENGAGEMENT: High {eng.get('High',{}).get('n',0):,} | Moderate {eng.get('Moderate',{}).get('n',0):,} | Low {eng.get('Low',{}).get('n',0):,}

Return ONLY valid JSON (no markdown):
{{"overview":{{"headline":"...","critical_flag":"...","positive_flag":"..."}},"programme_outcomes":{{"narrative":"...","best_programme":"...","best_programme_reason":"...","worst_programme":"...","worst_programme_reason":"...","advantage_narrative":"..."}},"cohort_analysis":{{"narrative":"...","very_high_action":"...","coverage_insight":"..."}},"devices":{{"narrative":"...","recommendation":"..."}},"appointments":{{"narrative":"...","zero_appt_action":"..."}},"engagement":{{"narrative":"...","low_engagement_action":"..."}},"recommendations":[{{"priority":1,"title":"...","action":"...","expected_impact":"...","owner":"...","timeline":"..."}}]}}
Produce exactly 5 recommendations. Base everything only on the numbers above."""

    # Try Anthropic Claude Haiku (primary  for context extraction)
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        try:
            import anthropic as _anth
            print("  Using Claude Haiku (Anthropic)")
            client = _anth.Anthropic(api_key=anthropic_key)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            raw = msg.content[0].text.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1]
                raw = raw[4:].strip() if raw.startswith("json") else raw.strip()
            return json.loads(raw)
        except Exception as e:
            print(f"  Haiku failed: {e}")

    # Try Groq
    groq_key = os.environ.get("GROQ_API_KEY","")
    if groq_key:
        try:
            from groq import Groq
            print("  Using Groq")
            c = Groq(api_key=groq_key)
            r = c.chat.completions.create(model="llama-3.3-70b-versatile",max_tokens=2000,
                messages=[{"role":"user","content":prompt}])
            raw = r.choices[0].message.content.strip()
            if raw.startswith("```"): raw = raw.split("```")[1]; raw = raw[4:] if raw.startswith("json") else raw
            return json.loads(raw.strip())
        except Exception as e:
            print(f"  Groq failed: {e}")

    # Try Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY","")
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            print("  Using Gemini")
            m = genai.GenerativeModel("gemini-1.5-flash")
            r = m.generate_content(prompt)
            raw = r.text.strip()
            if raw.startswith("```"): raw = raw.split("```")[1]; raw = raw[4:] if raw.startswith("json") else raw
            return json.loads(raw.strip())
        except Exception as e:
            print(f"  Gemini failed: {e}")

    # Rule-based fallback
    print("  Using rule-based insights (no API key set)")
    return generate_rule_based_insights(summary)


# 
# MAIN
# 
def main():
    print("\n" + "="*60)
    print(f"  MANAGED CARE 3.0  Script 4: Analysis")
    print(f"  Camp year    : {SELECTED_CAMP_YEAR}  ({DATE_FROM} to {_yr_range['to'] or 'present'})")
    print(f"  Camp codes   : {', '.join(CAMP_CODES_CURRENT)}")
    print(f"  Policy codes : {', '.join(YEAR_CODES[ENROLLED_YEAR])}")
    print("="*60)

    # Pass ENROLLED_YEAR so d_policy is queried with the correct year + codes
    summary  = build_summary(ENROLLED_YEAR)

    print("\n[5] Generating insights")
    insights = call_ai(summary)

    output = {
        "meta": {
            "generated_at": summary["generated_at"],
            "enrolled_year": ENROLLED_YEAR,
            "camp_date_from": DATE_FROM,
            "camp_date_to":   DATE_TO,
        },
        "metrics": summary,
        "insights": insights
    }

    out_path = os.path.join(DATA_DIR, "claude_insights.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=int)

    print(f"\n Saved  {out_path}")

    print("\n[6] Saving policy, camp monthly & appointment utilization CSVs")
    policy_df = save_policy_csv_for_dashboard()
    save_camp_monthly_csv()
    print("\n[7] Fetching appointment utilization from f_claim")
    appt_df = fetch_appointments_utilization()

    # Recalculate zero_appt using f_claim appointment data (not comparison CSV) for the enrolled year
    if not appt_df.empty and not policy_df.empty:
        year = ENROLLED_YEAR
        codes = YEAR_CODES.get(year, YEAR_CODES["2025"])
        year_appt = appt_df[appt_df["year"] == year]
        enrolled_hashes = set(policy_df[policy_df["mc_product_code"].isin(codes)]["mobile_number_hash"].dropna())
        # Count unique users: use phr_id if available, else mobile_number_hash (same as dashboard logic)
        booked_rows = year_appt[year_appt["claim_status"].isin(["Authorized","Redeemed","Paid"])]
        booked_users = set([r if pd.notna(r) else h for r, h in zip(booked_rows["phr_id"], booked_rows["mobile_number_hash"])])
        booked_users.discard(None)  # Remove None values
        zero_n = len(enrolled_hashes) - len(booked_users)
        zero_pct = round(zero_n / len(enrolled_hashes) * 100, 2) if enrolled_hashes else 0
        output["metrics"]["zero_appt"] = {"zero_appt": zero_n, "pct": zero_pct}

    # Re-save insights with updated zero_appt metrics
    out_path = os.path.join(DATA_DIR, "claude_insights.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=int)

    print("\n[8] Fetching 2026 lifestyle assessment benefit assignments")
    fetch_benefit_assignments_2026()

    print("\n  Top recommendations:")
    for r in insights.get("recommendations", [])[:3]:
        print(f"    {r.get('priority')}. {r.get('title')} [{r.get('owner')}]")
    print("\n Done. Reload dashboard to see updated data.")

# 
# BENEFIT ASSIGNMENTS 2026  lifestyle assessments assigned
# 
def fetch_benefit_assignments_2026():
    """
    Fetch assigned lifestyle assessment benefits from f_customerpolicybenefit
    for 2026 VYTAL enrolled users.

    Benefit codes confirmed:
      BH-AAB = Alcohol Assessment Benefit
      BH-SAB = Stress Assessment Benefit
      (Device benefit codes pending  will be added when available)
    """
    codes_sql = ", ".join(f"'{c}'" for c in YEAR_CODES["2026"])
    # Include all known benefit codes. Add device codes here when available.
    BENEFIT_CODES = ("'BH-AAB'", "'BH-SAB'")
    benefit_sql   = ", ".join(BENEFIT_CODES)

    q = f"""
    SELECT
        p.personmobilephone_hash        AS mobile_number_hash,
        p.masterphrid                   AS phr_id,
        p.vlocity_ins_fsc__productcode__c AS mc_product_code,
        p.lob__c                        AS cohort,
        b.assetcoveragename             AS benefit_name,
        b.assetcoverageproductcode      AS benefit_code,
        b.benefitstatus
    FROM deltalake.dl_standard_customermart.f_customerpolicybenefit b
    JOIN deltalake.dl_standard_customermart.d_policy p
        ON b.policysfdc_id = p.policysfdc_id
    WHERE b.productcode IN ({codes_sql})
      AND b.assetcoverageproductcode IN ({benefit_sql})
      AND p.personmobilephone_hash IS NOT NULL
      AND (p.is_test_policy__c = FALSE OR p.is_test_policy__c IS NULL)
      AND SUBSTR(CAST(p.createddate AS VARCHAR), 1, 7) >= '2026-06'
      AND SUBSTR(CAST(p.createddate AS VARCHAR), 1, 7) <= '2027-05'
    """
    df = run_trino_query(q)
    if df is None or df.empty:
        print("  No lifestyle assessment benefit assignments found yet (BH-AAB / BH-SAB)")
        # Save empty so dashboard doesn't crash
        pd.DataFrame(columns=[
            "mobile_number_hash", "phr_id", "mc_product_code", "cohort",
            "benefit_name", "benefit_code", "benefitstatus"
        ]).to_csv(os.path.join(DATA_DIR, "managed_care_benefit_assignments_2026.csv"), index=False)
        return pd.DataFrame()

    path = os.path.join(DATA_DIR, "managed_care_benefit_assignments_2026.csv")
    df.to_csv(path, index=False)
    print(f"  Saved managed_care_benefit_assignments_2026.csv  {len(df):,} rows | "
          f"{df['mobile_number_hash'].nunique():,} unique users")
    print(f"  Breakdown:")
    for code, grp in df.groupby("benefit_code"):
        print(f"    {code}: {grp['mobile_number_hash'].nunique():,} users assigned")
    return df


if __name__ == "__main__":
    main()

