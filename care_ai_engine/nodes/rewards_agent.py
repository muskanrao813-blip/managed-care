"""Agent 9 — Rewards Agent: device eligibility, FOMO nudges, points, levels."""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from state import PatientState
from nodes.llm import call_claude
from prompts.system_prompts import REWARDS_AGENT
from constants.programme_context import DEVICE_CAPS, FOMO_THRESHOLD, PROGRAMME_CONTEXT
import db
from datetime import datetime


def _get_slots_remaining(device_type: str) -> int:
    """Get actual remaining slots from DB."""
    cap = DEVICE_CAPS.get(device_type, 100)
    c = db.conn()
    allocated = c.execute("""
        SELECT COUNT(*) as cnt FROM reward_allocations
        WHERE reward_type=? AND allocated=1
    """, (device_type,)).fetchone()["cnt"]
    c.close()
    return cap - allocated


def rewards_agent_node(state: PatientState) -> dict:
    prog = PROGRAMME_CONTEXT["DIABETES"]
    device_type = prog["devices"].get(state["cohort"], "Glucometer")

    # Check device eligibility
    counts = db.get_consultation_counts(state["mobile_hash"])
    first_doctor_done = counts["doctor_used"] >= 1
    slots_remaining   = _get_slots_remaining(device_type)
    fomo_threshold    = int(DEVICE_CAPS.get(device_type, 100) * FOMO_THRESHOLD)
    is_fomo_trigger   = slots_remaining <= fomo_threshold

    # Check lifestyle assessment eligibility
    lifestyle_eligible = None
    trend = db.get_hba1c_trend(state["mobile_hash"])
    latest_hba1c = trend[-1]["value"] if trend else None
    if (state.get("is_overweight") and latest_hba1c and latest_hba1c >= 5.7
            and state.get("stress_high")):
        lifestyle_eligible = "Metabolic"
    elif state.get("alcohol_risk"):
        lifestyle_eligible = "Alcohol"
    elif state.get("stress_high"):
        lifestyle_eligible = "Stress"

    context = f"""
PATIENT:
  cohort: {state['cohort']}
  device_type: {device_type}
  device_eligible: {state['device_eligible']}
  device_allocated: {state['device_allocated']}
  first_doctor_done: {first_doctor_done}
  points: {state['points']}
  level: {state['level']}

INVENTORY:
  slots_remaining: {slots_remaining}
  total_cap: {DEVICE_CAPS.get(device_type, 100)}
  fomo_threshold: {fomo_threshold}
  is_fomo_trigger: {is_fomo_trigger}
  fomo_sensitivity: {state['fomo_sensitivity']}

LIFESTYLE ELIGIBILITY: {lifestyle_eligible or 'None'}

HRA FLAGS:
  is_overweight: {state.get('is_overweight', False)}
  stress_high: {state.get('stress_high', False)}
  alcohol_risk: {state.get('alcohol_risk', False)}
"""
    result = call_claude(REWARDS_AGENT, context, max_tokens=384)

    if not result:
        action = "none"
        if state["device_eligible"] and first_doctor_done and not state["device_allocated"]:
            action = "allocate_device" if slots_remaining > 0 else "send_fomo"
        elif is_fomo_trigger and not state["device_allocated"]:
            action = "send_fomo"

        result = {
            "action": action,
            "device_type": device_type,
            "device_eligible": state["device_eligible"] or first_doctor_done,
            "fomo_message": (
                f"Your VYTAL programme includes a FREE {device_type}! "
                f"Only {slots_remaining} slots left this month — "
                f"complete your first doctor consultation to claim yours."
            ) if action == "send_fomo" else None,
            "slots_remaining": slots_remaining,
            "points_to_award": 0,
            "new_level": None,
            "lifestyle_assessment_eligible": lifestyle_eligible,
        }

    action = result.get("action", "none")

    # Execute action
    if action == "allocate_device" and not state["device_allocated"]:
        c = db.conn()
        c.execute("""
            UPDATE reward_allocations SET allocated=1, allocation_date=?, status='allocated'
            WHERE mobile_hash=? AND reward_type=?
        """, (datetime.now().strftime("%Y-%m-%d"), state["mobile_hash"], device_type))
        if c.execute("SELECT changes()").fetchone()[0] == 0:
            c.execute("""
                INSERT INTO reward_allocations (mobile_hash, reward_type, eligibility_date, allocated, allocation_date, status)
                VALUES (?,?,?,1,?,?)
            """, (state["mobile_hash"], device_type,
                  datetime.now().strftime("%Y-%m-%d"),
                  datetime.now().strftime("%Y-%m-%d"), "allocated"))
        c.commit()
        c.close()
        db.update_patient(state["mobile_hash"], {"device_allocated": 1})

        # Notify patient
        from nodes.communication_crafter import _send_whatsapp
        _send_whatsapp(
            state["mobile_hash"],
            f"Congratulations! Your FREE {device_type} has been reserved for you. "
            f"Our team will contact you within 3 working days for delivery. "
            f"You have also earned 50 bonus points!",
            ["Thank you!", "Delivery details", "How to use"]
        )
        db.add_points(state["mobile_hash"], 50)

    elif action == "send_fomo" and result.get("fomo_message"):
        from nodes.communication_crafter import _send_whatsapp
        _send_whatsapp(state["mobile_hash"], result["fomo_message"],
                       ["Claim my device", "Tell me more", "Later"])
        db.log_nudge(
            state["mobile_hash"], "WHATSAPP", 1, "fomo_device",
            "fomo_v1", result["fomo_message"], ["Claim my device", "Tell me more", "Later"]
        )

    # Award points if any
    if result.get("points_to_award", 0) > 0:
        db.add_points(state["mobile_hash"], result["points_to_award"])

    # Update device eligibility
    updates = {}
    if result.get("device_eligible") != state["device_eligible"]:
        updates["device_eligible"] = 1 if result.get("device_eligible") else 0
    if updates:
        db.update_patient(state["mobile_hash"], updates)

    return {
        "device_eligible":  result.get("device_eligible", state["device_eligible"]),
        "device_allocated": action == "allocate_device" or state["device_allocated"],
        "points": state["points"] + result.get("points_to_award", 0),
    }
