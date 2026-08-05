"""Agent 3 — Psychology Profiler: infers stage of change, updates comm strategy."""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from state import PatientState
from nodes.llm import call_claude
from prompts.system_prompts import PSYCHOLOGY_PROFILER
import db


def _build_context(state: PatientState) -> str:
    eng  = db.get_engagement_signals(state["mobile_hash"], days=7)
    nudges = db.get_recent_nudges(state["mobile_hash"], limit=10)
    responded  = sum(1 for n in nudges if n["status"] == "RESPONDED")
    sent       = sum(1 for n in nudges if n["status"] in ("SENT", "RESPONDED", "IGNORED"))
    counts = db.get_consultation_counts(state["mobile_hash"])

    return f"""
WEEKLY SIGNALS (last 7 days):
  meal_logs_7d: {eng['meal_logs']} / 7
  step_logs_7d: {eng['step_logs']} / 7
  mood_logs_7d: {eng['mood_logs']} / 7
  weight_logs_7d: {eng['weight_logs']} / 7
  whatsapp_sent: {sent}
  whatsapp_responded: {responded}
  consecutive_no_response: {state['consecutive_no_resp']}
  consecutive_missed_appts: {state['consecutive_missed']}
  last_nudge_channel: {state['last_nudge_channel']}
  last_nudge_responded: {state['last_nudge_responded']}

APPOINTMENTS (since enrolment):
  doctor_completed: {counts['doctor_used']}
  dietician_completed: {counts['dietician_used']}

HRA:
  hra_completed: {state.get('hra_completed', False)}
  stress_level: {state.get('stress_level', 'Unknown')}
  sleep_hours: {state.get('sleep_hours', 'Unknown')}
  alcohol_risk: {state.get('alcohol_risk', False)}

PREVIOUS PSYCH PROFILE:
{state.get('psych_profile') or 'None — baseline run'}
"""


def _fallback(state: PatientState) -> dict:
    eng = db.get_engagement_signals(state["mobile_hash"], days=7)
    nudges = db.get_recent_nudges(state["mobile_hash"], limit=10)
    responded = sum(1 for n in nudges if n["status"] == "RESPONDED")

    if eng["meal_logs"] >= 5 and responded >= 3:
        stage, style = "Action", "Achievement"
    elif responded >= 1 or eng["meal_logs"] >= 2:
        stage, style = "Contemplation", "Empathetic"
    else:
        stage, style = "Pre-contemplation", "FOMO"

    distress = (state.get("stress_high") and eng["meal_logs"] == 0
                and state["consecutive_missed"] >= 2)

    return {
        "stage": stage, "motivation_type": "Extrinsic",
        "comm_style": style, "barrier": "Time",
        "fomo_sensitivity": "Medium", "contact_window": "evening",
        "smart_send_time": "18:30",
        "distress_flag": distress, "escalate_to_sfdc": state["consecutive_missed"] >= 3,
        "frustration_stage": "SOFT_REST" if distress else "NORMAL",
        "profile_summary": f"Patient in {stage} stage with {style} communication preference."
    }


def psychology_profiler_node(state: PatientState) -> dict:
    context = _build_context(state)
    result  = call_claude(PSYCHOLOGY_PROFILER, context, max_tokens=512) or _fallback(state)

    profile_json = json.dumps(result)
    updates = {
        "psych_profile":    profile_json,
        "psych_stage":      result.get("stage", state["psych_stage"]),
        "motivation_type":  result.get("motivation_type", state["motivation_type"]),
        "comm_style":       result.get("comm_style", state["comm_style"]),
        "barrier":          result.get("barrier", state["barrier"]),
        "fomo_sensitivity": result.get("fomo_sensitivity", state["fomo_sensitivity"]),
        "smart_send_time":  result.get("smart_send_time", state["smart_send_time"]),
        "distress_flag":    1 if result.get("distress_flag") else 0,
        "frustration_stage": result.get("frustration_stage", state["frustration_stage"]),
    }
    db.update_patient(state["mobile_hash"], updates)

    # Create escalation if needed
    if result.get("escalate_to_sfdc"):
        db.create_escalation(
            state["mobile_hash"], "repeated_miss", "HIGH",
            f"3+ consecutive missed appointments — {state['mobile_hash']}",
            "Patient has missed 3+ consecutive appointments. Automated comms stopped.",
            "Hello, I am calling from your VYTAL care team. We noticed you have missed several appointments. "
            "We want to make sure you are getting the support you need. How can we help?"
        )

    return {
        "psych_profile":    profile_json,
        "psych_stage":      result.get("stage", state["psych_stage"]),
        "comm_style":       result.get("comm_style", state["comm_style"]),
        "barrier":          result.get("barrier", state["barrier"]),
        "fomo_sensitivity": result.get("fomo_sensitivity", state["fomo_sensitivity"]),
        "smart_send_time":  result.get("smart_send_time", state["smart_send_time"]),
        "distress_flag":    result.get("distress_flag", state["distress_flag"]),
        "frustration_stage": result.get("frustration_stage", state["frustration_stage"]),
        "escalate_to_human": result.get("escalate_to_sfdc", False),
    }
