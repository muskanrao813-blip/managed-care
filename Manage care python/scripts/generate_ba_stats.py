"""
MANAGED CARE 3.0 — BA Operations Stats Generator
Reads pipeline CSVs + SQLite (when agents running) → writes Data/ba_stats.json
Run: python scripts/generate_ba_stats.py
"""
import sys, os, json
import pandas as pd
from datetime import datetime, date, timedelta
from collections import Counter

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = next((os.path.join(SCRIPT_DIR, d) for d in ["Data","data","DATA"]
                   if os.path.isdir(os.path.join(SCRIPT_DIR, d))),
                  os.path.join(SCRIPT_DIR, "Data"))
os.makedirs(DATA_DIR, exist_ok=True)

DB_CANDIDATES = [
    os.path.join(os.path.expanduser('~'), 'Documents', 'claude', 'vytals_care_coordinator', 'vytals_care.db'),
    os.path.join(os.path.dirname(SCRIPT_DIR), 'claude', 'vytals_care_coordinator', 'vytals_care.db'),
]
DB_PATH = next((p for p in DB_CANDIDATES if os.path.exists(p)), None)
OUT     = os.path.join(DATA_DIR, 'ba_stats.json')
TODAY   = date.today()

PROG_SHORT = {"Diabetes Management":"Diabetes","Dyslipidemia Management":"Dyslipidemia",
              "Thyroid Care":"Thyroid","Liver Care":"Liver","Kidney Care":"Kidney"}

def lcsv(f):
    p = os.path.join(DATA_DIR, f)
    return pd.read_csv(p, low_memory=False) if os.path.exists(p) else pd.DataFrame()

def ljson(f):
    p = os.path.join(DATA_DIR, f)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}

def pct(n, d): return round(n/d*100, 1) if d > 0 else 0
def si(v):
    try: return int(v)
    except: return 0
def sf(v):
    try: return round(float(v), 1)
    except: return 0.0

print("Loading pipeline data...")
alloc    = lcsv("managed_care_program_allocation.csv")
comp     = lcsv("managed_care_comparison.csv")
device   = lcsv("managed_care_device_eligibility.csv")
appt_u   = lcsv("managed_care_appt_utilization.csv")
insights = ljson("claude_insights.json")
adp      = ljson("managed_care_appt_deep.json")

m   = insights.get("metrics", {})
piv = m.get("improvement_pivot", {})
camp_users   = si(m.get("camp_users", m.get("camp_total", 0)))
camp_total   = si(m.get("camp_total", camp_users))
enrolled     = si(m.get("enrolled", 0))
mc_imp       = sf(piv.get("overall_mc_improved_pct", 0))
non_imp      = sf(piv.get("overall_non_mc_improved_pct", 0))
advantage    = round(mc_imp/non_imp, 1) if non_imp > 0 else 0
cohort_s     = m.get("cohort_split", {})
zero_a       = m.get("zero_appt", {})

prog_dist = {}
for prog, v in piv.get("by_programme", {}).items():
    sh = PROG_SHORT.get(prog, prog)
    prog_dist[sh] = {"mc_total": si(v.get("mc_total",0)),
                     "mc_improved_pct": sf(v.get("mc_improved_pct",0)),
                     "np_improved_pct": sf(v.get("np_improved_pct",0)),
                     "advantage_x":     sf(v.get("advantage_x",0)),
                     "mc_worsened_pct": sf(v.get("mc_worsened_pct",0))}

# Engagement
eng_dist, dev_dist, ls_dist, avg_eng = {}, {}, {}, 0
if not device.empty:
    if "engagement_tier" in device.columns:
        tc = device["engagement_tier"].value_counts().to_dict()
        td = len(device)
        for t in ["High","Moderate","Low","Very Low"]:
            n = si(tc.get(t,0)); eng_dist[t] = {"n":n,"pct":pct(n,td)}
        if "engagement_score" in device.columns:
            avg_eng = round(float(device["engagement_score"].dropna().mean()),1)
    if "primary_device" in device.columns:
        for d2, n in device["primary_device"].fillna("None").value_counts().items():
            dev_dist[str(d2)] = {"n":si(n),"pct":pct(n,len(device))}
    if "lifestyle_assessment" in device.columns:
        tags = []
        for val in device["lifestyle_assessment"].fillna("None"):
            for t in str(val).split("|"): tags.append(t.strip())
        for t, n in Counter(tags).items(): ls_dist[t] = si(n)

# Appointments
appt_kpis, ben_bd, fup, reps = {}, [], {}, []
if not appt_u.empty:
    nc = appt_u[~appt_u["claim_status"].str.lower().isin(["cancelled"])]
    bu = si(nc["phr_id"].nunique())
    cp = si(appt_u[appt_u["claim_status"].isin(["Redeemed","Paid"])]["claim_count"].sum())
    tc = si(nc["claim_count"].sum())
    ap = round(float(nc.groupby("phr_id")["claim_count"].sum().mean()),1) if bu > 0 else 0
    appt_kpis = {"enrolled":enrolled,"booked_users":bu,"booking_rate":pct(bu,enrolled),
                 "zero_appt":si(enrolled-bu),"zero_appt_pct":pct(enrolled-bu,enrolled),
                 "total_claims":tc,"completed":cp,"avg_per_user":ap}
    if "benefit_name" in appt_u.columns:
        for bn, grp in appt_u.groupby("benefit_name"):
            ben_bd.append({"benefit":str(bn),"users":si(grp["phr_id"].nunique()),"claims":si(grp["claim_count"].sum())})
        ben_bd.sort(key=lambda x: x["claims"], reverse=True)
if adp: fup = adp.get("followup_pending",{}); reps = adp.get("repeat_bookings",[])[:8]

# YoY
yoy = {}
if not comp.empty:
    tr = comp["mobile_number_hash"].nunique()
    imp = comp[comp["improvement_flag"]=="Improved"]["mobile_number_hash"].nunique()
    wor = comp[comp["improvement_flag"]=="Worsened"]["mobile_number_hash"].nunique()
    nc2 = comp[comp["improvement_flag"].isin(["No Change","No Risk"])]["mobile_number_hash"].nunique()
    yoy = {"total_retested":tr,"improved":si(imp),"improved_pct":pct(imp,tr),
           "worsened":si(wor),"worsened_pct":pct(wor,tr),"no_change":si(nc2)}
    by_prog = []
    if "managed_care_program" in comp.columns:
        for prog in comp["managed_care_program"].dropna().unique():
            if prog in ("None",""): continue
            sub = comp[comp["managed_care_program"]==prog]
            u = sub["mobile_number_hash"].nunique()
            i = sub[sub["improvement_flag"]=="Improved"]["mobile_number_hash"].nunique()
            w = sub[sub["improvement_flag"]=="Worsened"]["mobile_number_hash"].nunique()
            by_prog.append({"programme":PROG_SHORT.get(prog,prog),"total":u,
                            "improved_pct":pct(i,u),"worsened_pct":pct(w,u)})
        by_prog.sort(key=lambda x: x["improved_pct"], reverse=True)
    yoy["by_programme"] = by_prog

# SQLite agent stats
agent_stats = {"available": False}
if DB_PATH:
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
        tp   = conn.execute("SELECT COUNT(*) as n FROM patients WHERE is_active=1").fetchone()["n"]

        ch_stats = {}
        for r in conn.execute("SELECT channel,outcome,COUNT(*) as n FROM interaction_logs WHERE created_at>=datetime('now','-7 days') AND direction='outbound' GROUP BY channel,outcome").fetchall():
            ch = r["channel"] or "unknown"
            ch_stats.setdefault(ch,{"sent":0,"positive":0})
            ch_stats[ch]["sent"] += r["n"]
            if r["outcome"] in ("answered","responded","booked","button_yes","button_no","replied"):
                ch_stats[ch]["positive"] += r["n"]
        for ch in ch_stats:
            s = ch_stats[ch]; s["rate"] = pct(s["positive"],s["sent"])

        dr = {r["compliance_flag"]:r["n"] for r in conn.execute("SELECT compliance_flag,COUNT(*) as n FROM diet_adherence_logs WHERE created_at>=datetime('now','-7 days') GROUP BY compliance_flag").fetchall()}
        diet_pct = pct(dr.get("good",0),sum(dr.values()))

        med_open   = conn.execute("SELECT COUNT(*) n FROM medical_escalations WHERE status='open'").fetchone()["n"]
        churn_open = conn.execute("SELECT COUNT(*) n FROM churn_interventions WHERE status='open'").fetchone()["n"]

        sg_rows = []
        try:
            sg_rows = [dict(r) for r in conn.execute("SELECT p.phr_id,s.task_type,s.priority,s.status,s.description,s.created_at,s.due_by FROM sg_agent_tasks s JOIN patients p ON p.patient_id=s.patient_id WHERE s.status IN ('open','assigned') ORDER BY s.created_at DESC LIMIT 20").fetchall()]
        except: pass

        agent_runs = {}
        try:
            for r in conn.execute("SELECT agent_name,MAX(completed_at) last_run,SUM(users_processed) processed,SUM(error_count) errors,AVG(duration_sec) avg_dur FROM agent_run_log WHERE completed_at>=datetime('now','-7 days') GROUP BY agent_name").fetchall():
                agent_runs[r["agent_name"]] = {"last_run":r["last_run"] or "never","processed":si(r["processed"]),"errors":si(r["errors"]),"avg_sec":sf(r["avg_dur"])}
        except: pass

        traj_dist = {}
        try:
            for r in conn.execute("SELECT JSON_EXTRACT(signal_json,'$.directional_analysis.overall_direction') dir,COUNT(*) n FROM user_signal_snapshots WHERE generated_at>=datetime('now','-7 days') GROUP BY dir").fetchall():
                if r["dir"]: traj_dist[r["dir"]] = r["n"]
        except: pass

        upcoming = []
        try:
            upcoming = [dict(r) for r in conn.execute("SELECT p.phr_id,b.benefit_type,b.scheduled_date,b.status,b.attempt_count FROM plan_benefits_tracker b JOIN patients p ON p.patient_id=b.patient_id WHERE b.status='pending' AND b.scheduled_date<=date('now','+7 days') ORDER BY b.scheduled_date LIMIT 30").fetchall()]
        except: pass

        dir_counts = {}
        try:
            for r in conn.execute("SELECT overall_direction,COUNT(*) n FROM user_signal_snapshots WHERE generated_at>=datetime('now','-7 days') GROUP BY overall_direction").fetchall():
                if r["overall_direction"]: dir_counts[r["overall_direction"]] = r["n"]
        except: pass

        conn.close()
        agent_stats = {"available":True,"total_patients":tp,"channel_stats":ch_stats,
                       "diet_pct":diet_pct,"medical_open":si(med_open),"churn_open":si(churn_open),
                       "sg_tasks":sg_rows,"agent_runs":agent_runs,"traj_dist":traj_dist,
                       "direction_dist":dir_counts,"upcoming_week":upcoming}
        print(f"SQLite: {tp} active patients")
    except Exception as e:
        print(f"SQLite error: {e}")

recs      = insights.get("insights",{}).get("recommendations",[])[:5] if insights else []
ai_ov     = insights.get("insights",{}).get("overview",{}) if insights else {}
prog_ins  = insights.get("insights",{}).get("programme_outcomes",{}) if insights else {}

out = {"generated_at":datetime.now().strftime("%Y-%m-%d %H:%M"),"data_date":TODAY.isoformat(),
       "overview":{"camp_total":camp_total,"camp_users":camp_users,"enrolled":enrolled,
                   "coverage_pct":pct(enrolled,camp_users),"mc_improved_pct":mc_imp,
                   "non_improved_pct":non_imp,"advantage_x":advantage,
                   "zero_appt_n":si(zero_a.get("zero_appt",0)),"zero_appt_pct":sf(zero_a.get("pct",0)),
                   "cohort":{"very_high":si(cohort_s.get("Very High",0)),"high":si(cohort_s.get("High",0)),"moderate":si(cohort_s.get("Moderate",0))}},
       "programmes":prog_dist,
       "engagement":{"tiers":eng_dist,"avg_score":avg_eng,"device_dist":dev_dist,"lifestyle_dist":ls_dist},
       "appointments":{"kpis":appt_kpis,"benefit_breakdown":ben_bd,"follow_up_pending":fup,"repeat_bookings":reps},
       "yoy":yoy,"agent_stats":agent_stats,
       "insights":{"overview":ai_ov,"recommendations":recs,"programme_outcomes":prog_ins}}

with open(OUT,'w',encoding='utf-8') as f:
    json.dump(out,f,ensure_ascii=False,indent=2)
print(f"✅ ba_stats.json saved — {enrolled:,} enrolled | {mc_imp}% improved | {advantage}× advantage")
