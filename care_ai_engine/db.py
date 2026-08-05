"""
Local SQLite database for AI Care Coordinator engine.
No external setup needed — creates care_coordinator.db on first run.
All writes go here. Trino is read-only.
"""

import sqlite3, json, os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "care_coordinator.db"


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA = """
-- Core patient record (written once on enrolment, updated each orchestrator run)
CREATE TABLE IF NOT EXISTS patients (
    mobile_hash         TEXT PRIMARY KEY,
    phr_id              TEXT,
    product_code        TEXT,
    cohort              TEXT,           -- MODERATE | HIGH | VERY_HIGH
    programme           TEXT DEFAULT 'DIABETES',
    policy_start_date   TEXT,
    gender              TEXT,

    -- Clinical state (updated by Health Profiler)
    latest_hba1c        REAL,
    hba1c_target        REAL DEFAULT 7.0,
    hba1c_band          TEXT,           -- Normal|Moderate|High|Very High
    hba1c_delta         REAL,
    clinical_review_needed INTEGER DEFAULT 0,
    health_profile      TEXT,           -- JSON blob from Health Profiler

    -- Psychology state (updated weekly by Psychology Profiler)
    psych_stage         TEXT DEFAULT 'Pre-contemplation',
    motivation_type     TEXT DEFAULT 'Extrinsic',
    comm_style          TEXT DEFAULT 'Empathetic',
    barrier             TEXT DEFAULT 'None',
    fomo_sensitivity    TEXT DEFAULT 'Medium',
    smart_send_time     TEXT DEFAULT '18:30',
    distress_flag       INTEGER DEFAULT 0,
    frustration_stage   TEXT DEFAULT 'NORMAL',
    psych_profile       TEXT,           -- JSON from Psychology Profiler

    -- Engagement signals (updated after each interaction)
    meal_logs_7d        INTEGER DEFAULT 0,
    step_logs_7d        INTEGER DEFAULT 0,
    mood_logs_7d        INTEGER DEFAULT 0,
    weight_logs_7d      INTEGER DEFAULT 0,
    last_nudge_at       TEXT,
    last_nudge_channel  TEXT,
    last_nudge_responded INTEGER DEFAULT 0,
    consecutive_no_resp INTEGER DEFAULT 0,
    consecutive_missed  INTEGER DEFAULT 0,

    -- Rewards
    points              INTEGER DEFAULT 0,
    level               TEXT DEFAULT 'BRONZE',
    device_eligible     INTEGER DEFAULT 0,
    device_allocated    INTEGER DEFAULT 0,
    device_type         TEXT,

    -- Benefit caps (from BENEFIT_CAPS, written at enrolment)
    doctor_max          INTEGER DEFAULT 8,
    dietician_max       INTEGER DEFAULT 8,

    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

-- Clinical schedule per patient
CREATE TABLE IF NOT EXISTS clinical_schedule (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile_hash     TEXT NOT NULL,
    appt_type       TEXT NOT NULL,      -- DOCTOR | DIETICIAN | LAB_TEST
    scheduled_date  TEXT NOT NULL,
    status          TEXT DEFAULT 'PENDING',  -- PENDING|BOOKED|COMPLETED|MISSED
    source          TEXT,               -- enrollment | lab_trigger | improvement
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mobile_hash) REFERENCES patients(mobile_hash)
);

-- Every consultation booked (tracked in our DB, sourced from f_claim / appointments)
CREATE TABLE IF NOT EXISTS consultations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile_hash     TEXT NOT NULL,
    phr_id          TEXT,
    consult_type    TEXT NOT NULL,      -- DOCTOR | DIETICIAN | LAB_TEST
    benefit_name    TEXT,               -- raw value from f_claim.benefit_name
    provider_name   TEXT,
    consult_date    TEXT,
    status          TEXT DEFAULT 'BOOKED',  -- BOOKED|COMPLETED|CANCELLED
    outcome_notes   TEXT,
    points_awarded  INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mobile_hash) REFERENCES patients(mobile_hash)
);

-- Every nudge sent (WhatsApp / Voice / App)
CREATE TABLE IF NOT EXISTS nudge_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile_hash     TEXT NOT NULL,
    channel         TEXT NOT NULL,      -- WHATSAPP | VOICE_BOT | APP_NUDGE
    tier            INTEGER DEFAULT 1,  -- 1=first send, 2=rechurn, 3=voice
    trigger_event   TEXT,               -- what caused this nudge
    script_variant  TEXT,               -- empathetic_v1 | fomo_high_v1 | etc.
    message         TEXT NOT NULL,
    quick_replies   TEXT,               -- JSON array
    scheduled_at    TEXT,
    sent_at         TEXT,
    responded_at    TEXT,
    response        TEXT,
    status          TEXT DEFAULT 'PENDING',  -- PENDING|SENT|RESPONDED|IGNORED
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mobile_hash) REFERENCES patients(mobile_hash)
);

-- Monthly adherence scores
CREATE TABLE IF NOT EXISTS adherence_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile_hash     TEXT NOT NULL,
    score_month     TEXT NOT NULL,      -- YYYY-MM
    clinical_score  REAL DEFAULT 0,     -- 0-30
    engagement_score REAL DEFAULT 0,    -- 0-25
    intent_score    REAL DEFAULT 0,     -- 0-25
    lifestyle_score REAL DEFAULT 0,     -- 0-20
    total_score     REAL DEFAULT 0,     -- 0-100
    score_band      TEXT,               -- Very Low|Low|Moderate|High
    delta_from_last REAL,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mobile_hash) REFERENCES patients(mobile_hash)
);

-- HbA1c and biomarker history (written each time a new lab comes in from Trino)
CREATE TABLE IF NOT EXISTS lab_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile_hash     TEXT NOT NULL,
    phr_id          TEXT,
    test_date       TEXT NOT NULL,
    loinc_id        TEXT,
    test_name       TEXT,
    value           REAL,
    unit            TEXT,
    source          TEXT DEFAULT 'trino_sync',
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mobile_hash) REFERENCES patients(mobile_hash)
);

-- Device and lifestyle reward allocation
CREATE TABLE IF NOT EXISTS reward_allocations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile_hash     TEXT NOT NULL,
    reward_type     TEXT NOT NULL,      -- CGM|Glucometer|Weighing_Scale|BP_Monitor
    eligibility_date TEXT,
    fomo_nudge_sent INTEGER DEFAULT 0,
    allocated       INTEGER DEFAULT 0,
    allocation_date TEXT,
    status          TEXT DEFAULT 'eligible',  -- eligible|allocated|dispatched|delivered
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mobile_hash) REFERENCES patients(mobile_hash)
);

-- Orchestrator decision log (every daily run)
CREATE TABLE IF NOT EXISTS orchestrator_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile_hash     TEXT NOT NULL,
    run_date        TEXT NOT NULL,
    trigger_event   TEXT,
    priority_action TEXT,
    urgency         TEXT,
    reasoning       TEXT,
    actions         TEXT,               -- JSON
    watch_signals   TEXT,               -- JSON
    risk_flags      TEXT,               -- JSON
    escalate        INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mobile_hash) REFERENCES patients(mobile_hash)
);

-- Human escalation queue (SG Agent tasks)
CREATE TABLE IF NOT EXISTS escalations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile_hash     TEXT NOT NULL,
    reason          TEXT NOT NULL,      -- repeated_miss|benefit_cap|distress|emergency
    priority        TEXT DEFAULT 'HIGH',
    status          TEXT DEFAULT 'OPEN',  -- OPEN|IN_PROGRESS|RESOLVED
    subject         TEXT,
    description     TEXT,
    call_script     TEXT,
    resolved_at     TEXT,
    resolved_by     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mobile_hash) REFERENCES patients(mobile_hash)
);

-- User self-logs (weight, steps, mood, meals — from app)
CREATE TABLE IF NOT EXISTS user_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile_hash     TEXT NOT NULL,
    log_type        TEXT NOT NULL,      -- weight|steps|mood|meal|glucose
    log_date        TEXT NOT NULL,
    value           TEXT,               -- JSON: {kg:78.5} or {score:3} or {steps:6200}
    source          TEXT DEFAULT 'app', -- app|wearable|manual
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mobile_hash) REFERENCES patients(mobile_hash)
);

-- Care plan versions (audit trail of all plan changes)
CREATE TABLE IF NOT EXISTS care_plan_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile_hash     TEXT NOT NULL,
    version         INTEGER NOT NULL,
    lane            TEXT NOT NULL,      -- clinical | engagement
    trigger         TEXT,               -- enrollment|lab_result|weekly_psych|improvement
    reason          TEXT,
    clinical_schedule TEXT,             -- JSON
    engagement_schedule TEXT,           -- JSON
    dietary_focus   TEXT,
    status          TEXT DEFAULT 'active',  -- active|superseded
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (mobile_hash) REFERENCES patients(mobile_hash)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_nudge_mobile    ON nudge_events(mobile_hash, status);
CREATE INDEX IF NOT EXISTS idx_consult_mobile  ON consultations(mobile_hash, consult_type);
CREATE INDEX IF NOT EXISTS idx_lab_mobile      ON lab_history(mobile_hash, loinc_id);
CREATE INDEX IF NOT EXISTS idx_orch_mobile     ON orchestrator_log(mobile_hash, run_date);
CREATE INDEX IF NOT EXISTS idx_logs_mobile     ON user_logs(mobile_hash, log_type, log_date);
CREATE INDEX IF NOT EXISTS idx_schedule_mobile ON clinical_schedule(mobile_hash, appt_type, status);
"""


def init_db():
    """Create all tables. Safe to call multiple times."""
    c = conn()
    c.executescript(SCHEMA)
    c.commit()
    c.close()
    print(f"[DB] Initialised: {DB_PATH}")


# ─────────────────────────────────────────────────────────────────────────────
# SEED — one realistic diabetes patient for testing
# ─────────────────────────────────────────────────────────────────────────────

def seed_test_patient():
    """
    Seeds one Diabetes patient with realistic history.
    Safe to call multiple times — skips if patient already exists.
    """
    c = conn()
    existing = c.execute(
        "SELECT mobile_hash FROM patients WHERE mobile_hash = 'TEST_HASH_001'"
    ).fetchone()
    if existing:
        c.close()
        print("[DB] Test patient already seeded — skipping")
        return

    today = datetime.now()

    # ── Patient record ────────────────────────────────────────────────────────
    c.execute("""
        INSERT INTO patients (
            mobile_hash, phr_id, product_code, cohort, programme,
            policy_start_date, gender,
            latest_hba1c, hba1c_target, hba1c_band, hba1c_delta,
            psych_stage, comm_style, fomo_sensitivity, smart_send_time,
            points, level, device_type, device_eligible,
            doctor_max, dietician_max
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        "TEST_HASH_001", "PHR_TEST_001", "VYTAL0626", "VERY_HIGH", "DIABETES",
        (today - timedelta(days=5)).strftime("%Y-%m-%d"), "Male",
        7.5, 7.0, "High", -0.3,
        "Action", "Achievement", "High", "18:30",
        340, "SILVER", "CGM", 1,
        99, 99
    ))

    # ── HbA1c history (3 months) ───────────────────────────────────────────────
    hba1c_data = [
        ((today - timedelta(days=90)).strftime("%Y-%m-%d"), "4548-4", "HbA1c", 8.2, "%"),
        ((today - timedelta(days=60)).strftime("%Y-%m-%d"), "4548-4", "HbA1c", 7.8, "%"),
        ((today - timedelta(days=30)).strftime("%Y-%m-%d"), "4548-4", "HbA1c", 7.5, "%"),
    ]
    for (dt, loinc, name, val, unit) in hba1c_data:
        c.execute("""
            INSERT INTO lab_history (mobile_hash, phr_id, test_date, loinc_id, test_name, value, unit)
            VALUES (?,?,?,?,?,?,?)
        """, ("TEST_HASH_001", "PHR_TEST_001", dt, loinc, name, val, unit))

    # ── Clinical schedule (generated at enrolment) ─────────────────────────────
    enrol = today - timedelta(days=5)
    schedules = [
        ("DOCTOR",    (enrol + timedelta(days=30)).strftime("%Y-%m-%d"),  "PENDING", "enrollment"),
        ("DIETICIAN", (enrol + timedelta(days=1)).strftime("%Y-%m-%d"),   "PENDING", "enrollment"),
        ("LAB_TEST",  (enrol + timedelta(days=90)).strftime("%Y-%m-%d"),  "PENDING", "enrollment"),
    ]
    for (atype, dt, status, src) in schedules:
        c.execute("""
            INSERT INTO clinical_schedule (mobile_hash, appt_type, scheduled_date, status, source)
            VALUES (?,?,?,?,?)
        """, ("TEST_HASH_001", atype, dt, status, src))

    # ── User logs (14 days) ────────────────────────────────────────────────────
    for i in range(14):
        d = (today - timedelta(days=13 - i)).strftime("%Y-%m-%d")
        # Steps every day
        steps = [4200,3800,6500,4100,5200,3900,7100,4500,4300,6800,5100,4000,4700,3600][i]
        c.execute("INSERT INTO user_logs (mobile_hash, log_type, log_date, value) VALUES (?,?,?,?)",
                  ("TEST_HASH_001", "steps", d, json.dumps({"steps": steps, "target": 8000})))
        # Meals on some days
        if i in [0, 1, 3, 4, 6, 8, 9, 11, 13]:
            c.execute("INSERT INTO user_logs (mobile_hash, log_type, log_date, value) VALUES (?,?,?,?)",
                      ("TEST_HASH_001", "meal", d, json.dumps({"meals": ["Poha", "Dal rice"], "calories": 1600})))
        # Weight every 3 days
        if i % 3 == 0:
            c.execute("INSERT INTO user_logs (mobile_hash, log_type, log_date, value) VALUES (?,?,?,?)",
                      ("TEST_HASH_001", "weight", d, json.dumps({"kg": round(82.4 - i * 0.05, 1)})))

    # ── Past nudges ────────────────────────────────────────────────────────────
    nudges = [
        ("WHATSAPP", 1, "daily_schedule", "achievement_v1",
         "Great progress! Your HbA1c dropped from 8.2 to 7.5 in 3 months!",
         (today - timedelta(days=10)).isoformat(), "RESPONDED", "Thanks!"),
        ("WHATSAPP", 1, "meal_log_gap", "empathetic_v1",
         "Hi! You haven't logged lunch today. Want to log it now?",
         (today - timedelta(days=2)).isoformat(), "RESPONDED", "Will do"),
    ]
    for (ch, tier, trigger, variant, msg, sent_at, status, resp) in nudges:
        c.execute("""
            INSERT INTO nudge_events
            (mobile_hash, channel, tier, trigger_event, script_variant, message, sent_at, response, status)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, ("TEST_HASH_001", ch, tier, trigger, variant, msg, sent_at, resp, status))

    # ── Monthly adherence score ────────────────────────────────────────────────
    c.execute("""
        INSERT INTO adherence_scores
        (mobile_hash, score_month, clinical_score, engagement_score, intent_score, lifestyle_score, total_score, score_band)
        VALUES (?,?,?,?,?,?,?,?)
    """, ("TEST_HASH_001", today.strftime("%Y-%m"), 22.5, 18.0, 16.0, 12.0, 68.5, "Moderate"))

    # ── Reward allocation ──────────────────────────────────────────────────────
    c.execute("""
        INSERT INTO reward_allocations (mobile_hash, reward_type, eligibility_date, allocated, status)
        VALUES (?,?,?,?,?)
    """, ("TEST_HASH_001", "CGM", today.strftime("%Y-%m-%d"), 0, "eligible"))

    c.commit()
    c.close()
    print("[DB] Test patient seeded: TEST_HASH_001 (VYTAL0626, VERY_HIGH, Diabetes)")


# ─────────────────────────────────────────────────────────────────────────────
# READ HELPERS — used by orchestrator nodes
# ─────────────────────────────────────────────────────────────────────────────

def get_patient(mobile_hash: str) -> dict | None:
    c = conn()
    row = c.execute("SELECT * FROM patients WHERE mobile_hash = ?", (mobile_hash,)).fetchone()
    c.close()
    return dict(row) if row else None


def get_pending_nudge(mobile_hash: str) -> dict | None:
    c = conn()
    row = c.execute("""
        SELECT * FROM nudge_events
        WHERE mobile_hash = ? AND status = 'SENT'
        ORDER BY sent_at DESC LIMIT 1
    """, (mobile_hash,)).fetchone()
    c.close()
    return dict(row) if row else None


def get_clinical_schedule(mobile_hash: str) -> list:
    c = conn()
    rows = c.execute("""
        SELECT * FROM clinical_schedule
        WHERE mobile_hash = ? AND status = 'PENDING'
        ORDER BY scheduled_date
    """, (mobile_hash,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_consultation_counts(mobile_hash: str) -> dict:
    c = conn()
    rows = c.execute("""
        SELECT consult_type, COUNT(*) as cnt
        FROM consultations
        WHERE mobile_hash = ? AND status = 'COMPLETED'
        GROUP BY consult_type
    """, (mobile_hash,)).fetchall()
    c.close()
    counts = {r["consult_type"]: r["cnt"] for r in rows}
    return {
        "doctor_used":    counts.get("DOCTOR", 0),
        "dietician_used": counts.get("DIETICIAN", 0),
        "lab_used":       counts.get("LAB_TEST", 0),
    }


def get_engagement_signals(mobile_hash: str, days: int = 7) -> dict:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    c = conn()
    rows = c.execute("""
        SELECT log_type, COUNT(*) as cnt
        FROM user_logs
        WHERE mobile_hash = ? AND log_date >= ?
        GROUP BY log_type
    """, (mobile_hash, since)).fetchall()
    c.close()
    counts = {r["log_type"]: r["cnt"] for r in rows}
    return {
        "meal_logs":   counts.get("meal", 0),
        "step_logs":   counts.get("steps", 0),
        "mood_logs":   counts.get("mood", 0),
        "weight_logs": counts.get("weight", 0),
    }


def get_hba1c_trend(mobile_hash: str) -> list:
    c = conn()
    rows = c.execute("""
        SELECT test_date, value, unit FROM lab_history
        WHERE mobile_hash = ? AND loinc_id = '4548-4'
        ORDER BY test_date
    """, (mobile_hash,)).fetchall()
    c.close()
    return [{"date": r["test_date"], "value": r["value"], "unit": r["unit"]} for r in rows]


def get_recent_nudges(mobile_hash: str, limit: int = 5) -> list:
    c = conn()
    rows = c.execute("""
        SELECT * FROM nudge_events
        WHERE mobile_hash = ?
        ORDER BY created_at DESC LIMIT ?
    """, (mobile_hash, limit)).fetchall()
    c.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# WRITE HELPERS — used by orchestrator nodes and tool layer
# ─────────────────────────────────────────────────────────────────────────────

def update_patient(mobile_hash: str, fields: dict):
    """Generic patient field update. Pass only the fields that changed."""
    if not fields:
        return
    fields["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values     = list(fields.values()) + [mobile_hash]
    c = conn()
    c.execute(f"UPDATE patients SET {set_clause} WHERE mobile_hash = ?", values)
    c.commit()
    c.close()


def log_nudge(mobile_hash: str, channel: str, tier: int, trigger: str,
              variant: str, message: str, quick_replies: list = None) -> int:
    c = conn()
    cur = c.execute("""
        INSERT INTO nudge_events
        (mobile_hash, channel, tier, trigger_event, script_variant, message, quick_replies, scheduled_at, status)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (mobile_hash, channel, tier, trigger, variant, message,
          json.dumps(quick_replies or []),
          datetime.now().isoformat(), "PENDING"))
    nid = cur.lastrowid
    c.commit()
    c.close()
    return nid


def mark_nudge_sent(nudge_id: int):
    c = conn()
    c.execute("UPDATE nudge_events SET status='SENT', sent_at=? WHERE id=?",
              (datetime.now().isoformat(), nudge_id))
    c.commit()
    c.close()


def mark_nudge_responded(mobile_hash: str, response: str):
    c = conn()
    c.execute("""
        UPDATE nudge_events
        SET status='RESPONDED', responded_at=?, response=?
        WHERE mobile_hash=? AND status='SENT'
        ORDER BY sent_at DESC LIMIT 1
    """, (datetime.now().isoformat(), response, mobile_hash))
    c.execute("""
        UPDATE patients SET last_nudge_responded=1, consecutive_no_resp=0
        WHERE mobile_hash=?
    """, (mobile_hash,))
    c.commit()
    c.close()


def log_consultation(mobile_hash: str, phr_id: str, consult_type: str,
                     benefit_name: str, provider: str, date: str,
                     status: str = "BOOKED") -> int:
    c = conn()
    cur = c.execute("""
        INSERT INTO consultations
        (mobile_hash, phr_id, consult_type, benefit_name, provider_name, consult_date, status)
        VALUES (?,?,?,?,?,?,?)
    """, (mobile_hash, phr_id, consult_type, benefit_name, provider, date, status))
    cid = cur.lastrowid
    c.commit()
    c.close()
    return cid


def log_lab_result(mobile_hash: str, phr_id: str, test_date: str,
                   loinc_id: str, test_name: str, value: float, unit: str):
    c = conn()
    c.execute("""
        INSERT INTO lab_history
        (mobile_hash, phr_id, test_date, loinc_id, test_name, value, unit)
        VALUES (?,?,?,?,?,?,?)
    """, (mobile_hash, phr_id, test_date, loinc_id, test_name, value, unit))
    # Update patient's latest HbA1c if applicable
    if loinc_id in ("4548-4", "59261-8"):
        c.execute(
            "UPDATE patients SET latest_hba1c=?, updated_at=? WHERE mobile_hash=?",
            (value, datetime.now().isoformat(), mobile_hash)
        )
    c.commit()
    c.close()


def log_user_activity(mobile_hash: str, log_type: str, value: dict, log_date: str = None):
    date = log_date or datetime.now().strftime("%Y-%m-%d")
    c = conn()
    c.execute("""
        INSERT INTO user_logs (mobile_hash, log_type, log_date, value)
        VALUES (?,?,?,?)
    """, (mobile_hash, log_type, date, json.dumps(value)))
    c.commit()
    c.close()


def add_points(mobile_hash: str, pts: int):
    c = conn()
    c.execute("UPDATE patients SET points = points + ?, updated_at=? WHERE mobile_hash=?",
              (pts, datetime.now().isoformat(), mobile_hash))
    # Recalculate level
    row = c.execute("SELECT points FROM patients WHERE mobile_hash=?", (mobile_hash,)).fetchone()
    if row:
        p = row["points"]
        level = "PLATINUM" if p >= 1000 else "GOLD" if p >= 500 else "SILVER" if p >= 200 else "BRONZE"
        c.execute("UPDATE patients SET level=? WHERE mobile_hash=?", (level, mobile_hash))
    c.commit()
    c.close()


def create_escalation(mobile_hash: str, reason: str, priority: str,
                      subject: str, description: str, call_script: str) -> int:
    c = conn()
    cur = c.execute("""
        INSERT INTO escalations
        (mobile_hash, reason, priority, subject, description, call_script)
        VALUES (?,?,?,?,?,?)
    """, (mobile_hash, reason, priority, subject, description, call_script))
    eid = cur.lastrowid
    # Set frustration_stage to SOFT_REST — stop all automated comms
    c.execute(
        "UPDATE patients SET frustration_stage='SOFT_REST', updated_at=? WHERE mobile_hash=?",
        (datetime.now().isoformat(), mobile_hash)
    )
    c.commit()
    c.close()
    return eid


def log_orchestrator_run(mobile_hash: str, trigger: str, plan: dict):
    c = conn()
    c.execute("""
        INSERT INTO orchestrator_log
        (mobile_hash, run_date, trigger_event, priority_action, urgency,
         reasoning, actions, watch_signals, risk_flags, escalate)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        mobile_hash,
        datetime.now().strftime("%Y-%m-%d"),
        trigger,
        plan.get("priority_action", ""),
        plan.get("urgency", "medium"),
        plan.get("reasoning", ""),
        json.dumps(plan.get("actions", [])),
        json.dumps(plan.get("watch_signals", [])),
        json.dumps(plan.get("risk_flags", [])),
        1 if plan.get("escalate_to_human") else 0,
    ))
    c.commit()
    c.close()


def save_care_plan(mobile_hash: str, lane: str, trigger: str,
                   reason: str, schedule: dict, dietary_focus: str = None):
    c = conn()
    # Get next version number
    row = c.execute("""
        SELECT COALESCE(MAX(version), 0) + 1 AS next_v
        FROM care_plan_versions WHERE mobile_hash=?
    """, (mobile_hash,)).fetchone()
    version = row["next_v"]
    # Supersede previous active plans for this lane
    c.execute("""
        UPDATE care_plan_versions SET status='superseded'
        WHERE mobile_hash=? AND lane=? AND status='active'
    """, (mobile_hash, lane))
    # Insert new version
    c.execute("""
        INSERT INTO care_plan_versions
        (mobile_hash, version, lane, trigger, reason, clinical_schedule, dietary_focus, status)
        VALUES (?,?,?,?,?,?,?,?)
    """, (mobile_hash, version, lane, trigger, reason,
          json.dumps(schedule), dietary_focus, "active"))
    c.commit()
    c.close()
    return version


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD HELPERS — used by the API layer
# ─────────────────────────────────────────────────────────────────────────────

def get_all_patients() -> list:
    c = conn()
    rows = c.execute("""
        SELECT mobile_hash, product_code, cohort, latest_hba1c,
               hba1c_target, psych_stage, frustration_stage,
               points, level, device_eligible, created_at
        FROM patients ORDER BY created_at DESC
    """).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_escalation_queue() -> list:
    c = conn()
    rows = c.execute("""
        SELECT e.*, p.cohort, p.latest_hba1c
        FROM escalations e
        JOIN patients p ON e.mobile_hash = p.mobile_hash
        WHERE e.status IN ('OPEN','IN_PROGRESS')
        ORDER BY e.created_at DESC
    """).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_orchestrator_history(mobile_hash: str, limit: int = 10) -> list:
    c = conn()
    rows = c.execute("""
        SELECT * FROM orchestrator_log
        WHERE mobile_hash=? ORDER BY created_at DESC LIMIT ?
    """, (mobile_hash, limit)).fetchall()
    c.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    seed_test_patient()
    print(f"\n[DB] Database ready at: {DB_PATH}")
    print("[DB] Tables: patients, clinical_schedule, consultations, nudge_events,")
    print("             adherence_scores, lab_history, reward_allocations,")
    print("             orchestrator_log, escalations, user_logs, care_plan_versions")
