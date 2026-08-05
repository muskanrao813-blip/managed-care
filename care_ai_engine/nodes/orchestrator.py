"""Agent 1 — Orchestrator: reads full patient state, decides next action."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from state import PatientState
from nodes.llm import call_claude
from prompts.system_prompts import ORCHESTRATOR
import db
from datetime import datetime, timedelta


def build_context(state: PatientState) -> str:
    today = datetime.now().strftime("%A, %B %d %Y")
    sched = db.get_clinical_schedule(state["mobile_hash"])
    counts = db.get_consultation_counts(state["mobile_hash"])
    eng = db.get_engagement_signals(state["mobile_hash"], days=7)

    # Check if today is a clinical schedule date
    today_str = datetime.now().strftime("%Y-%m-%d")
    upcoming = [s for s in sched
                if s["scheduled_date"] <= (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")]

    return f"""Today: {today}
Trigger: {state['trigger_event']}

PATIENT:
  mobile_hash: {state['mobile_hash']}
  cohort: {state['cohort']}
  programme: {state['programme']}
  policy_start_date: {state['policy_start_date']}
  day_number: {state['day_number']}

CLINICAL:
  latest_hba1c: {state['latest_hba1c']}
  hba1c_target: {state['hba1c_target']}
  hba1c_band: {state['hba1c_band']}
  hba1c_delta: {state['hba1c_delta']}
  clinical_review_needed: {state['clinical_review_needed']}

BENEFITS USED:
  doctor: {counts['doctor_used']} / {state.get('doctor_max', 99)}
  dietician: {counts['dietician_used']} / {state.get('dietician_max', 99)}
  benefit_cap_reached: {state.get('benefit_cap_reached', False)}

UPCOMING CLINICAL DATES (next 3 days):
  {upcoming if upcoming else 'None'}

PSYCHOLOGY:
  stage: {state['psych_stage']}
  comm_style: {state['comm_style']}
  frustration_stage: {state['frustration_stage']}
  distress_flag: {state['distress_flag']}

ENGAGEMENT (last 7 days):
  meal_logs: {eng['meal_logs']} / 7
  step_logs: {eng['step_logs']} / 7
  mood_logs: {eng['mood_logs']} / 7
  consecutive_no_response: {state['consecutive_no_resp']}
  consecutive_missed_appts: {state['consecutive_missed']}
  last_nudge_channel: {state['last_nudge_channel']}
  last_nudge_responded: {state['last_nudge_responded']}

REWARDS:
  points: {state['points']}
  level: {state['level']}
  device_eligible: {state['device_eligible']}
  device_allocated: {state['device_allocated']}"""


def _fallback(state: PatientState) -> dict:
    """Rule-based decision when Claude is unavailable."""
    trigger = state["trigger_event"]

    if state["distress_flag"] or state["frustration_stage"] == "SOFT_REST":
        return {"action": "end", "priority_action": "Communication paused — distress/backoff",
                "urgency": "low", "reasoning": "Patient in distress or soft rest mode.",
                "message_type": None, "weekly_focus": "Recovery"}

    if trigger in ("enrollment",):
        return {"action": "health_profiler", "priority_action": "Profile new patient",
                "urgency": "high", "reasoning": "New enrolment — build health profile first.",
                "message_type": "welcome", "weekly_focus": "Onboarding"}

    if trigger == "lab_received":
        return {"action": "health_profiler", "priority_action": "Update health profile from new lab",
                "urgency": "high", "reasoning": "New lab result received.",
                "message_type": "lab_test", "weekly_focus": "Clinical review"}

    if trigger == "weekly_psych":
        return {"action": "psychology_profiler", "priority_action": "Weekly psychology refresh",
                "urgency": "low", "reasoning": "Weekly cadence update.",
                "message_type": None, "weekly_focus": "Engagement optimisation"}

    if trigger == "monthly_progress":
        return {"action": "progress_reporter", "priority_action": "Generate monthly report",
                "urgency": "low", "reasoning": "Monthly progress cycle.",
                "message_type": None, "weekly_focus": "Progress review"}

    if trigger == "wa_reply":
        return {"action": "diet_adherence", "priority_action": "Handle patient reply",
                "urgency": "medium", "reasoning": "Patient responded.",
                "message_type": "diet_checkin", "weekly_focus": "Engagement"}

    # Daily schedule — simple priority
    eng = db.get_engagement_signals(state["mobile_hash"], days=7)
    if eng["meal_logs"] < 3:
        return {"action": "communication_crafter", "priority_action": "Nudge meal logging",
                "urgency": "medium", "reasoning": "Low meal log adherence this week.",
                "message_type": "meal_log", "weekly_focus": "Diet adherence"}

    sched = db.get_clinical_schedule(state["mobile_hash"])
    from datetime import timedelta
    upcoming = [s for s in sched
                if s["scheduled_date"] <= (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")]
    if upcoming:
        return {"action": "appointment_coordinator", "priority_action": "Appointment reminder",
                "urgency": "high", "reasoning": f"Appointment due: {upcoming[0]['appt_type']}",
                "message_type": "appointment", "weekly_focus": "Clinical adherence"}

    return {"action": "communication_crafter", "priority_action": "Daily engagement nudge",
            "urgency": "low", "reasoning": "Standard daily engagement.",
            "message_type": "step_goal", "weekly_focus": "Lifestyle improvement"}


def orchestrator_node(state: PatientState) -> dict:
    context = build_context(state)
    result  = call_claude(ORCHESTRATOR, context, max_tokens=512) or _fallback(state)

    # Log the decision
    db.log_orchestrator_run(state["mobile_hash"], state["trigger_event"], result)

    return {
        "current_action":   result.get("action"),
        "next_agent":       result.get("action"),
        "escalate_to_human": result.get("action") == "escalate",
        "escalation_reason": result.get("escalation_reason"),
        "current_message":  {"type": result.get("message_type"),
                              "reasoning": result.get("reasoning"),
                              "weekly_focus": result.get("weekly_focus")},
    }
