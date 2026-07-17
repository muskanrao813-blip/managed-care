"""
VYTAL 2026 appointments from f_appointmentflattable.
Key columns found: phrid, appointmentdate, appointmentstatus, appointmentbookingdate,
                   vlocity_ins_fsc__productcode__c, benefit_name__c, isfollowupappointment,
                   appointmentcategory, speciality
"""
import sys, os, urllib
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import date, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from config import TRINO_HOST as HOST, TRINO_USER, TRINO_PASSWORD
PORT = 443
TODAY = date.today()

VYTAL_CODES = [
    'VYTAL0126','VYTAL0226','VYTAL0326','VYTAL0426','VYTAL0526',
    'VYTAL0626','VYTAL0726','VYTAL0826','VYTAL0926','VYTAL01026'
]
cs = ", ".join(f"'{c}'" for c in VYTAL_CODES)

pw  = urllib.parse.quote_plus(TRINO_PASSWORD)
url = f"trino://{TRINO_USER}:{pw}@{HOST}:{PORT}/system?http_scheme=https"
TABLE = "deltalake.dl_standard_pbireporting.f_appointmentflattable"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(SCRIPT_DIR, "Data")

def run_q(sql, label=""):
    try:
        engine = create_engine(url)
        with engine.connect() as c:
            r = c.execute(text(sql))
            df = pd.DataFrame(r.fetchall(), columns=r.keys())
        engine.dispose()
        print(f"  [{label}] {len(df):,} rows")
        return df
    except Exception as e:
        print(f"  ERR [{label}]: {str(e)[:400]}")
        return pd.DataFrame()

print("=" * 64)
print(f"  VYTAL Appointment Flat Table Analysis  |  Today: {TODAY}")
print("=" * 64)

# ── Step 1: VYTAL appointments from f_appointmentflattable ──
print("\n[1] All VYTAL appointments (Apr 2026+) from flat table...")
df_appt = run_q(f"""
    SELECT
        phrid                                   AS phr_id,
        appointmentdate                         AS appt_date,
        CAST(appointmentdate AS DATE)           AS appt_date_dt,
        appointmentstatus                       AS status,
        appointmentbookingdate                  AS booking_date,
        appointmentcategory                     AS appt_category,
        vlocity_ins_fsc__productcode__c         AS product_code,
        benefit_name__c                         AS benefit_name,
        isfollowupappointment                   AS is_followup,
        claimstatus                             AS claim_status,
        claimid                                 AS claim_id,
        speciality,
        CAST(appointmentbookingdate AS DATE)    AS booking_date_dt,
        istestappt
    FROM {TABLE}
    WHERE vlocity_ins_fsc__productcode__c IN ({cs})
      AND (istestappt = 0 OR istestappt IS NULL)
      AND appointmentdate >= DATE '2026-04-01'
    ORDER BY phr_id, appt_date
""", "vytal_appts")

if df_appt.empty:
    print("  No VYTAL appointments found. Exiting.")
    sys.exit(1)

print(f"\n=== RAW OVERVIEW ===")
print(f"Total rows              : {len(df_appt):,}")
print(f"Unique phr_ids          : {df_appt['phr_id'].nunique():,}")
print(f"Date range              : {df_appt['appt_date'].min()} → {df_appt['appt_date'].max()}")

print(f"\n--- Appointment Status ---")
print(df_appt['status'].value_counts(dropna=False).to_string())

print(f"\n--- Appointment Category ---")
print(df_appt['appt_category'].value_counts(dropna=False).to_string())

print(f"\n--- Benefit Name ---")
print(df_appt['benefit_name'].value_counts(dropna=False).head(20).to_string())

print(f"\n--- Product Code ---")
print(df_appt['product_code'].value_counts(dropna=False).to_string())

print(f"\n--- Speciality (top 15) ---")
print(df_appt['speciality'].value_counts(dropna=False).head(15).to_string())

print(f"\n--- Is Follow-Up Appointment ---")
print(df_appt['is_followup'].value_counts(dropna=False).to_string())

print(f"\n--- Claim Status ---")
print(df_appt['claim_status'].value_counts(dropna=False).to_string())

# ── Step 2: Completed appointments ──────────────────────────
print(f"\n[2] Completed appointments (status = COM)...")
df_done = df_appt[df_appt['status'].str.upper() == 'COM'].copy()
print(f"  Completed: {len(df_done):,} rows  |  {df_done['phr_id'].nunique():,} unique users")

if not df_done.empty:
    print(f"\n--- Completed by benefit ---")
    print(df_done['benefit_name'].value_counts(dropna=False).to_string())

    print(f"\n--- Completed by product code ---")
    print(df_done['product_code'].value_counts(dropna=False).to_string())

    print(f"\n--- Completed appointment dates ---")
    done_dates = pd.to_datetime(df_done['appt_date'], errors='coerce').dt.date
    print(f"  Date range: {done_dates.min()} → {done_dates.max()}")
    print(f"  By month:")
    monthly = done_dates.apply(lambda d: str(d)[:7] if pd.notna(d) else None).value_counts().sort_index()
    print(monthly.to_string())

# ── Step 3: Upcoming / Booked ────────────────────────────────
print(f"\n[3] Booked (upcoming) appointments...")
df_booked = df_appt[df_appt['status'].str.upper().isin(['BOOKED','CONFIRMED','SCHEDULED'])].copy()
print(f"  Booked: {len(df_booked):,} rows  |  {df_booked['phr_id'].nunique():,} unique users")
if not df_booked.empty:
    print(f"  Future dates:")
    fut = pd.to_datetime(df_booked['appt_date'], errors='coerce').dt.date
    print(f"    Range: {fut.min()} → {fut.max()}")
    print(f"    Count >{TODAY}: {(fut > TODAY).sum()}")

# ── Step 4: Follow-Up Pending Analysis ──────────────────────
print(f"\n[4] Follow-Up Pending Analysis (by cohort threshold)...")

# Use ALL non-cancelled as "attended" (Authorized = attended, per PM)
df_active = df_appt[~df_appt['status'].str.upper().isin(['CANCELLED','CANCEL'])].copy()
df_active['appt_date_dt'] = pd.to_datetime(df_active['appt_date'], errors='coerce').dt.date

# Category classification
DOCTOR_DIET_BENEFITS = ['nutritionist','teleconsultation','diet','wellness inclinic','consultation']
LAB_BENEFITS         = ['lab','diagnostic','health monitoring','test']

def classify_benefit(b):
    b = str(b or '').lower()
    if any(k in b for k in LAB_BENEFITS):     return 'lab'
    if any(k in b for k in DOCTOR_DIET_BENEFITS): return 'doctor_diet'
    return 'other'

df_active['benefit_cat'] = df_active['benefit_name'].apply(classify_benefit)
print(f"  Benefit category split:")
print(df_active['benefit_cat'].value_counts().to_string())

# Thresholds (days since last appointment → overdue)
THRESHOLDS = {
    'doctor_diet': {'Very High': 30, 'High': 60,  'Moderate': 90},
    'lab':         {'Very High': 90, 'High': 90,  'Moderate': 180},
}

# Load enrolled phr_ids + product code to get cohort info
# We'll use impact scores from CSV
IMPACT_CSV = os.path.join(DATA_DIR, "managed_care_impact_scores.csv")
if os.path.exists(IMPACT_CSV):
    imp = pd.read_csv(IMPACT_CSV)
    imp_max = imp.groupby('mobile_number_hash')['scaled_score'].max().reset_index()
    def cohort(s):
        if s>=75: return 'Very High'
        if s>=50: return 'High'
        if s>=25: return 'Moderate'
        return 'Low'
    imp_max['cohort'] = imp_max['scaled_score'].apply(cohort)
    # We need phr_id → mobile_hash → cohort; get phr_id from enrolled
    ENRL_CSV = os.path.join(DATA_DIR, "managed_care_enrolled_phrs.csv")
    if os.path.exists(ENRL_CSV):
        enrl = pd.read_csv(ENRL_CSV)
        vytal_enrl = enrl[enrl['mc_product_code'].isin(VYTAL_CODES)][['phr_id','mobile_number_hash']].drop_duplicates()
        cohort_map = dict(zip(
            imp_max.merge(vytal_enrl, on='mobile_number_hash', how='inner')['phr_id'],
            imp_max.merge(vytal_enrl, on='mobile_number_hash', how='inner')['cohort']
        ))
        print(f"\n  Cohort-mapped VYTAL users: {len(cohort_map):,}")
    else:
        cohort_map = {}
else:
    cohort_map = {}

for cat in ['doctor_diet', 'lab']:
    cat_df = df_active[df_active['benefit_cat'] == cat].copy()
    if cat_df.empty:
        print(f"\n  [{cat}] No data")
        continue

    # Last appointment date per user
    last_appt = (cat_df.groupby('phr_id')['appt_date_dt']
                       .max().reset_index()
                       .rename(columns={'appt_date_dt':'last_appt'}))
    last_appt['cohort']     = last_appt['phr_id'].map(cohort_map).fillna('Unknown')
    last_appt['days_since'] = last_appt['last_appt'].apply(
        lambda d: (TODAY - d).days if pd.notna(d) else None
    )

    print(f"\n  [{cat.upper()}] {len(last_appt):,} users | cohort-mapped: {(last_appt['cohort']!='Unknown').sum():,}")
    print(f"  Last appt date range: {last_appt['last_appt'].min()} → {last_appt['last_appt'].max()}")
    print(f"  Days since (min/max): {last_appt['days_since'].min()} / {last_appt['days_since'].max()}")

    for cohort_name, threshold_days in THRESHOLDS[cat].items():
        grp     = last_appt[last_appt['cohort'] == cohort_name]
        pending = grp[grp['days_since'] > threshold_days]
        total   = len(grp)
        n       = len(pending)
        pct     = round(n/total*100,1) if total > 0 else 0
        print(f"    {cohort_name:<12} total={total:>4}  pending(>{threshold_days}d)={n:>4}  ({pct}%)")
        if n > 0:
            print(f"      Days since range for pending: {pending['days_since'].min()} – {pending['days_since'].max()}")

# ── Step 5: Repeat booking check ────────────────────────────
print(f"\n[5] Repeat Bookings from Appointment Flat Table...")
df_nc = df_appt[~df_appt['status'].str.upper().isin(['CANCELLED','CANCEL'])].copy()
per_user = df_nc.groupby(['phr_id','benefit_name'])['claim_id'].nunique().reset_index()
per_user.columns = ['phr_id','benefit_name','n_appts']

print(f"\n  Benefit × frequency distribution:")
for bn in per_user['benefit_name'].dropna().unique():
    grp  = per_user[per_user['benefit_name']==bn]['n_appts']
    n1   = (grp==1).sum()
    n2   = (grp==2).sum()
    n3p  = (grp>=3).sum()
    rep  = n2 + n3p
    print(f"  {str(bn):<45} total={len(grp):>4}  1x={n1}  2x={n2}  3x+={n3p}  repeat={rep}")

# ── Step 6: Save full VYTAL appointment data ─────────────────
out_path = os.path.join(DATA_DIR, "vytal_appt_flat.csv")
df_appt.to_csv(out_path, index=False)
print(f"\n[Saved] {out_path}  ({len(df_appt):,} rows)")
print("=" * 64)
