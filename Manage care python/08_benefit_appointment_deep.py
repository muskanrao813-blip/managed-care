"""
============================================================
MANAGED CARE 3.0 — SCRIPT 08: Benefit + Appointment Deep Analysis
============================================================
Data sources:
  1. f_claim (claims table)
     → All benefits for enrolled users with created_date (booking date)
     → Used for: all benefits overview, repeat bookings, other benefits

  2. f_appointmentflattable
     → Nutritionist + Teleconsultation only
     → appointmentdate (actual service date), appointmentstatus, speciality
     → Used to calculate follow-up due date

  3. Customermart lab table
     → Lab Discounts / Health Monitoring benefit data
     → Actual test date and lab name

Output: Data/managed_care_benefit_deep.json

Run: python 08_benefit_appointment_deep.py
============================================================
"""
import sys, os, urllib, json
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import date, timedelta, datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import TRINO_HOST as HOST, TRINO_USER, TRINO_PASSWORD
PORT = 443
TODAY = date.today()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = next(
    (os.path.join(SCRIPT_DIR, d) for d in ["Data","data","DATA"]
     if os.path.isdir(os.path.join(SCRIPT_DIR, d))),
    os.path.join(SCRIPT_DIR, "Data")
)
OUT_PATH = os.path.join(DATA_DIR, "managed_care_benefit_deep.json")

PURELIFE_CODES = ['PURELIFE1','PURELIFE2','PURELIFE3','PURELIFE4','PURELIFE5']
VYTAL_CODES    = [
    'VYTAL0126','VYTAL0226','VYTAL0326','VYTAL0426','VYTAL0526',
    'VYTAL0626','VYTAL0726','VYTAL0826','VYTAL0926','VYTAL01026'
]
ALL_MC_CODES = PURELIFE_CODES + VYTAL_CODES

PROG_MAP = {
    'PURELIFE1':'Diabetes Management',    'VYTAL0126':'Diabetes Management',   'VYTAL0626':'Diabetes Management',
    'PURELIFE2':'Dyslipidemia Management','VYTAL0226':'Dyslipidemia Management','VYTAL0726':'Dyslipidemia Management',
    'PURELIFE3':'Thyroid Care',           'VYTAL0526':'Thyroid Care',           'VYTAL01026':'Thyroid Care',
    'PURELIFE4':'Liver Care',             'VYTAL0326':'Liver Care',             'VYTAL0826':'Liver Care',
    'PURELIFE5':'Kidney Care',            'VYTAL0426':'Kidney Care',            'VYTAL0926':'Kidney Care',
}

# Follow-up thresholds (days from appointment_date to follow-up due)
FOLLOWUP_THRESHOLDS = {
    'doctor_diet': {'Very High': 30,  'High': 60,  'Moderate': 90},
    'lab':         {'Very High': 90,  'High': 90,  'Moderate': 180},
}

# ── CONNECTION ────────────────────────────────────────────
pw  = urllib.parse.quote_plus(TRINO_PASSWORD)
URL = f"trino://{TRINO_USER}:{pw}@{HOST}:{PORT}/system?http_scheme=https"

def run_q(sql, label="", silent=False):
    try:
        engine = create_engine(URL)
        with engine.connect() as c:
            r  = c.execute(text(sql))
            df = pd.DataFrame(r.fetchall(), columns=r.keys())
        engine.dispose()
        if not silent:
            print(f"  [{label}] {len(df):,} rows")
        return df
    except Exception as e:
        if not silent:
            print(f"  ERR [{label}]: {str(e)[:300]}")
        return pd.DataFrame()

def show_cols(table, label=""):
    df = run_q(f"SHOW COLUMNS FROM {table}", label or table, silent=True)
    if df.empty:
        return []
    col = next((c for c in df.columns if c.lower() in ('column','col_name','name')), df.columns[0])
    return df[col].str.lower().tolist()


# ═══════════════════════════════════════════════════════════
# STEP 0 — Enrolled count from d_policy (source of truth)
# ═══════════════════════════════════════════════════════════
def fetch_enrolled_count(year_filter=None):
    """Return enrolled user count from d_policy — no duplication."""
    codes_sql = ", ".join(f"'{c}'" for c in (
        VYTAL_CODES    if year_filter == '2026' else
        PURELIFE_CODES if year_filter == '2025' else
        ALL_MC_CODES
    ))
    yr_clause = ""
    if year_filter == '2025':
        yr_clause = "AND SUBSTR(CAST(createddate AS VARCHAR),1,7) >= '2025-04' AND SUBSTR(CAST(createddate AS VARCHAR),1,7) <= '2026-03'"
    elif year_filter == '2026':
        yr_clause = "AND SUBSTR(CAST(createddate AS VARCHAR),1,7) >= '2026-04'"

    df = run_q(f"""
        SELECT COUNT(DISTINCT masterphrid) AS enrolled_count
        FROM deltalake.dl_standard_customermart.d_policy
        WHERE vlocity_ins_fsc__productcode__c IN ({codes_sql})
          AND masterphrid IS NOT NULL
          AND personmobilephone_hash IS NOT NULL
          AND (is_test_policy__c = FALSE OR is_test_policy__c IS NULL)
          {yr_clause}
    """, f"enrolled_{year_filter or 'all'}", silent=True)
    return int(df['enrolled_count'].iloc[0]) if not df.empty else 0


# ═══════════════════════════════════════════════════════════
# STEP 1 — Claims via d_policy join (zero duplication)
# ═══════════════════════════════════════════════════════════
def fetch_claims(year_filter=None):
    """
    Pull all MC benefit claims from f_claim.
    FIX: joins with d_policy (not customers table) — customers has 2-6 duplicate
         rows per phr_id which inflates row counts.
    Deduplicates by claim_id after join to eliminate any residual duplicates.
    Uses policy_effective_date as booking date proxy (f_claim has no created_at).
    """
    print(f"\n[Step 1] Claims via d_policy join — no customer-table duplication (year={year_filter or 'all'})...")

    codes_sql = ", ".join(f"'{c}'" for c in (
        VYTAL_CODES    if year_filter == '2026' else
        PURELIFE_CODES if year_filter == '2025' else
        ALL_MC_CODES
    ))

    # Programme year window filter on policy createddate
    yr_clause = ""
    if year_filter == '2025':
        yr_clause = "AND SUBSTR(CAST(p.createddate AS VARCHAR),1,7) >= '2025-04' AND SUBSTR(CAST(p.createddate AS VARCHAR),1,7) <= '2026-03'"
    elif year_filter == '2026':
        yr_clause = "AND SUBSTR(CAST(p.createddate AS VARCHAR),1,7) >= '2026-04'"

    sql = f"""
        SELECT
            p.personmobilephone_hash        AS mobile_number_hash,
            fc.phr_id,
            fc.product_code,
            fc.benefit_name,
            fc.claim_status,
            fc.claim_type,
            fc.claim_id,
            fc.provider_name,
            fc.provider_type,
            SUBSTR(CAST(p.createddate AS VARCHAR),1,10) AS policy_date,
            SUBSTR(CAST(p.createddate AS VARCHAR),1,7)  AS policy_month
        FROM deltalake.dl_standard_customermart.f_claim fc
        JOIN deltalake.dl_standard_customermart.d_policy p
            ON fc.phr_id   = p.masterphrid
           AND fc.product_code = p.vlocity_ins_fsc__productcode__c
        WHERE fc.product_code IN ({codes_sql})
          AND p.personmobilephone_hash IS NOT NULL
          AND (p.is_test_policy__c = FALSE OR p.is_test_policy__c IS NULL)
          {yr_clause}
    """
    df_raw = run_q(sql, f"claims_raw_{year_filter or 'all'}")
    if df_raw.empty:
        return df_raw

    # Deduplicate by claim_id (d_policy may still have multiple policies per user)
    before = len(df_raw)
    df = df_raw.drop_duplicates(subset='claim_id').copy()
    print(f"  Dedup: {before:,} → {len(df):,} rows  ({before-len(df):,} duplicates removed)")
    print(f"  Unique claim_ids    : {df['claim_id'].nunique():,}")
    print(f"  Unique users        : {df['mobile_number_hash'].nunique():,}")

    nc = df[~df['claim_status'].str.lower().isin(['cancelled','cancel'])]
    print(f"\n  --- Benefit name (non-cancelled) ---")
    print(nc.groupby('benefit_name').agg(
        claims=('claim_id','count'), unique_users=('mobile_number_hash','nunique')
    ).sort_values('claims', ascending=False).to_string())

    print(f"\n  --- Claim status ---")
    print(df['claim_status'].value_counts(dropna=False).to_string())

    return df


# ═══════════════════════════════════════════════════════════
# STEP 2 — Appointment flat table: deduplicated by appointmentid
# ═══════════════════════════════════════════════════════════
def fetch_appt_flat(mobile_hashes, year_filter=None):
    """
    Pulls appointments from f_appointmentflattable.
    FIX 1: deduplicate by appointmentid using ROW_NUMBER() — the table has
            multiple rows per appointmentid (audit/update trail).
    FIX 2: join with d_policy (not customers table) to get mobile_number_hash
            without row multiplication.
    Classifies benefit category via speciality column (more reliable than
    benefit_name__c which differs between tables).
    """
    print(f"\n[Step 2] Appointment flat table — dedup by appointmentid, d_policy join (year={year_filter or 'all'})...")
    TABLE = "deltalake.dl_standard_pbireporting.f_appointmentflattable"

    codes_sql = ", ".join(f"'{c}'" for c in (
        VYTAL_CODES    if year_filter == '2026' else
        PURELIFE_CODES if year_filter == '2025' else
        ALL_MC_CODES
    ))

    # date filter goes INSIDE the subquery — bare column names, no alias prefix
    inner_date_filter = ""
    if year_filter == '2025':
        inner_date_filter = "AND appointmentdate >= DATE '2025-04-01' AND appointmentdate <= DATE '2026-03-31'"
    elif year_filter == '2026':
        inner_date_filter = "AND appointmentdate >= DATE '2026-04-01'"

    sql = f"""
        SELECT
            p.personmobilephone_hash                    AS mobile_number_hash,
            a.phrid                                     AS phr_id,
            a.appointmentid                             AS appt_id,
            CAST(a.appointmentdate AS DATE)             AS appt_date,
            CAST(a.appointmentbookingdate AS DATE)      AS booking_date,
            a.appointmentstatus                         AS appt_status,
            a.appointmentcategory                       AS appt_category,
            a.vlocity_ins_fsc__productcode__c           AS product_code,
            a.benefit_name__c                           AS benefit_name,
            a.speciality,
            a.isfollowupappointment                     AS is_followup,
            a.claimstatus                               AS claim_status,
            a.claimid                                   AS claim_id
        FROM (
            SELECT appointmentid, phrid, appointmentdate, appointmentbookingdate,
                   appointmentstatus, appointmentcategory,
                   vlocity_ins_fsc__productcode__c,
                   benefit_name__c, speciality,
                   isfollowupappointment, claimstatus, claimid,
                   ROW_NUMBER() OVER (
                       PARTITION BY appointmentid
                       ORDER BY recordupdatedat DESC
                   ) AS rn
            FROM {TABLE}
            WHERE vlocity_ins_fsc__productcode__c IN ({codes_sql})
              AND (istestappt = 0 OR istestappt IS NULL)
              {inner_date_filter}
        ) a
        JOIN deltalake.dl_standard_customermart.d_policy p
            ON a.phrid                          = p.masterphrid
           AND a.vlocity_ins_fsc__productcode__c = p.vlocity_ins_fsc__productcode__c
        WHERE a.rn = 1
          AND (p.is_test_policy__c = FALSE OR p.is_test_policy__c IS NULL)
          AND p.personmobilephone_hash IS NOT NULL
    """
    df = run_q(sql, f"appt_flat_{year_filter or 'all'}")
    if df.empty:
        return df

    df['appt_date']    = pd.to_datetime(df['appt_date'],    errors='coerce').dt.date
    df['booking_date'] = pd.to_datetime(df['booking_date'],  errors='coerce').dt.date

    print(f"  Unique appointments (appt_id): {df['appt_id'].nunique():,}")
    print(f"  Unique users                 : {df['mobile_number_hash'].nunique():,}")
    print(f"  Date range                   : {df['appt_date'].min()} → {df['appt_date'].max()}")

    print(f"\n  --- Status ---")
    print(df['appt_status'].value_counts(dropna=False).to_string())
    print(f"\n  --- Benefit name ---")
    print(df['benefit_name'].value_counts(dropna=False).to_string())
    print(f"\n  --- Speciality ---")
    print(df['speciality'].value_counts(dropna=False).head(10).to_string())

    # Classify using speciality (more reliable than benefit_name)
    DIET_SPEC = {'dietitian/nutritionist','nutritionist','dietician','dietitian'}
    LAB_SPEC  = {'pathologist','radiologist','lab technician','diagnostics'}
    def classify(row):
        spec = str(row.get('speciality','') or '').lower()
        bn   = str(row.get('benefit_name','') or '').lower()
        if any(k in spec for k in DIET_SPEC) or 'nutrit' in bn or 'wellness program' in bn:
            return 'diet'
        if 'general physician' in spec or spec == 'physician' or ('tele' in bn and 'diet' not in spec):
            return 'doctor'
        if any(k in spec for k in LAB_SPEC) or 'lab' in bn or 'health monit' in bn:
            return 'lab'
        return 'other'

    df['benefit_cat'] = df.apply(classify, axis=1)

    print(f"\n  --- Benefit category after classify ---")
    print(df['benefit_cat'].value_counts().to_string())

    return df


# ═══════════════════════════════════════════════════════════
# STEP 3 — Lab data from customermart
# ═══════════════════════════════════════════════════════════
def fetch_lab_data(mobile_hashes, year_filter=None):
    """
    Try to find lab order/test data in customermart for enrolled MC users.
    """
    print(f"\n[Step 3] Lab data from customermart (year={year_filter or 'all'})...")

    # Discover lab tables
    lab_table_candidates = [
        "deltalake.dl_standard_customermart.f_lab_order",
        "deltalake.dl_standard_customermart.f_lab_orders",
        "deltalake.dl_standard_customermart.lab_orders",
        "deltalake.dl_standard_customermart.f_lab_report",
        "deltalake.dl_standard_customermart.f_lab_test",
        "deltalake.dl_standard_customermart.lab_tests",
        "deltalake.dl_standard_customermart.lab_results",
        "central.phrservice.labreports",
        "central.phrservice.lab_reports",
    ]

    lab_table = None
    for t in lab_table_candidates:
        cols = show_cols(t, label=t)
        if cols:
            print(f"  Found: {t}  ({len(cols)} cols: {cols[:10]})")
            lab_table = t
            break

    if not lab_table:
        print("  No lab table found — checking what lab-related tables exist in customermart...")
        df_tabs = run_q("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_catalog = 'deltalake'
              AND (LOWER(table_name) LIKE '%lab%' OR LOWER(table_name) LIKE '%test%')
              AND table_schema LIKE '%customermart%'
            LIMIT 30
        """, "lab_tables_discovery")
        if not df_tabs.empty:
            print(df_tabs.to_string(index=False))
        return pd.DataFrame()

    codes_sql = ", ".join(f"'{c}'" for c in (VYTAL_CODES if year_filter=='2026' else PURELIFE_CODES if year_filter=='2025' else ALL_MC_CODES))
    hashes_sql = ", ".join(f"'{h}'" for h in list(mobile_hashes)[:500])
    cols = show_cols(lab_table)

    # Try common column patterns
    mob_col  = next((c for c in ['mobile_number_hash','mobile_hash','phone_hash','mobilehash'] if c in cols), None)
    date_col = next((c for c in ['test_date','order_date','created_at','service_date','report_date','lab_date'] if c in cols), None)
    status_col = next((c for c in ['status','order_status','test_status','report_status'] if c in cols), None)

    if not mob_col:
        print(f"  Cannot find mobile_number_hash column in {lab_table}. Cols: {cols[:20]}")
        return pd.DataFrame()

    date_expr = f"CAST({date_col} AS DATE) AS lab_date" if date_col else "NULL AS lab_date"
    status_expr = f"{status_col} AS lab_status" if status_col else "NULL AS lab_status"

    sql = f"""
        SELECT {mob_col} AS mobile_number_hash,
               {date_expr},
               {status_expr}
        FROM {lab_table}
        WHERE {mob_col} IN ({hashes_sql})
        LIMIT 5000
    """
    df = run_q(sql, "lab_data")
    if not df.empty:
        print(f"  Lab date range: {df['lab_date'].min()} → {df['lab_date'].max()}")
        if 'lab_status' in df.columns:
            print(f"  Status breakdown:\n{df['lab_status'].value_counts().to_string()}")
    return df


# ═══════════════════════════════════════════════════════════
# STEP 4 — Compute follow-up pending (appt_date based)
# ═══════════════════════════════════════════════════════════
def compute_followup_from_flat(df_flat, df_claims_lab, enrolled_n, year_label):
    """
    For each user per benefit category:
    - Use appt_date from flat table (doctor/diet)
    - Use claim_date from claims table (lab, others)
    - Calculate days since last appointment
    - Flag pending based on cohort threshold
    Note: cohort data not yet available for VYTAL users, so all users shown without
    cohort split; split will be populated when impact scores for VYTAL are available.
    """
    print(f"\n[Step 4] Follow-Up Pending — {year_label}...")

    results = {}

    # ── Doctor + Diet (from flat table) ──────────────────
    for cat in ['doctor', 'diet']:
        cat_df = df_flat[df_flat['benefit_cat'] == cat] if not df_flat.empty else pd.DataFrame()
        cat_df = cat_df[~cat_df['appt_status'].str.upper().isin(['CAN','CANCEL'])] if not cat_df.empty else cat_df

        if cat_df.empty:
            results[cat] = {'no_data': True, 'note': 'No appointments in flat table for this category'}
            print(f"  [{cat}] No data")
            continue

        last = cat_df.groupby('mobile_number_hash').agg(
            last_appt_date=('appt_date','max'),
            total_appts   =('claim_id','count'),
            completed     =('appt_status', lambda x: (x.str.upper()=='COM').sum()),
        ).reset_index()

        last['days_since']    = last['last_appt_date'].apply(
            lambda d: (TODAY - d).days if pd.notna(d) else None)
        last['followup_due']  = last['last_appt_date'].apply(
            lambda d: d + timedelta(days=30) if pd.notna(d) else None)  # VH = 30d default

        cat_res = {
            'unique_users':     int(len(last)),
            'total_appts':      int(last['total_appts'].sum()),
            'completed_appts':  int(last['completed'].sum()),
            'last_appt_range': {
                'min': str(last['last_appt_date'].min()),
                'max': str(last['last_appt_date'].max()),
            },
            'followup_thresholds': FOLLOWUP_THRESHOLDS['doctor_diet'],
        }

        for cohort_label, threshold_days in FOLLOWUP_THRESHOLDS['doctor_diet'].items():
            pending  = last[last['days_since'] > threshold_days]
            not_yet  = last[last['days_since'] <= threshold_days]
            cat_res[cohort_label.lower().replace(' ','_')] = {
                'threshold_days':   threshold_days,
                'cohort_label':     cohort_label,
                'total_with_appt':  int(len(last)),
                'pending_followup': int(len(pending)),
                'pending_pct':      round(len(pending)/max(len(last),1)*100, 1),
                'within_window':    int(len(not_yet)),
                'note':             'All users shown (cohort scores pending for VYTAL)',
            }
            print(f"  [{cat}] {cohort_label:<12} total={len(last):>4}  "
                  f"pending(>{threshold_days}d)={len(pending):>4}  "
                  f"({round(len(pending)/max(len(last),1)*100,1)}%)  "
                  f"within_window={len(not_yet):>4}")

            # Show upcoming due dates
            due_df = last[last['days_since'].between(0, threshold_days)].copy()
            if not due_df.empty:
                due_df['due_date'] = due_df['last_appt_date'].apply(
                    lambda d: d + timedelta(days=threshold_days) if pd.notna(d) else None)
                next7 = due_df[due_df['due_date'] <= TODAY + timedelta(days=7)]
                print(f"    Due within 7 days: {len(next7)}")

        results[cat] = cat_res

    # ── Lab (from claims table) ───────────────────────────
    if not df_claims_lab.empty:
        lab_nc = df_claims_lab[
            ~df_claims_lab['claim_status'].str.lower().isin(['cancelled','cancel'])
        ].copy()
        if 'claim_date' in lab_nc.columns:
            lab_nc['claim_date'] = pd.to_datetime(lab_nc['claim_date'], errors='coerce').dt.date
            last_lab = lab_nc.groupby('mobile_number_hash')['claim_date'].max().reset_index()
            last_lab.columns = ['mobile_number_hash','last_lab_date']
            last_lab['days_since'] = last_lab['last_lab_date'].apply(
                lambda d: (TODAY - d).days if pd.notna(d) else None)

            lab_res = {
                'unique_users': int(len(last_lab)),
                'last_lab_range': {
                    'min': str(last_lab['last_lab_date'].min()),
                    'max': str(last_lab['last_lab_date'].max()),
                },
                'followup_thresholds': FOLLOWUP_THRESHOLDS['lab'],
            }
            for cohort_label, threshold_days in FOLLOWUP_THRESHOLDS['lab'].items():
                pending = last_lab[last_lab['days_since'] > threshold_days]
                lab_res[cohort_label.lower().replace(' ','_')] = {
                    'threshold_days':   threshold_days,
                    'cohort_label':     cohort_label,
                    'total_with_appt':  int(len(last_lab)),
                    'pending_followup': int(len(pending)),
                    'pending_pct':      round(len(pending)/max(len(last_lab),1)*100,1),
                }
                print(f"  [lab] {cohort_label:<12} total={len(last_lab):>4}  "
                      f"pending(>{threshold_days}d)={len(pending):>4}")
            results['lab'] = lab_res
        else:
            results['lab'] = {'no_data': True, 'note': 'No claim_date column in lab claims'}
    else:
        results['lab'] = {'no_data': True, 'note': 'No lab claim data available'}

    return results


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    print("\n" + "="*64)
    print("  Managed Care 3.0 — Script 08: Benefit + Appointment Deep")
    print(f"  Today: {TODAY}")
    print("="*64)

    output = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'today':        str(TODAY),
        'by_year':      {},
    }

    for yr in ['2025', '2026']:
        print(f"\n{'='*64}")
        print(f"  Processing Year: {yr}")
        print(f"{'='*64}")

        # Step 0: True enrolled count from d_policy
        enrolled_n = fetch_enrolled_count(year_filter=yr)
        print(f"\n  Enrolled (d_policy): {enrolled_n:,}")

        # Step 1: Claims
        df_claims = fetch_claims(year_filter=yr)
        if df_claims.empty:
            print(f"  No claims data for {yr} — skipping")
            output['by_year'][yr] = {'no_data': True, 'enrolled_users': enrolled_n}
            continue

        mobile_hashes = set(df_claims['mobile_number_hash'].dropna().astype(str))

        # Claims summary for ALL benefits (with date)
        nc = df_claims[~df_claims['claim_status'].str.lower().isin(['cancelled','cancel'])].copy()
        if 'claim_date' in nc.columns:
            nc['claim_date'] = pd.to_datetime(nc['claim_date'], errors='coerce').dt.date
            nc['claim_month'] = nc['claim_date'].apply(lambda d: str(d)[:7] if pd.notna(d) else None)

        # Per-user per-benefit summary
        benefit_summary = {}
        for bn in nc['benefit_name'].dropna().unique():
            grp = nc[nc['benefit_name']==bn]
            per_user = grp.groupby('mobile_number_hash').agg(
                total_claims=('claim_id','count'),
                unique_claims=('claim_id','nunique'),
                first_claim=('claim_date','min') if 'claim_date' in grp.columns else ('claim_id','count'),
                last_claim=('claim_date','max')  if 'claim_date' in grp.columns else ('claim_id','count'),
            ).reset_index()

            n_users = len(per_user)
            n1  = int((per_user['unique_claims']==1).sum())
            n2  = int((per_user['unique_claims']==2).sum())
            n3  = int((per_user['unique_claims']==3).sum())
            n4  = int((per_user['unique_claims']==4).sum())
            n5  = int((per_user['unique_claims']==5).sum())
            n5p = int((per_user['unique_claims']>5).sum())

            # Monthly trend
            if 'claim_month' in nc.columns:
                monthly = (grp.groupby('claim_month')['claim_id'].count()
                           .reset_index().rename(columns={'claim_id':'count'}))
                monthly_trend = monthly.to_dict('records')
            else:
                monthly_trend = []

            benefit_summary[str(bn)] = {
                'total_users':   n_users,
                'total_claims':  int(grp['claim_id'].count()),
                'repeat_users':  n2+n3+n4+n5+n5p,
                'users_1x':      n1, 'users_2x': n2, 'users_3x': n3,
                'users_4x':      n4, 'users_5x': n5, 'users_5x_plus': n5p,
                'first_booking': str(per_user['first_claim'].min()) if 'first_claim' in per_user.columns else None,
                'last_booking':  str(per_user['last_claim'].max())  if 'last_claim'  in per_user.columns else None,
                'monthly_trend': monthly_trend,
            }

        # Claims: lab benefits only (for lab follow-up)
        LAB_BENEFITS = ['lab discounts','health monitoring']
        df_claims_lab = nc[nc['benefit_name'].str.lower().isin(LAB_BENEFITS)].copy() if not nc.empty else pd.DataFrame()
        print(f"\n  Lab claims rows: {len(df_claims_lab):,}")

        # Step 2: Appointment flat table (ROW_NUMBER dedup + d_policy join)
        df_flat = fetch_appt_flat(mobile_hashes, year_filter=yr)

        # Flat table summary — deduped by appt_id
        flat_summary = {}
        if not df_flat.empty:
            for bn in df_flat['benefit_name'].dropna().unique():
                grp = df_flat[df_flat['benefit_name']==bn]
                nc_grp = grp[~grp['appt_status'].str.upper().isin(['CAN','CANCEL'])]
                flat_summary[str(bn)] = {
                    'total_appts':      int(grp['appt_id'].nunique()),
                    'unique_users':     int(grp['mobile_number_hash'].nunique()),
                    'completed_COM':    int((nc_grp['appt_status'].str.upper()=='COM').sum()),
                    'booked':           int(nc_grp['appt_status'].str.upper().isin(['BOOKED','CONFIRMED']).sum()),
                    'rescheduled_RES':  int((nc_grp['appt_status'].str.upper()=='RES').sum()),
                    'cancelled_CAN':    int(grp['appt_status'].str.upper().isin(['CAN','CANCEL']).sum()),
                    'speciality_dist':  nc_grp['speciality'].value_counts().head(10).to_dict(),
                    'date_range': {
                        'min': str(nc_grp['appt_date'].min()) if not nc_grp.empty else None,
                        'max': str(nc_grp['appt_date'].max()) if not nc_grp.empty else None,
                    },
                    'is_followup_count': int((nc_grp['is_followup']==True).sum()),
                }

            # Total across all benefits (non-cancelled)
            nc_flat = df_flat[~df_flat['appt_status'].str.upper().isin(['CAN','CANCEL'])]
            flat_summary['__totals__'] = {
                'total_unique_appts': int(df_flat['appt_id'].nunique()),
                'total_unique_users': int(df_flat['mobile_number_hash'].nunique()),
                'completed_COM':      int((nc_flat['appt_status'].str.upper()=='COM').sum()),
                'booked':             int(nc_flat['appt_status'].str.upper().isin(['BOOKED','CONFIRMED']).sum()),
                'rescheduled_RES':    int((nc_flat['appt_status'].str.upper()=='RES').sum()),
                'cancelled_CAN':      int(df_flat['appt_status'].str.upper().isin(['CAN','CANCEL']).sum()),
                'never_booked':       max(0, enrolled_n - int(df_flat['mobile_number_hash'].nunique())),
            }
            print(f"\n  FLAT TOTALS: appts={flat_summary['__totals__']['total_unique_appts']}  "
                  f"COM={flat_summary['__totals__']['completed_COM']}  "
                  f"BOOKED={flat_summary['__totals__']['booked']}  "
                  f"never_booked={flat_summary['__totals__']['never_booked']}")

            # Daily trend — unique users per appt_date (non-cancelled)
            daily_trend = (nc_flat.groupby('appt_date')['mobile_number_hash']
                           .nunique().reset_index()
                           .rename(columns={'mobile_number_hash':'unique_users'})
                           .sort_values('appt_date'))
            daily_trend_list = [{'date': str(r['appt_date']), 'unique_users': int(r['unique_users'])}
                                 for _, r in daily_trend.iterrows()]
        else:
            daily_trend_list = []

        # Step 3: Lab data
        df_lab = fetch_lab_data(mobile_hashes, year_filter=yr)

        # Step 4: Follow-up pending
        followup = compute_followup_from_flat(df_flat, df_claims_lab, enrolled_n, yr)

        # Assemble year output
        users_with_appts = int(df_flat['mobile_number_hash'].nunique()) if not df_flat.empty else 0
        output['by_year'][yr] = {
            'year_label':        '2025 – PURELIFE (Apr 2025 – Mar 2026)' if yr=='2025' else '2026 – VYTAL (Apr 2026 – Mar 2027)',
            'enrolled_users':    enrolled_n,
            'users_with_claims': int(df_claims['mobile_number_hash'].nunique()) if not df_claims.empty else 0,
            'users_with_appts':  users_with_appts,
            'never_booked':      max(0, enrolled_n - users_with_appts),
            'claims_summary':    benefit_summary,
            'appt_flat_summary': flat_summary,
            'daily_trend_flat':  daily_trend_list,
            'followup_pending':  followup,
        }

        print(f"\n  === {yr} SUMMARY ===")
        print(f"  Enrolled users : {enrolled_n:,}")
        print(f"  Benefits found : {list(benefit_summary.keys())}")
        for bn, v in benefit_summary.items():
            print(f"    {str(bn)[:45]:<45} users={v['total_users']:>5}  repeat={v['repeat_users']:>4}")

    # Save JSON
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n[Done] Saved → {OUT_PATH}")
    print("="*64)


if __name__ == "__main__":
    main()
