"""
============================================================
MANAGED CARE 3.0 — SCRIPT 3b: Device & Lifestyle Eligibility (2026)
============================================================
Purpose:
  - For each VYTAL-enrolled user (2026), score eligibility for:
      Devices     : CGM, Glucometer, Weighing Machine, BP Monitor (100 slots each)
      Assessments : Metabolic Syndrome, Stress Impact, Alcohol Impact
  - Inputs : managed_care_policy_data.csv (enrolled VYTAL users + cohort)
             managed_care_hra_wellness.csv (HRA from fetch_hra_wellness.py)
             Trino: f_claim biomarkers (BPC01/02/03)
             Trino: f_claim VYTAL appointments
  - Scoring: Clinical 30% + Engagement 25% + Adherence 25% + Lifestyle 20%
  - Allocation: top 100 per device type, priority Very High > High > Moderate,
                then engagement_score DESC
  - Output: managed_care_device_eligibility_2026.csv

Non-interactive — safe for daily pipeline.
Run after: Script 01, Script 02, Script 04, fetch_hra_wellness.py
============================================================
"""

import sys, os, math, urllib
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ── PATHS ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = next((os.path.join(SCRIPT_DIR, d) for d in ["Data","data","DATA"]
                   if os.path.isdir(os.path.join(SCRIPT_DIR, d))),
                  os.path.join(SCRIPT_DIR, "Data"))

POLICY_CSV  = os.path.join(DATA_DIR, "managed_care_policy_data.csv")
HRA_CSV     = os.path.join(DATA_DIR, "managed_care_hra_wellness.csv")
OUTPUT_PATH = os.path.join(DATA_DIR, "managed_care_device_eligibility_2026.csv")

# ── TRINO ─────────────────────────────────────────────────────────────────────
from config import TRINO_HOST, TRINO_USER, TRINO_PASSWORD
_pw  = urllib.parse.quote_plus(TRINO_PASSWORD)
_ENG = None

def get_engine():
    global _ENG
    if _ENG is None:
        _ENG = create_engine(
            f'trino://{TRINO_USER}:{_pw}@{TRINO_HOST}:{443}/system?http_scheme=https'
        )
    return _ENG

def q(sql, label='', retry=1):
    try:
        with get_engine().connect() as c:
            r = c.execute(text(sql))
            df = pd.DataFrame(r.fetchall(), columns=r.keys())
        print(f"    [{label}] {len(df):,} rows")
        return df
    except Exception as e:
        print(f"    ERR [{label}]: {str(e)[:200]}")
        if retry > 0:
            return q(sql, label, retry-1)
        return pd.DataFrame()

def sql_list(vals):
    return ', '.join(f"'{v}'" for v in vals)

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
COHORT_RANK    = {'Very High': 1, 'High': 2, 'Moderate': 3}
DEVICE_SLOTS   = {'CGM': 100, 'Glucometer': 100, 'Weighing Machine': 100, 'BP Monitor': 100}
LIFESTYLE_SLOTS = {'Metabolic Syndrome': 100, 'Stress Impact': 100, 'Alcohol Impact': 100}

VYTAL_CODES = [
    'VYTAL0126','VYTAL0226','VYTAL0326','VYTAL0426','VYTAL0526',
    'VYTAL0626','VYTAL0726','VYTAL0826','VYTAL0926','VYTAL01026'
]
ENROLL_FROM = '2026-06'
ENROLL_TO   = '2027-05'
APPT_FROM   = '2026-06-01'    # appointments counted from programme start
CAMP_FROM   = '2026-04'       # biomarkers from 2026 camp reports

# Confirmed available LOINC codes in BPC camp reports
LOINC_HBAIC   = '4548-4'
# BMI (39156-5) and BP (8480-6/8462-4) are vitals — NOT in lab parsed data
# Cholesterol/Dyslipidemia
LOINC_CHOL    = '2093-3'   # Total Cholesterol
LOINC_LDL     = '2089-1'   # LDL Cholesterol
LOINC_HDL     = '2085-9'   # HDL Cholesterol
LOINC_TRIG    = '2571-8'   # Triglycerides
# Liver
LOINC_ALT     = '1742-6'   # Alanine aminotransferase (ALT)
LOINC_AST     = '1920-8'   # Aspartate aminotransferase (AST)
LOINC_GGT     = '6768-6'   # Gamma glutamyl transferase
# Renal/Kidney
LOINC_CREAT   = '2160-0'   # Creatinine
# Thyroid
LOINC_TSH     = '3016-3'   # Thyroid stimulating hormone

# All LOINC codes to fetch in biomarker query
ALL_LOINCS = [
    LOINC_HBAIC,
    LOINC_CHOL, LOINC_LDL, LOINC_HDL, LOINC_TRIG,
    LOINC_ALT, LOINC_AST, LOINC_GGT,
    LOINC_CREAT,
    LOINC_TSH,
]

# Abnormal thresholds per condition
# Cholesterol: Total > 200 OR LDL > 130 OR Trig > 150 OR HDL < 40
CHOL_HIGH   = 200; LDL_HIGH = 130; TRIG_HIGH = 150; HDL_LOW = 40
# Liver: ALT > 56 OR AST > 40 OR GGT > 60
ALT_HIGH    = 56; AST_HIGH = 40; GGT_HIGH = 60
# Renal: Creatinine > 1.2
CREAT_HIGH  = 1.2
# Thyroid: TSH < 0.4 (hyper) OR TSH > 4.5 (hypo)
TSH_LOW     = 0.4; TSH_HIGH = 4.5

SMOKING_POSITIVE  = ['yes','occasional','former','moderate','once in a week',
                      '1-2 cigarettes','more than 8 cigarettes']
ALCOHOL_HIGH_RISK = ['4-7 drinks','8+ drinks','7+ drinks','8 or more','heavy',
                      'moderate drinker','5-14 drinks in a week','more than 14 drinks in a week']
STRESS_HIGH       = ['high','extremely high','very high']
SLEEP_LOW         = ['<6 hours','less than 6','fewer than 6','< 6','less than 6 hours']

BATCH_SIZE = 500

# ── STEP 1: Load 2026 enrolled users ─────────────────────────────────────────
def load_enrolled():
    print("[1] Loading 2026 enrolled VYTAL users from policy CSV...")
    if not os.path.exists(POLICY_CSV):
        print(f"  ERR: {POLICY_CSV} not found — run Script 04 first")
        return pd.DataFrame()
    df = pd.read_csv(POLICY_CSV)
    df26 = df[
        df['policy_year_month'].astype(str).between(ENROLL_FROM, ENROLL_TO) &
        df['mc_product_code'].isin(VYTAL_CODES)
    ].copy()
    # One row per user — keep highest-priority cohort if user appears in multiple
    df26['cohort_rank'] = df26['cohort'].map(COHORT_RANK).fillna(9)
    df26 = df26.sort_values('cohort_rank').drop_duplicates('mobile_number_hash', keep='first')
    df26 = df26.rename(columns={'managed_care_program': 'programme'})[
        ['mobile_number_hash','mc_product_code','policy_year_month','cohort','programme']
    ]
    print(f"  {len(df26):,} unique enrolled users")
    print(f"  Cohort: {df26['cohort'].value_counts().to_dict()}")
    return df26

# ── STEP 2: Fetch phr_ids from d_policy ──────────────────────────────────────
def fetch_phr_ids(hash_list):
    ids = sql_list(hash_list)
    df = q(f"""
        SELECT DISTINCT personmobilephone_hash AS mobile_number_hash,
               masterphrid AS phr_id
        FROM deltalake.dl_standard_customermart.d_policy
        WHERE personmobilephone_hash IN ({ids})
          AND masterphrid IS NOT NULL
    """, 'phr_ids')
    return df.drop_duplicates('mobile_number_hash') if not df.empty else df

# ── STEP 3: Fetch biomarkers (2026 camp BPC reports) ─────────────────────────
def fetch_biomarkers(hash_list):
    """
    Fetches all 5 clinical condition markers from camp lab reports:
    Diabetes (HbA1c), Cholesterol (Total/LDL/HDL/Trig), Liver (ALT/AST/GGT),
    Renal (Creatinine), Thyroid (TSH).
    Note: BMI and BP are vitals — not available in lab parsed data.
    """
    ids      = sql_list(hash_list)
    loincs   = sql_list(ALL_LOINCS)
    df = q(f"""
        SELECT DISTINCT
            d.mobile_number_hash,
            b.loinc_id,
            TRY_CAST(b.value AS DOUBLE) AS value,
            d.created_at
        FROM deltalake.dl_standard_customermart.f_claim a
        JOIN deltalake.dl_central_hrxlabs.customers d ON a.orderid = d.order_id
        JOIN deltalake.dl_central_health_vault.phr_lab_parsed_data_parsed_data_results_readings b
            ON a.orderid = b.transaction_id
        WHERE a.product_code IN ('BPC01','BPC02','BPC03')
          AND b.loinc_id IN ({loincs})
          AND d.mobile_number_hash IN ({ids})
          AND b.value IS NOT NULL
          AND SUBSTR(CAST(d.created_at AS VARCHAR),1,7) >= '{CAMP_FROM}'
    """, 'biomarkers')

    empty_cols = ['mobile_number_hash','hba1c','chol_total','ldl','hdl','triglycerides',
                  'alt','ast','ggt','creatinine','tsh']
    if df.empty:
        return pd.DataFrame(columns=empty_cols)

    df = df.sort_values('created_at', ascending=False).drop_duplicates(
        ['mobile_number_hash','loinc_id'], keep='first')
    wide = df.pivot_table(index='mobile_number_hash', columns='loinc_id',
                          values='value', aggfunc='first').reset_index()
    wide.columns.name = None
    wide = wide.rename(columns={
        LOINC_HBAIC: 'hba1c',
        LOINC_CHOL:  'chol_total',
        LOINC_LDL:   'ldl',
        LOINC_HDL:   'hdl',
        LOINC_TRIG:  'triglycerides',
        LOINC_ALT:   'alt',
        LOINC_AST:   'ast',
        LOINC_GGT:   'ggt',
        LOINC_CREAT: 'creatinine',
        LOINC_TSH:   'tsh',
    })
    for c in empty_cols[1:]:
        if c not in wide.columns:
            wide[c] = np.nan
    return wide[empty_cols]

# ── STEP 4: Fetch VYTAL appointments (2026 programme) ────────────────────────
def fetch_appointments(hash_list):
    # f_claim has no created_at column — VYTAL codes are 2026-only so no date filter needed
    ids    = sql_list(hash_list)
    vcodes = sql_list(VYTAL_CODES)
    df = q(f"""
        SELECT
            c.mobile_number_hash,
            fc.claim_id     AS appt_id,
            fc.benefit_name AS appt_type,
            fc.claim_status,
            'mc_claim'      AS appt_source
        FROM deltalake.dl_standard_customermart.f_claim fc
        JOIN deltalake.dl_central_hrxlabs.customers c ON fc.phr_id = c.phr_id
        WHERE fc.product_code IN ({vcodes})
          AND c.mobile_number_hash IN ({ids})
          AND fc.claim_status IN ('Authorized','Redeemed','Paid')
    """, 'appointments')
    if df.empty:
        return pd.DataFrame(columns=['mobile_number_hash','appt_booked',
                                      'appt_completed','appt_types_used'])
    summary = df.groupby('mobile_number_hash').agg(
        appt_booked    =('appt_id',     'count'),
        appt_completed =('claim_status', lambda x: (x=='Redeemed').sum()),
        appt_types_used=('appt_type',   'nunique'),
    ).reset_index()
    return summary

# ── STEP 5: Load & parse HRA wellness CSV ────────────────────────────────────
_HRA_CACHE = None

def load_hra():
    global _HRA_CACHE
    if _HRA_CACHE is None:
        if not os.path.exists(HRA_CSV):
            print(f"  WARNING: HRA CSV not found ({HRA_CSV})")
            print("           Run fetch_hra_wellness.py to populate it.")
            _HRA_CACHE = pd.DataFrame()
        else:
            _HRA_CACHE = pd.read_csv(HRA_CSV)
            print(f"  HRA CSV loaded: {len(_HRA_CACHE):,} rows, "
                  f"{_HRA_CACHE['phr_id'].nunique():,} unique phr_ids")
    return _HRA_CACHE

def parse_hra(df_wide, phr_ids):
    if df_wide is None or df_wide.empty:
        return pd.DataFrame(columns=['phr_id','smoking_status','alcohol_frequency',
                                      'stress_level','sleep_hours','bmi_category'])
    df = df_wide[df_wide['phr_id'].isin(phr_ids)].copy()
    if df.empty:
        return pd.DataFrame(columns=['phr_id','smoking_status','alcohol_frequency',
                                      'stress_level','sleep_hours','bmi_category'])

    def coalesce(row, *cols):
        for c in cols:
            v = str(row[c]).strip() if c in row.index and pd.notna(row[c]) else ''
            if v:
                return v
        return ''

    df['smoking_status']    = df.apply(lambda r: coalesce(r,
        'metadata_user_response_smoking_habit','metadata_user_response_smoke'), axis=1)
    df['alcohol_frequency'] = df.apply(lambda r: coalesce(r,
        'metadata_user_response_drinking_habit','metadata_user_response_alcohol',
        'metadata_user_response_drink'), axis=1)
    df['stress_level']      = df.apply(lambda r: coalesce(r,
        'metadata_user_response_stress','metadata_user_response_feeling_stress'), axis=1)
    df['sleep_hours']       = df.apply(lambda r: coalesce(r,
        'metadata_user_response_average_hours_of_sleep','metadata_user_response_sleep'), axis=1)
    df['bmi_category']      = df['metadata_user_response_bmi'].fillna('') \
        if 'metadata_user_response_bmi' in df.columns else ''
    # Include has_high_bp from HRA (Q1007) for Metabolic Syndrome assessment
    df['has_high_bp'] = df.apply(lambda r: coalesce(r,
        'metadata_user_response_high_bp', 'has_high_bp'), axis=1)

    return df.drop_duplicates('phr_id')[['phr_id','smoking_status','alcohol_frequency',
                                          'stress_level','sleep_hours','bmi_category','has_high_bp']]

# ── STEP 6: Scoring & assignment ─────────────────────────────────────────────
def assign_device(row):
    """
    CGM and Glucometer are glucose monitoring devices — ONLY for Diabetes programme users.
    Non-Diabetes users get Weighing Machine or BP Monitor based on BMI/BP or programme.

    Diabetes users:
      HbA1c > 8    → CGM  |  HbA1c 6.5–8 → Glucometer
      No/low HbA1c → CGM (VH) or Glucometer (H/M) via programme fallback

    Non-Diabetes users:
      BMI > 25 (from HRA) → Weighing Machine
      BP > 140/90 (from HRA) → BP Monitor
      Programme fallback:
        Dyslipidemia H/VH → BP Monitor  |  Dyslipidemia M → Weighing Machine
        Thyroid / Liver / Kidney (any)  → Weighing Machine
    """
    hba1c     = row.get('hba1c')
    bmi       = row.get('bmi')
    sbp       = row.get('sbp')
    dbp       = row.get('dbp')
    programme = str(row.get('programme', ''))
    cohort    = str(row.get('cohort', ''))

    is_diabetes = 'Diabetes' in programme

    if is_diabetes:
        # HbA1c biomarker takes priority for Diabetes users
        if pd.notna(hba1c) and hba1c > 8:
            return 'CGM'
        if pd.notna(hba1c) and hba1c >= 6.5:
            return 'Glucometer'
        # Programme fallback for Diabetes (HbA1c missing or < 6.5)
        return 'CGM' if cohort == 'Very High' else 'Glucometer'

    # Non-Diabetes: BMI/BP from HRA (not available from camp labs, only if HRA filled)
    if pd.notna(bmi) and bmi > 25:
        return 'Weighing Machine'
    if (pd.notna(sbp) and sbp > 140) or (pd.notna(dbp) and dbp > 90):
        return 'BP Monitor'

    # Programme-based fallback for non-Diabetes
    if any(p in programme for p in ['Dyslipidemia', 'Cholesterol']):
        return 'BP Monitor' if cohort in ['High', 'Very High'] else 'Weighing Machine'
    if any(p in programme for p in ['Thyroid', 'Liver', 'Kidney']):
        return 'Weighing Machine'

    return 'None'

def count_morbidities(row):
    """
    Count confirmed risk conditions per orchestration doc:
    Diabetes, Cholesterol, Renal, Liver, Thyroid — each = 1 morbidity.
    Uses lab biomarkers (abnormal thresholds) as primary source.
    Programme enrollment used as fallback when specific labs are missing.
    BMI/BP not available from camp labs — skipped here; HRA BMI used if available.
    """
    conditions = set()

    # 1. Diabetes: HbA1c >= 5.7
    if pd.notna(row.get('hba1c')) and row['hba1c'] >= 5.7:
        conditions.add('Diabetes')

    # 2. Cholesterol/Dyslipidemia: Total > 200 OR LDL > 130 OR Trig > 150 OR HDL < 40
    chol_abnormal = (
        (pd.notna(row.get('chol_total'))   and row['chol_total']   > CHOL_HIGH) or
        (pd.notna(row.get('ldl'))          and row['ldl']          > LDL_HIGH)  or
        (pd.notna(row.get('triglycerides'))and row['triglycerides']> TRIG_HIGH) or
        (pd.notna(row.get('hdl'))          and row['hdl']          < HDL_LOW)
    )
    if chol_abnormal:
        conditions.add('Cholesterol')
    elif 'Dyslipidemia' in str(row.get('programme', '')) or \
         'Cholesterol' in str(row.get('programme', '')):
        conditions.add('Cholesterol')   # programme-based fallback

    # 3. Liver: ALT > 56 OR AST > 40 OR GGT > 60
    liver_abnormal = (
        (pd.notna(row.get('alt')) and row['alt'] > ALT_HIGH) or
        (pd.notna(row.get('ast')) and row['ast'] > AST_HIGH) or
        (pd.notna(row.get('ggt')) and row['ggt'] > GGT_HIGH)
    )
    if liver_abnormal:
        conditions.add('Liver')
    elif 'Liver' in str(row.get('programme', '')):
        conditions.add('Liver')

    # 4. Renal/Kidney: Creatinine > 1.2
    if pd.notna(row.get('creatinine')) and row['creatinine'] > CREAT_HIGH:
        conditions.add('Renal')
    elif 'Kidney' in str(row.get('programme', '')):
        conditions.add('Renal')

    # 5. Thyroid: TSH < 0.4 (hyper) or TSH > 4.5 (hypo)
    if pd.notna(row.get('tsh')) and (row['tsh'] < TSH_LOW or row['tsh'] > TSH_HIGH):
        conditions.add('Thyroid')
    elif 'Thyroid' in str(row.get('programme', '')):
        conditions.add('Thyroid')

    # 6. Overweight/Obese from HRA (BMI not in camp labs)
    bmi_cat = str(row.get('bmi_category', '')).lower()
    if bmi_cat in ['overweight', 'obese']:
        conditions.add('Overweight')

    return len(conditions)

def assess_lifestyle(row):
    asmts = []
    overweight   = str(row.get('bmi_category','')).lower() in ['overweight','obese','yes']
    # Also check lab BMI if HRA not available
    if not overweight and pd.notna(row.get('bmi')):
        overweight = row['bmi'] > 25
    abnormal_hba = pd.notna(row.get('hba1c')) and row['hba1c'] >= 5.7
    # High BP: from HRA Q1007 (Yes/No) or lab SBP/DBP
    # NOTE: 2026 HRA questionnaire does NOT include Q1007 — BP data unavailable from HRA
    bp_from_hra = str(row.get('has_high_bp','')).strip().lower() == 'yes'
    bp_from_lab = (pd.notna(row.get('sbp')) and row['sbp'] > 140) or \
                  (pd.notna(row.get('dbp')) and row['dbp'] > 90)
    high_bp = bp_from_hra or bp_from_lab
    bp_available = bp_from_hra or bp_from_lab

    alc_val      = str(row.get('alcohol_frequency') or '').lower()
    alcohol_risk = any(a.lower() in alc_val for a in ALCOHOL_HIGH_RISK)
    stress_val   = str(row.get('stress_level') or '').lower()
    stress_high  = any(s.lower() in stress_val for s in STRESS_HIGH)

    # Metabolic Syndrome criteria:
    # - If BP data available: require all 3 (BMI overweight + HbA1c ≥5.7 + High BP)
    # - If BP not available (2026 HRA has no Q1007): require 2 of 2 (BMI + HbA1c)
    if bp_available:
        metabolic = overweight and abnormal_hba and high_bp
    else:
        metabolic = overweight and abnormal_hba  # 2026: BP not collected in questionnaire
    if metabolic:
        asmts.append('Metabolic Syndrome')
    # Alcohol Impact: HRA high alcohol intake
    # (LFT data not yet available; HRA alcohol is primary criterion)
    if alcohol_risk:
        asmts.append('Alcohol Impact')
    # Stress Impact: HRA high stress + High BP
    if stress_high and high_bp:
        asmts.append('Stress Impact')
    return '|'.join(asmts) if asmts else 'None'

def calc_score(row):
    """
    Scoring per orchestration doc (0–100 total):
      Clinical Risk  (30%): morbidity count → raw 0–100, ×0.30 = 0–30 pts
      Engagement     (25%): consultations from claims (0–25 raw), ×0.25/25×100 = 0–25 pts
                            App opens not available (0), consultations as recommended = 15 pts raw
      Adherence      (25%): claim service types used as proxy for logs (0–25 raw), ×0.25 = 0–25 pts
      Lifestyle      (20%): HRA risk factors (0–20 raw), ×0.20/20×100 = 0–20 pts
    """
    # 1. Clinical Risk — morbidity count → normalize to 0-100
    morbidities = count_morbidities(row)
    if   morbidities >= 4: clinical_raw = 100       # more than 3 → 30 pts contribution
    elif morbidities == 3: clinical_raw = 83.3       # triple       → 25 pts
    elif morbidities == 2: clinical_raw = 66.7       # dual         → 20 pts
    elif morbidities == 1: clinical_raw = 50.0       # single       → 15 pts
    else:
        # fallback: use cohort when biomarkers not available
        cohort_map = {'Very High': 83.3, 'High': 66.7, 'Moderate': 50.0}
        clinical_raw = cohort_map.get(str(row.get('cohort','')), 50.0)

    # 2. Engagement — appointment claims (proxy for consultations completed)
    # Raw: app_opens (0–10, not available=0) + consultations (0–15)
    # "As recommended" = ≥1 completed claim → 15 pts raw
    appt_comp  = float(row.get('appt_completed', 0) or 0)
    appt_booked = float(row.get('appt_booked', 0) or 0)
    consult_raw = 15 if appt_comp >= 1 else (7 if appt_booked >= 1 else 0)
    engagement_raw = consult_raw   # app opens not available (0)
    engagement_normalized = (engagement_raw / 25) * 100   # normalize to 0-100

    # 3. Adherence Intent — service types used as log proxy
    # Nutritionist=diet(9), Health Monitoring=activity(8), Teleconsult=sleep(4), other=stress(4)
    appt_types = float(row.get('appt_types_used', 0) or 0)
    if   appt_types >= 4: adherence_raw = 25
    elif appt_types == 3: adherence_raw = 17   # diet+activity+sleep = 9+8=17
    elif appt_types == 2: adherence_raw = 9    # diet+activity = 9
    elif appt_types == 1: adherence_raw = 4    # any single type
    else:                 adherence_raw = 0
    adherence_normalized = (adherence_raw / 25) * 100   # normalize to 0-100

    # 4. Lifestyle Risk — HRA factors (already 0–20 scale)
    lifestyle_raw = 0
    if str(row.get('smoking_status','')).lower() in SMOKING_POSITIVE:
        lifestyle_raw += 10
    if any(a.lower() in str(row.get('alcohol_frequency','')).lower() for a in ALCOHOL_HIGH_RISK):
        lifestyle_raw += 5
    if any(s.lower() in str(row.get('stress_level','')).lower() for s in STRESS_HIGH):
        lifestyle_raw += 3
    if any(s.lower() in str(row.get('sleep_hours','')).lower() for s in SLEEP_LOW):
        lifestyle_raw += 2
    lifestyle_raw = min(lifestyle_raw, 20)
    lifestyle_normalized = (lifestyle_raw / 20) * 100   # normalize to 0-100

    total = (clinical_raw * 0.30 +
             engagement_normalized * 0.25 +
             adherence_normalized * 0.25 +
             lifestyle_normalized * 0.20)
    return round(min(total, 100), 1)

def engagement_tier(score):
    if score > 75:  return 'High'
    if score >= 50: return 'Moderate'
    if score >= 30: return 'Low'
    return 'Very Low'

# ── STEP 7: Allocate slots (top 100 per device/assessment type) ───────────────
def allocate_slots(df):
    """
    Priority: Very High cohort first, then High, then Moderate.
    Within same cohort: engagement_score DESC.
    100 slots per device type, 200/100/100 for lifestyle assessments.
    """
    df = df.copy()
    df['cohort_rank'] = df['cohort'].map(COHORT_RANK).fillna(9)
    df['device_allocated']     = False
    df['device_rank']          = np.nan
    df['lifestyle_allocated']  = False
    df['lifestyle_rank']       = np.nan

    # Device allocation
    for device, slots in DEVICE_SLOTS.items():
        eligible = df[df['primary_device'] == device].copy()
        if eligible.empty:
            continue
        ranked = eligible.sort_values(
            ['cohort_rank','engagement_score'], ascending=[True, False]
        ).reset_index()
        ranked['_rank'] = ranked.index + 1
        top = ranked[ranked['_rank'] <= slots]['index'].tolist()
        df.loc[top, 'device_allocated'] = True
        df.loc[top, 'device_rank']      = ranked.set_index('index').loc[top, '_rank'].values

    # Lifestyle allocation (first assessment type per user, by slot count)
    for ltype, slots in LIFESTYLE_SLOTS.items():
        eligible = df[df['lifestyle_assessment'].str.contains(ltype, na=False)
                      & ~df['lifestyle_allocated']].copy()
        if eligible.empty:
            continue
        ranked = eligible.sort_values(
            ['cohort_rank','engagement_score'], ascending=[True, False]
        ).reset_index()
        ranked['_rank'] = ranked.index + 1
        top = ranked[ranked['_rank'] <= slots]['index'].tolist()
        df.loc[top, 'lifestyle_allocated'] = True
        df.loc[top, 'lifestyle_rank']      = ranked.set_index('index').loc[top, '_rank'].values

    return df

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*60)
    print("  MANAGED CARE 3.0 — Script 3b: Device Eligibility 2026")
    print("="*60)

    # Step 1: Load enrolled users
    enrolled = load_enrolled()
    if enrolled.empty:
        print("  No enrolled users found — aborting.")
        return

    # Step 2: Load HRA once (reused across batches)
    print("\n[2] Loading HRA wellness CSV...")
    hra_all = load_hra()
    hra_available = not hra_all.empty

    # Step 3: Process in batches
    n = len(enrolled)
    n_batches = math.ceil(n / BATCH_SIZE)
    print(f"\n[3] Processing {n:,} users in {n_batches} batch(es) of {BATCH_SIZE}...")

    results = []
    for i in range(n_batches):
        batch = enrolled.iloc[i*BATCH_SIZE:(i+1)*BATCH_SIZE].copy()
        hashes = batch['mobile_number_hash'].dropna().tolist()
        print(f"\n  Batch {i+1}/{n_batches} — {len(hashes)} users")

        # phr_ids
        df_phr = fetch_phr_ids(hashes)
        if not df_phr.empty:
            batch = batch.merge(df_phr, on='mobile_number_hash', how='left')
        else:
            batch['phr_id'] = np.nan

        # Biomarkers
        df_bio = fetch_biomarkers(hashes)
        batch = batch.merge(df_bio, on='mobile_number_hash', how='left')

        # HRA
        if hra_available and 'phr_id' in batch.columns:
            phr_ids = batch['phr_id'].dropna().unique().tolist()
            df_hra  = parse_hra(hra_all, phr_ids)
            batch   = batch.merge(df_hra, on='phr_id', how='left')
            batch['hra_available'] = batch['phr_id'].isin(df_hra['phr_id'].tolist())
        else:
            for c in ['smoking_status','alcohol_frequency','stress_level',
                      'sleep_hours','bmi_category']:
                batch[c] = np.nan
            batch['hra_available'] = False

        # Appointments
        df_appt = fetch_appointments(hashes)
        batch   = batch.merge(df_appt, on='mobile_number_hash', how='left')

        # Fill numeric nulls
        for c in ['hba1c','chol_total','ldl','hdl','triglycerides',
                  'alt','ast','ggt','creatinine','tsh',
                  'appt_booked','appt_completed','appt_types_used']:
            if c in batch.columns:
                batch[c] = pd.to_numeric(batch[c], errors='coerce')

        # Device & lifestyle — also tag whether Tier 1 (biomarker) or Tier 2 (programme) drove assignment
        def assign_device_tier(row):
            hba1c = row.get('hba1c')
            programme = str(row.get('programme', ''))
            # Biomarker tier only when Diabetes user AND HbA1c drove the assignment
            if 'Diabetes' in programme and pd.notna(hba1c) and hba1c >= 6.5:
                return 'Biomarker'
            if row.get('primary_device', 'None') != 'None':
                return 'Programme'
            return 'None'

        batch['primary_device']       = batch.apply(assign_device,     axis=1)
        batch['device_assignment_tier']= batch.apply(assign_device_tier, axis=1)
        batch['lifestyle_assessment'] = batch.apply(assess_lifestyle,   axis=1)
        batch['engagement_score']     = batch.apply(calc_score,         axis=1)
        batch['engagement_tier']      = batch['engagement_score'].apply(engagement_tier)

        results.append(batch)

    # Step 4: Combine + allocate
    print("\n[4] Allocating device and lifestyle slots...")
    df_all = pd.concat(results, ignore_index=True)

    # Remove duplicate mobile hashes (keep highest score)
    df_all = df_all.sort_values('engagement_score', ascending=False)\
                   .drop_duplicates('mobile_number_hash', keep='first')\
                   .reset_index(drop=True)

    df_all = allocate_slots(df_all)

    # Step 5: Save
    final_cols = [
        'mobile_number_hash','phr_id','programme','cohort',
        'mc_product_code','policy_year_month',
        'hba1c','chol_total','ldl','hdl','triglycerides',
        'alt','ast','ggt','creatinine','tsh',
        'hra_available','smoking_status','alcohol_frequency','stress_level','sleep_hours','bmi_category','has_high_bp',
        'appt_booked','appt_completed','appt_types_used',
        'clinical_risk_score','engagement_score','engagement_tier',
        'primary_device','device_assignment_tier','lifestyle_assessment',
        'device_allocated','device_rank',
        'lifestyle_allocated','lifestyle_rank',
    ]
    df_out = df_all[[c for c in final_cols if c in df_all.columns]].copy()
    df_out['run_date'] = pd.Timestamp.today().strftime('%Y-%m-%d')
    df_out.to_csv(OUTPUT_PATH, index=False)

    # Summary
    total = len(df_out)
    hra_n = df_out['hra_available'].sum() if 'hra_available' in df_out.columns else 0
    bio_n = df_out['hba1c'].notna().sum()
    dev_alloc = df_out[df_out['device_allocated'] == True]
    ls_alloc  = df_out[df_out['lifestyle_allocated'] == True]

    print(f"\n{'='*60}")
    print(f"  Total enrolled          : {total:,}")
    print(f"  With HRA data           : {int(hra_n):,} ({int(hra_n/total*100) if total else 0}%)")
    print(f"  With biomarker data     : {bio_n:,} ({int(bio_n/total*100) if total else 0}%)")
    print(f"\n  Device eligibility (all eligible):")
    print(df_out['primary_device'].value_counts().to_string())
    print(f"\n  Device ALLOCATED (top 100 per type):")
    print(dev_alloc['primary_device'].value_counts().to_string())
    print(f"\n  Lifestyle ALLOCATED:")
    for lt in ['Metabolic Syndrome','Stress Impact','Alcohol Impact']:
        n_ls = ls_alloc['lifestyle_assessment'].str.contains(lt, na=False).sum()
        print(f"    {lt}: {n_ls}")
    print(f"\n  Saved -> {OUTPUT_PATH}")
    print(f"{'='*60}")

    get_engine().dispose()

if __name__ == '__main__':
    main()
