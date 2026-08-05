"""Agent 7 — Appointment Coordinator: reminders, bookings, missed recovery."""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from state import PatientState
from nodes.llm import call_claude
from prompts.system_prompts import APPOINTMENT_COORDINATOR
from constants.programme_context import BENEFIT_CAPS
import db
from datetime import datetime, timedelta


def appointment_coordinator_node(state: PatientState) -> dict:
    sched  = db.get_clinical_schedule(state["mobile_hash"])
    counts = db.get_consultation_counts(state["mobile_hash"])
    caps   = BENEFIT_CAPS.get(state["cohort"], BENEFIT_CAPS["HIGH"])
    today  = datetime.now()

    # Find appointments due in next 3 days
    upcoming = []
    for s in sched:
        if s["status"] == "PENDING":
            due = datetime.strptime(s["scheduled_date"], "%Y-%m-%d")
            days_away = (due - today).days
            if -2 <= days_away <= 3:
                upcoming.append({**dict(s), "days_away": days_away})

    if not upcoming:
        return {"current_action": "none"}

    # Check benefit caps
    appt = upcoming[0]
    appt_type = appt["appt_type"]
    used_key  = "doctor_used" if appt_type == "DOCTOR" else "dietician_used"
    max_key   = "doctor" if appt_type == "DOCTOR" else "dietician"
    used = counts.get(used_key, 0)
    cap  = caps.get(max_key, 99)

    if used >= cap:
        db.create_escalation(
            state["mobile_hash"], "benefit_cap", "MEDIUM",
            f"Benefit cap reached — {appt_type}",
            f"Patient has used all {cap} {appt_type} consultations.",
            "Hello, I am calling to discuss your consultation benefits for this year."
        )
        db.update_patient(state["mobile_hash"], {"benefit_cap_reached": 1})
        return {"benefit_cap_reached": True, "escalate_to_human": True,
                "escalation_reason": "benefit_cap"}

    # Build context for Claude
    context = f"""
UPCOMING APPOINTMENT:
  type: {appt_type}
  date: {appt['scheduled_date']}
  days_away: {appt['days_away']}
  status: {appt['status']}

PATIENT:
  comm_style: {state['comm_style']}
  barrier: {state['barrier']}
  consecutive_missed: {state['consecutive_missed']}
  doctor_used: {counts['doctor_used']} / {cap}
  dietician_used: {counts['dietician_used']} / {caps.get('dietician', 99)}

MISSED RECOVERY:
  is_missed: {appt['days_away'] < 0}
  consecutive_missed: {state['consecutive_missed']}
"""
    result = call_claude(APPOINTMENT_COORDINATOR, context, max_tokens=512)

    if not result:
        # Fallback message
        if appt["days_away"] < 0:
            msg = (f"Hi! We noticed you missed your {appt_type.lower()} consultation on {appt['scheduled_date']}. "
                   f"No worries — your slot can be rebooked easily. "
                   f"Reply REBOOK and we will set a new time within 2 days.")
            qr  = ["REBOOK", "Next week", "Not interested"]
        else:
            msg = (f"Reminder: Your {appt_type.lower()} consultation is on {appt['scheduled_date']}. "
                   f"It is a video call — no travel needed. Reply CONFIRM to lock it in.")
            qr  = ["CONFIRM", "RESCHEDULE", "Help"]
        result = {"action": "send_reminder", "message": msg,
                  "quick_replies": qr, "points_on_completion": 25}

    # Log and send nudge
    nudge_id = db.log_nudge(
        state["mobile_hash"], "WHATSAPP", 1,
        "appt_reminder", "appointment_v1",
        result.get("message", ""), result.get("quick_replies", [])
    )
    db.mark_nudge_sent(nudge_id)

    # If escalation needed after 3 misses
    if result.get("escalate_to_sfdc") or state["consecutive_missed"] >= 3:
        db.create_escalation(
            state["mobile_hash"], "repeated_miss", "HIGH",
            f"3+ consecutive missed {appt_type} appointments",
            "Patient has missed 3+ appointments. Automated rescheduling stopped.",
            f"Hello, this is your VYTAL care team. We noticed you have missed your last few "
            f"{appt_type.lower()} appointments. We would like to help reschedule at a convenient time."
        )
        return {"escalate_to_human": True, "escalation_reason": "repeated_miss",
                "consecutive_missed": state["consecutive_missed"]}

    return {
        "current_message": {
            "type": "appointment", "nudge_id": nudge_id,
            "script": result.get("message", ""),
            "appt_type": appt_type, "appt_date": appt["scheduled_date"]
        }
    }
