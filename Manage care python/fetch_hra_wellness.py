"""
============================================================
MANAGED CARE 3.0 — HRA Fetch
============================================================
Source : dl_central_phrservice.assessment_reports
Auth   : OAuth2 (browser prompt on first run)
Filter : enrolled VYTAL phr_ids + journey_key='hra_healthcamp'
         + status='COMPLETED' + created_at >= 2026-04

Question ID map (confirmed from data):
  1001 = gender          1002 = DOB
  1003 = weight (kg)     1004 = height (cm)
  1005 = health problems 1006 = family history
  1007 = high BP (Yes/No)
  1008 = prolonged sitting
  1009 = exercise
  1010 = smoking frequency
  1011 = alcohol intake
  1012 = appetite        1013 = tiredness
  1014 = sleep hours     1015 = water (skip)
  1016 = diet

user_responses format (non-standard, parsed via regex):
  [{[answer_label], position, question_id, null, question_text, [code], type}, ...]

Output: managed_care_hra_wellness.csv — one row per user, lifestyle columns
        compatible with 03b_device_eligibility_2026.py

RUN: python fetch_hra_wellness.py  (browser OAuth prompt on first run)
============================================================
"""

import sys, os, re, urllib
import pandas as pd
import trino
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding='utf-8')

from config import TRINO_HOST as HOST, TRINO_USER, TRINO_PASSWORD
PORT = 443

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = next((os.path.join(SCRIPT_DIR, d) for d in ["Data","data","DATA"]
                   if os.path.isdir(os.path.join(SCRIPT_DIR, d))),
                  os.path.join(SCRIPT_DIR, "Data"))
os.makedirs(DATA_DIR, exist_ok=True)

OUT_HRA   = os.path.join(DATA_DIR, "managed_care_hra_wellness.csv")
OUT_PHRS  = os.path.join(DATA_DIR, "managed_care_camp_phrs.csv")
OUT_STATS = os.path.join(DATA_DIR, "managed_care_hra_stats.csv")

VYTAL_CODES = [
    'VYTAL0126','VYTAL0226','VYTAL0326','VYTAL0426','VYTAL0526',
    'VYTAL0626','VYTAL0726','VYTAL0826','VYTAL0926','VYTAL01026'
]

QID_MAP = {
    '1001': 'gender',
    '1002': 'dob',
    '1003': 'weight_kg',
    '1004': 'height_cm',
    '1005': 'health_problems',
    '1006': 'family_history',
    '1007': 'has_high_bp',           # Not in 2026 questionnaire
    '1008': 'sitting_hours',
    '1009': 'exercise_mins',
    '1010': 'smoking_status',
    '1011': 'alcohol_frequency',
    '1012': 'appetite',
    '1013': 'tiredness',
    '1014': 'sleep_hours',
    '1015': None,
    '1016': 'diet',
    # 2026 questionnaire uses custom IDs
    'activity_level':          'activity_level',
    'bfhl_1006_single_select': 'health_problems_custom',
    'bfl_1212':                'family_history_custom',
}


# ── PARSE user_responses STRING ───────────────────────────────────────────────
def parse_user_responses(resp_str):
    """
    Parse non-standard user_responses format into {question_id: answer_label}.
    Handles both numeric IDs (1001, 1010...) and custom IDs (activity_level, bfhl_1006_single_select).
    Format: [{[answer_label], position, question_id, null, question_text, [code], type}, ...]
    """
    results = {}
    if not resp_str or str(resp_str).strip() in ('[]', '', 'None'):
        return results

    # Match both numeric (1xxx) and word-character (activity_level) question IDs
    pattern = r'\{\[([^\]]*)\],\s*\d+,\s*([\w_]+)'
    for match in re.finditer(pattern, str(resp_str)):
        answer_label = match.group(1).strip()
        qid = match.group(2).strip()
        if qid not in results:
            results[qid] = answer_label
    return results


# ── CONNECTIONS ───────────────────────────────────────────────────────────────
def get_oauth_conn():
    return trino.dbapi.connect(
        host=HOST, port=PORT,
        http_scheme='https',
        auth=trino.auth.OAuth2Authentication(),
        verify=True,
    )

def get_vasu_engine():
    pw = urllib.parse.quote_plus(TRINO_PASSWORD)
    return create_engine(
        f'trino://{TRINO_USER}:{pw}@{HOST}:{PORT}/system?http_scheme=https'
    )


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*62)
    print("  HRA Fetch — assessment_reports (OAuth2)")
    print(f"  Filter: enrolled VYTAL users, journey_key=hra_healthcamp, COMPLETED")
    print("="*62)

    # Step 1: Enrolled VYTAL phr_ids via vasu credentials
    print("\n[Step 1] Fetching enrolled VYTAL phr_ids (vasu credentials)...")
    codes_sql = ', '.join(f"'{c}'" for c in VYTAL_CODES)
    eng = get_vasu_engine()
    try:
        with eng.connect() as c:
            r = c.execute(text(f"""
                SELECT DISTINCT masterphrid AS phr_id,
                       personmobilephone_hash AS mobile_number_hash
                FROM deltalake.dl_standard_customermart.d_policy
                WHERE vlocity_ins_fsc__productcode__c IN ({codes_sql})
                  AND personmobilephone_hash IS NOT NULL
                  AND masterphrid IS NOT NULL
                  AND (is_test_policy__c = FALSE OR is_test_policy__c IS NULL)
                  AND SUBSTR(CAST(createddate AS VARCHAR),1,7) >= '2026-06'
                  AND SUBSTR(CAST(createddate AS VARCHAR),1,7) <= '2027-05'
            """))
            df_phr = pd.DataFrame(r.fetchall(), columns=r.keys())
    except Exception as e:
        print(f"  ERR: {str(e)[:250]}")
        return
    finally:
        eng.dispose()

    if df_phr.empty:
        print("  No enrolled users — aborting.")
        return

    enrolled_phrs = df_phr['phr_id'].dropna().unique().tolist()
    df_phr.to_csv(OUT_PHRS, index=False)
    print(f"  {len(enrolled_phrs):,} enrolled phr_ids | Saved: {OUT_PHRS}")

    # Step 2: Fetch assessment_reports via OAuth in batches
    print(f"\n[Step 2] Fetching HRA from assessment_reports (OAuth2)...")
    print("  A browser window may open for authentication.")

    conn = get_oauth_conn()
    cur  = conn.cursor()

    # Get total HRA count (all users, not just enrolled) for dashboard display
    print("  Fetching total hra_healthcamp record counts...")
    try:
        cur.execute("""
            SELECT status, COUNT(DISTINCT phr_id) AS unique_users
            FROM deltalake.dl_central_phrservice.assessment_reports
            WHERE journey_key = 'hra_healthcamp'
              AND SUBSTR(CAST(created_at AS VARCHAR), 1, 7) >= '2026-04'
            GROUP BY status
        """)
        total_counts = {row[0]: row[1] for row in cur.fetchall()}
        total_completed_all  = total_counts.get('COMPLETED', 0)
        total_attempted_all  = sum(total_counts.values())
        print(f"  Total hra_healthcamp: {total_attempted_all} unique users "
              f"({total_completed_all} COMPLETED, {total_attempted_all - total_completed_all} STARTED)")
    except Exception as e:
        print(f"  WARNING: Could not fetch total counts: {str(e)[:100]}")
        total_completed_all = 0
        total_attempted_all = 0

    BATCH   = 500
    batches = [enrolled_phrs[i:i+BATCH] for i in range(0, len(enrolled_phrs), BATCH)]
    print(f"  {len(batches)} batch(es) x {BATCH}")

    raw_rows = []
    for i, batch in enumerate(batches):
        ids = ', '.join(f"'{p}'" for p in batch)
        try:
            cur.execute(f"""
                SELECT phr_id, status, score, weight, height,
                       CAST(user_responses AS VARCHAR) AS user_responses_str,
                       created_at
                FROM deltalake.dl_central_phrservice.assessment_reports
                WHERE journey_key = 'hra_healthcamp'
                  AND status IN ('COMPLETED', 'STARTED')
                  AND phr_id IN ({ids})
                  AND SUBSTR(CAST(created_at AS VARCHAR), 1, 7) >= '2026-04'
            """)
            rows = cur.fetchall()
            raw_rows.extend(rows)
            print(f"  Batch {i+1}/{len(batches)}: {len(rows)} rows")
        except Exception as e:
            print(f"  ERR batch {i+1}: {str(e)[:200]}")

    conn.close()

    if not raw_rows:
        print("\n  No completed HRA found for enrolled users from April 2026.")
        _save_empty(df_phr)
        return

    df_raw = pd.DataFrame(raw_rows, columns=['phr_id','status','score','weight','height','user_responses_str','created_at'])
    print(f"\n  Total raw records: {len(df_raw):,} | Unique users: {df_raw['phr_id'].nunique():,}")
    print(f"  Status breakdown: {df_raw['status'].value_counts().to_dict()}")

    # Step 3: Parse user_responses per record
    print("\n[Step 3] Parsing user_responses...")

    # Relevant lifestyle question IDs — keep record only if at least one is answered
    RELEVANT_QIDS = {'1007','1008','1009','1010','1011','1012','1013','1014'}

    records = []
    skipped_no_answers = 0
    for _, row in df_raw.iterrows():
        parsed = parse_user_responses(row['user_responses_str'])
        # Only keep if at least one relevant question was answered
        if not any(qid in parsed for qid in RELEVANT_QIDS):
            skipped_no_answers += 1
            continue
        rec = {'phr_id': row['phr_id'], 'hra_status': row['status'],
               'created_at': row['created_at'],
               'score': row['score'], 'weight_raw': row['weight'], 'height_raw': row['height']}
        for qid, field in QID_MAP.items():
            if field:
                rec[field] = parsed.get(qid, '')
        records.append(rec)

    print(f"  Records with relevant answers: {len(records):,} | Skipped (no answers): {skipped_no_answers:,}")

    if not records:
        print("  No usable HRA records found.")
        _save_empty(df_phr)
        return

    df_wide = pd.DataFrame(records)

    # Per user: prefer COMPLETED over STARTED, then latest date
    df_wide['_status_rank'] = df_wide['hra_status'].map({'COMPLETED': 0, 'STARTED': 1}).fillna(2)
    df_wide = df_wide.sort_values(['_status_rank','created_at'], ascending=[True, False])
    df_wide = df_wide.drop_duplicates('phr_id', keep='first').drop(columns=['_status_rank'])

    # Numeric weight / height — prefer direct columns over parsed
    df_wide['weight_kg'] = pd.to_numeric(df_wide['weight_raw'], errors='coerce').fillna(
        pd.to_numeric(df_wide.get('weight_kg',''), errors='coerce'))
    df_wide['height_cm'] = pd.to_numeric(df_wide['height_raw'], errors='coerce').fillna(
        pd.to_numeric(df_wide.get('height_cm',''), errors='coerce'))

    def bmi_cat(row):
        w, h = row['weight_kg'], row['height_cm']
        try:
            if pd.notna(w) and pd.notna(h) and float(h) > 0:
                bmi = float(w) / ((float(h)/100)**2)
                return 'Obese' if bmi >= 30 else ('Overweight' if bmi >= 25 else 'Normal')
        except: pass
        return ''
    df_wide['bmi_category'] = df_wide.apply(bmi_cat, axis=1)
    df_wide['stress_level'] = ''

    # Merge mobile_number_hash
    df_wide = df_wide.merge(df_phr[['phr_id','mobile_number_hash']], on='phr_id', how='left')

    # Legacy column names for 03b compatibility
    df_wide['metadata_user_response_smoking_habit']          = df_wide.get('smoking_status','')
    df_wide['metadata_user_response_drinking_habit']         = df_wide.get('alcohol_frequency','')
    df_wide['metadata_user_response_stress']                 = ''
    df_wide['metadata_user_response_average_hours_of_sleep'] = df_wide.get('sleep_hours','')
    df_wide['metadata_user_response_bmi']                    = df_wide['bmi_category']
    df_wide['metadata_journey_key']                          = 'hra_healthcamp'

    # Add metadata column for high BP from HRA (Q1007)
    df_wide['metadata_user_response_high_bp'] = df_wide.get('has_high_bp', '')

    df_wide.drop(columns=['weight_raw','height_raw'], inplace=True, errors='ignore')
    df_wide.to_csv(OUT_HRA, index=False)

    # Save HRA stats for dashboard display
    enrolled_with_hra = len(df_wide)
    pd.DataFrame([{
        'metric': 'enrolled_with_hra',      'value': enrolled_with_hra
    }, {
        'metric': 'total_completed_all',    'value': total_completed_all
    }, {
        'metric': 'total_attempted_all',    'value': total_attempted_all
    }]).to_csv(OUT_STATS, index=False)
    print(f"  Saved HRA stats -> {OUT_STATS}")

    # Summary
    total    = len(df_wide)
    coverage = total / len(enrolled_phrs) * 100
    print(f"\n{'='*62}")
    print(f"  Enrolled      : {len(enrolled_phrs):,}")
    print(f"  With HRA      : {total:,} ({coverage:.1f}%)")
    print(f"  Weight data   : {df_wide['weight_kg'].notna().sum():,}")
    print(f"  Height data   : {df_wide['height_cm'].notna().sum():,}")
    print(f"  BMI derived   : {(df_wide['bmi_category'] != '').sum():,}")
    print()
    for col, label in [
        ('smoking_status','Smoking'), ('alcohol_frequency','Alcohol'),
        ('sleep_hours','Sleep'), ('has_high_bp','High BP'), ('bmi_category','BMI'),
    ]:
        vals = df_wide[col].replace('', None).dropna()
        if len(vals) > 0:
            print(f"  {label} ({len(vals)} users):")
            print(vals.value_counts().head(4).to_string())
            print()
    print(f"  Saved -> {OUT_HRA}")
    print(f"  Run 03b_device_eligibility_2026.py to refresh device scores.")
    print(f"{'='*62}")


def _save_empty(df_phr):
    pd.DataFrame(columns=[
        'phr_id','mobile_number_hash','bmi_category','smoking_status',
        'alcohol_frequency','stress_level','sleep_hours','has_high_bp',
        'weight_kg','height_cm','metadata_user_response_smoking_habit',
        'metadata_user_response_drinking_habit','metadata_user_response_stress',
        'metadata_user_response_average_hours_of_sleep',
        'metadata_user_response_bmi','metadata_journey_key'
    ]).to_csv(OUT_HRA, index=False)
    print(f"  Saved empty: {OUT_HRA}")


if __name__ == "__main__":
    main()
