"""
fetch_voicebot_appt_source.py
Daily pipeline step: classify VYTAL appointments by booking source.
  Voice Bot = user answered call + said interested + claim created
  Organic   = everything else
  Agent     = user booked without voice bot
Outputs: Data/managed_care_appt_source.csv
         Data/managed_care_voicebot_funnel.json
"""
import sys, os, urllib, json
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import trino as trino_lib
from sqlalchemy import create_engine, text

from config import TRINO_HOST as HOST, TRINO_USER, TRINO_PASSWORD
from db_layer import read_table, save_dataframe

PORT = 443
pw   = urllib.parse.quote_plus(TRINO_PASSWORD)
url  = f"trino://{TRINO_USER}:{pw}@{HOST}:{PORT}/system?http_scheme=https"

VYTAL_CODES = ['VYTAL0126','VYTAL0226','VYTAL0326','VYTAL0426','VYTAL0526',
               'VYTAL0626','VYTAL0726','VYTAL0826','VYTAL0926','VYTAL01026']
cs = ", ".join(f"'{c}'" for c in VYTAL_CODES)

MCARE_CAMPAIGN_IDS = "234, 236, 240, 270"

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR     = os.path.join(SCRIPT_DIR, "Data")
OUT_FILE     = os.path.join(DATA_DIR, "managed_care_appt_source.csv")
FUNNEL_FILE  = os.path.join(DATA_DIR, "managed_care_voicebot_funnel.json")

# ── Step 0: Load ALL VYTAL mobile hashes from Neon (not stale CSV) ─────────
print("[0] Loading ALL VYTAL mobile hashes from Neon...")
policy = read_table("policy_data")
df_policy_raw = policy[
    policy['mc_product_code'].str.contains('VYTAL', regex=True, na=False)
][['phr_id','mobile_number_hash']].dropna().drop_duplicates('phr_id')
mc_hashes = set(df_policy_raw['mobile_number_hash'].dropna().unique())
print(f"  ALL VYTAL MC users with mobile hash: {len(mc_hashes):,}")

# ── Step 1: OAuth — get Mcare voicebot sessions (filtered to MC users) ────────
print("[1] Fetching Mcare voicebot sessions (OAuth2)...")
conn = trino_lib.dbapi.connect(
    host=HOST, port=PORT,
    http_scheme='https', auth=trino_lib.auth.OAuth2Authentication(), verify=True
)
cur = conn.cursor()

# Total dialled = all unique MC number_hashes in campaign runner (any call status)
cur.execute(f"""
    SELECT DISTINCT d.number_hash
    FROM deltalake.dl_central_ai_voicebot.dls_data d
    JOIN deltalake.dl_central_ai_voicebot.cs_campaign_runners cr
      ON cr.id = d.campaign_runner_id
    WHERE cr.campaign_id IN ({MCARE_CAMPAIGN_IDS})
      AND d.number_hash IS NOT NULL
""")
all_dialled_hashes = {r[0] for r in cur.fetchall()}
mc_dialled_hashes  = all_dialled_hashes & mc_hashes
total_dialled      = len(mc_dialled_hashes)
print(f"  Total dialled (all campaigns): {len(all_dialled_hashes):,}")
print(f"  Dialled who are MC/VYTAL users: {total_dialled:,}")

# Completed live sessions — answered calls
cur.execute(f"""
    SELECT d.number_hash, s.meta
    FROM deltalake.dl_central_ai_voicebot.dls_data d
    JOIN deltalake.dl_central_ai_voicebot.cs_campaign_runners cr
      ON cr.id = d.campaign_runner_id
    JOIN deltalake.dl_central_ai_voicebot.sms_session s
      ON s.data_id = d.id
    WHERE cr.campaign_id IN ({MCARE_CAMPAIGN_IDS})
      AND s.type = 'live'
      AND s.status = 'completed'
      AND d.number_hash IS NOT NULL
""")
rows = cur.fetchall()
print(f"  Completed live sessions (all): {len(rows)}")

# Parse intersted flag — keep best outcome per user, filter to MC users only
user_outcome = {}
for number_hash, meta in rows:
    if number_hash not in mc_hashes:
        continue  # skip non-MC users
    try:
        d    = json.loads(meta) if meta else {}
        flag = d.get('data', {}).get('intersted', None)
        cmb  = d.get('data', {}).get('call_me_back', False)
    except Exception:
        flag, cmb = None, False
    prev = user_outcome.get(number_hash, {})
    if flag is True or prev.get('intersted') is True:
        user_outcome[number_hash] = {'intersted': True,  'call_me_back': cmb or prev.get('call_me_back', False)}
    elif flag is False or prev.get('intersted') is False:
        user_outcome[number_hash] = {'intersted': False, 'call_me_back': cmb or prev.get('call_me_back', False)}
    else:
        if number_hash not in user_outcome:
            user_outcome[number_hash] = {'intersted': None, 'call_me_back': cmb}

answered          = len(user_outcome)
interested_hashes = {h for h, v in user_outcome.items() if v['intersted'] is True}
callback_cnt      = sum(1 for v in user_outcome.values() if v.get('call_me_back'))
no_answer         = total_dialled - answered

print(f"  MC users answered:   {answered}")
print(f"  intersted=True:      {len(interested_hashes)}")
print(f"  Call-me-back:        {callback_cnt}")
print(f"  No answer:           {no_answer}")

cur.close()
conn.close()

# ── Step 2: VYTAL appointments (vasu credentials) ────────────
print("[2] Fetching VYTAL appointments from Trino...")
engine = create_engine(url)
with engine.connect() as c:
    r = c.execute(text(f"""
        SELECT
            phrid                                   AS phr_id,
            appointmentdate                         AS appt_date,
            CAST(appointmentbookingdate AS VARCHAR)  AS booking_date,
            appointmentstatus                        AS status,
            speciality,
            vlocity_ins_fsc__productcode__c          AS product_code
        FROM deltalake.dl_standard_pbireporting.f_appointmentflattable
        WHERE vlocity_ins_fsc__productcode__c IN ({cs})
          AND (istestappt = 0 OR istestappt IS NULL)
          AND appointmentdate >= DATE '2026-04-01'
    """))
    df_appt = pd.DataFrame(r.fetchall(), columns=r.keys())
engine.dispose()
print(f"  Total appointments: {len(df_appt):,}  |  Unique users: {df_appt['phr_id'].nunique():,}")

# ── Step 3: Merge mobile hashes from policy CSV ───────────────
print("[3] Merging mobile hashes...")
df_appt = df_appt.merge(df_policy_raw, on='phr_id', how='left')

# ── Step 4: Classify source ───────────────────────────────────
df_appt['speciality_grp'] = df_appt['speciality'].apply(
    lambda x: 'Diet' if any(k in str(x).lower() for k in ['diet','nutri'])
              else ('Doctor' if any(k in str(x).lower() for k in ['physician','doctor','general'])
              else str(x))
)

# Classification Logic:
# Voice Bot = mobile_hash in answered_user_outcome (all voice bot campaign participants)
# Agent = has mobile_hash but NOT in answered_user_outcome
# Organic = no mobile_hash (cannot match to policy, direct bookings)
all_vb_users = set(user_outcome.keys())  # ALL answered VB campaign participants
df_appt['source'] = df_appt.apply(
    lambda row: ('Voice Bot' if (
        pd.notna(row['mobile_number_hash'])
        and row['mobile_number_hash'] in all_vb_users
        and row['status'] == 'COM'  # Only COM status = booked/completed
    ) else ('Organic' if pd.isna(row['mobile_number_hash']) else 'Agent')),
    axis=1
)

# ── Step 5: Save ─────────────────────────────────────────────
out = df_appt[['phr_id','appt_date','booking_date','status',
               'speciality','speciality_grp','product_code','source']].copy()
out.to_csv(OUT_FILE, index=False)
save_dataframe(out, "appt_source", if_exists="replace")
print(f"[Saved] {OUT_FILE}  ({len(out):,} rows)")

# Save voicebot funnel metrics for dashboard
# Only count as "booked" if voice bot user has completed appointment (claim created)
# Filter to appointments up to today to match dashboard date filtering
from datetime import datetime
today = pd.to_datetime(datetime.now().date())
df_appt['appt_date_parsed'] = pd.to_datetime(df_appt['appt_date'], errors='coerce')
df_appt_today = df_appt[df_appt['appt_date_parsed'] <= today]
vb_booked = int((df_appt_today['source'] == 'Voice Bot').sum())  # Only matched voice bot appointments

funnel = {
    "dialled":    total_dialled,
    "answered":   answered,
    "interested": len(interested_hashes),
    "booked":     vb_booked,
    "callback":   callback_cnt,
    "no_answer":  no_answer
}
with open(FUNNEL_FILE, 'w', encoding='utf-8') as f:
    json.dump(funnel, f, indent=2)
save_dataframe(pd.DataFrame([funnel]), "voicebot_performance", if_exists="replace")
print(f"[Saved] {FUNNEL_FILE}")

# Print summary
print("\n--- Summary ---")
print(out.groupby(['source','speciality_grp','status']).size().reset_index(name='count').to_string(index=False))
print("\nDone.")
