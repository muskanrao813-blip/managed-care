"""Agent 4 — Care Planner: clinical schedule + engagement schedule (two lanes)."""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from state import PatientState
from nodes.llm import call_claude
from prompts.system_prompts import CARE_PLANNER_CLINICAL, CARE_PLANNER_ENGAGEMENT
from constants.programme_context import CLINICAL_CADENCE, BENEFIT_CAPS
import db
from datetime import datetime, timedelta


def _compute_clinical_dates(state: PatientState) -> dict:
    """Compute initial clinical schedule from enrolment date + cohort cadence."""
    cohort  = state["cohort"]
    cadence = CLINICAL_CADENCE.get(cohort, CLINICAL_CADENCE["HIGH"])
    start   = datetime.strptime(state["policy_start_date"], "%Y-%m-%d") \
              if state.get("policy_start_date") else datetime.now()

    schedule = {
        "doctor":    [(start + timedelta(days=cadence["first_doctor"])).strftime("%Y-%m-%d")],
        "dietician": [(start + timedelta(days=cadence["first_diet"])).strftime("%Y-%m-%d")]
                      if cadence["first_diet"] >= 0 else [],
        "lab":       [(start + timedelta(days=cadence["first_lab"])).strftime("%Y-%m-%d")],
    }
    return schedule


def _build_clinical_context(state: PatientState) -> str:
    counts  = db.get_consultation_counts(state["mobile_hash"])
    caps    = BENEFIT_CAPS.get(state["cohort"], BENEFIT_CAPS["HIGH"])
    trend   = db.get_hba1c_trend(state["mobile_hash"])
    sched   = db.get_clinical_schedule(state["mobile_hash"])

    return f"""
PATIENT: cohort={state['cohort']}, policy_start={state['policy_start_date']}

BENEFIT CAPS:
  doctor_max: {caps['doctor']}, doctor_used: {counts['doctor_used']}
  dietician_max: {caps['dietician']}, dietician_used: {counts['dietician_used']}

CLINICAL REVIEW NEEDED: {state['clinical_review_needed']}
HBA1C TREND: {json.dumps(trend)}

CURRENT SCHEDULE:
{json.dumps([dict(s) for s in sched], indent=2)}

TRIGGER: {state['trigger_event']}
"""


def _build_engagement_context(state: PatientState) -> str:
    eng = db.get_engagement_signals(state["mobile_hash"], days=7)
    return f"""
PSYCHOLOGY PROFILE:
  stage: {state['psych_stage']}
  comm_style: {state['comm_style']}
  fomo_sensitivity: {state['fomo_sensitivity']}
  smart_send_time: {state['smart_send_time']}
  distress_flag: {state['distress_flag']}
  frustration_stage: {state['frustration_stage']}

ENGAGEMENT SIGNALS (last 7 days):
  meal_logs: {eng['meal_logs']}
  step_logs: {eng['step_logs']}
  mood_logs: {eng['mood_logs']}

DIET LOG COMPLIANCE: {round(eng['meal_logs'] / 7 * 100)}%
"""


def care_planner_node(state: PatientState) -> dict:
    trigger = state["trigger_event"]

    # ── Clinical Lane ──────────────────────────────────────────────────────────
    clinical_schedule = {}
    if trigger in ("enrollment", "lab_received") or state["clinical_review_needed"]:
        ctx    = _build_clinical_context(state)
        result = call_claude(CARE_PLANNER_CLINICAL, ctx, max_tokens=512)

        if result:
            clinical_schedule = result.get("clinical_schedule", {})
            if result.get("flag_cap_reached"):
                db.update_patient(state["mobile_hash"], {"benefit_cap_reached": 1})
        else:
            # Fallback: compute dates directly
            clinical_schedule = _compute_clinical_dates(state)

        # Write to DB
        for appt_type, dates in clinical_schedule.items():
            for entry in (dates if isinstance(dates, list) else []):
                date   = entry["date"] if isinstance(entry, dict) else entry
                reason = entry.get("reason", trigger) if isinstance(entry, dict) else trigger
                # Only insert if not already scheduled
                existing = db.get_clinical_schedule(state["mobile_hash"])
                already  = any(s["appt_type"].upper() == appt_type.upper()
                                and s["scheduled_date"] == date for s in existing)
                if not already:
                    c = db.conn()
                    c.execute("""
                        INSERT INTO clinical_schedule
                        (mobile_hash, appt_type, scheduled_date, status, source)
                        VALUES (?,?,?,?,?)
                    """, (state["mobile_hash"], appt_type.upper(), date, "PENDING", reason))
                    c.commit()
                    c.close()

        # Save plan version
        db.save_care_plan(
            state["mobile_hash"], "clinical", trigger,
            f"Clinical schedule set from {trigger}",
            clinical_schedule
        )

    # ── Engagement Lane ────────────────────────────────────────────────────────
    eng_schedule = {}
    if trigger in ("enrollment", "weekly_psych", "wa_reply") or not state.get("psych_profile"):
        ctx2   = _build_engagement_context(state)
        result2 = call_claude(CARE_PLANNER_ENGAGEMENT, ctx2, max_tokens=256)

        if result2:
            eng_schedule = result2
            db.update_patient(state["mobile_hash"], {
                "smart_send_time": result2.get("send_time", state["smart_send_time"])
            })

        db.save_care_plan(
            state["mobile_hash"], "engagement", trigger,
            f"Engagement schedule set from {trigger}",
            eng_schedule
        )

    return {
        "clinical_schedule": clinical_schedule,
        "next_agent": "communication_crafter" if trigger == "enrollment" else state.get("next_agent"),
    }
