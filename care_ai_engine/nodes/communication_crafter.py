"""Agent 5 — Communication Crafter: writes and sends all patient messages."""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from state import PatientState
from nodes.llm import call_claude
from prompts.system_prompts import COMMUNICATION_CRAFTER
from constants.programme_context import PROGRAMME_CONTEXT, BENEFIT_CAPS
import db
from datetime import datetime


# ── WhatsApp simulator (replace with real WATI/Gupshup API) ──────────────────
def _send_whatsapp(mobile_hash: str, message: str, quick_replies: list) -> bool:
    """Simulate sending a WhatsApp message. Swap for real API call."""
    print(f"\n[WHATSAPP] To: {mobile_hash[:10]}***")
    print(f"  Message: {message[:120]}...")
    print(f"  Quick replies: {quick_replies}")
    # TODO: replace with WATI / Gupshup API call
    # import requests
    # requests.post(WATI_URL, headers={"Authorization": f"Bearer {WATI_TOKEN}"},
    #               json={"phone": mobile_number, "message": message})
    return True


def _send_voice(mobile_hash: str, script: dict) -> bool:
    """Simulate triggering an Exotel voice call."""
    print(f"\n[VOICE BOT] To: {mobile_hash[:10]}***")
    print(f"  Script opening: {str(script)[:120]}...")
    # TODO: replace with Exotel API call
    return True


def _build_context(state: PatientState, message_type: str) -> str:
    prog   = PROGRAMME_CONTEXT["DIABETES"]
    caps   = BENEFIT_CAPS.get(state["cohort"], BENEFIT_CAPS["HIGH"])
    counts = db.get_consultation_counts(state["mobile_hash"])
    trend  = db.get_hba1c_trend(state["mobile_hash"])

    # Direction of HbA1c (no raw values)
    direction = "Stable"
    if len(trend) >= 2:
        delta = trend[-1]["value"] - trend[-2]["value"]
        direction = "Improving" if delta < 0 else "Worsening" if delta > 0 else "Stable"

    sched  = db.get_clinical_schedule(state["mobile_hash"])
    next_doc = next((s["scheduled_date"] for s in sched if s["appt_type"] == "DOCTOR"), "TBD")
    next_diet = next((s["scheduled_date"] for s in sched if s["appt_type"] == "DIETICIAN"), "TBD")

    return f"""
MESSAGE TYPE: {message_type}

PATIENT CONTEXT:
  cohort: {state['cohort']}
  programme: {state['programme']}
  policy_start_date: {state['policy_start_date']}
  points: {state['points']}
  level: {state['level']}
  device_type: {state['device_type']}

COMM PROFILE:
  comm_style: {state['comm_style']}
  barrier: {state['barrier']}
  fomo_sensitivity: {state['fomo_sensitivity']}
  psych_stage: {state['psych_stage']}

CLINICAL (direction only — do NOT mention raw values):
  sugar_levels_direction: {direction}
  hba1c_band: {state['hba1c_band']}
  next_doctor_date: {next_doc}
  next_dietician_date: {next_diet}

BENEFITS:
  doctor_remaining: {caps['doctor'] - counts['doctor_used']}
  dietician_remaining: {caps['dietician'] - counts['dietician_used']}
  device_type: {prog['devices'].get(state['cohort'], 'Glucometer')}
  device_eligible: {state['device_eligible']}
  device_allocated: {state['device_allocated']}

PROGRAMME:
  specialist: {prog['specialist']}
  user_language: {prog['user_language']}
  dietary_focus: {prog['dietary_focus']}
"""


_FALLBACK_MESSAGES = {
    "welcome": {
        "script": "Namaste! Welcome to your VYTAL Diabetes Management Programme by Bajaj Finserv Health. "
                  "Your programme is personalised to help you manage your sugar levels over the next 12 months. "
                  "Your first step: Book your diet consultation today — it is free for you! Reply YES and we will set it up.",
        "quick_replies": ["YES, book now", "Tell me more", "Later"],
        "channel": "WHATSAPP"
    },
    "meal_log": {
        "script": "Hi! You have not logged your meals today. Tracking your food helps your dietician understand "
                  "your sugar patterns better. Takes just 30 seconds — log now and earn 5 points!",
        "quick_replies": ["Log now", "Will do later", "Help"],
        "channel": "WHATSAPP"
    },
    "lab_test": {
        "script": "Your blood test is due this month! It helps your doctor track your sugar levels and plan the next steps. "
                  "Shall we book a convenient lab slot near you? Reply YES.",
        "quick_replies": ["YES, book", "This weekend", "Call me"],
        "channel": "WHATSAPP"
    },
    "step_goal": {
        "script": "Great day to move, [Name]! Can you hit 8,000 steps today? You are currently averaging 4,200 steps. "
                  "Even a 20-minute walk after dinner will get you there. Let us know when you hit the target!",
        "quick_replies": ["Done it!", "I will try", "Remind me at 6 PM"],
        "channel": "WHATSAPP"
    },
    "appointment": {
        "script": "Your consultation is scheduled soon! Please reply CONFIRM to keep the slot, "
                  "or RESCHEDULE if you need a different time. No travel needed — it is a video call.",
        "quick_replies": ["CONFIRM", "RESCHEDULE", "Cancel"],
        "channel": "WHATSAPP"
    },
    "progress": {
        "script": "Excellent work this month! Your sugar levels are moving in the right direction. "
                  "Keep up the great habits — consistency is what makes the difference. Keep going!",
        "quick_replies": ["Thank you!", "My score?", "Next steps"],
        "channel": "WHATSAPP"
    },
    "diet_checkin": {
        "script": "Quick check-in! How is your diet plan going this week? "
                  "Reply A if going well, B if mostly following, C if struggling a bit.",
        "quick_replies": ["A - Going well", "B - Mostly following", "C - Struggling"],
        "channel": "WHATSAPP"
    },
}


def communication_crafter_node(state: PatientState) -> dict:
    msg_info    = state.get("current_message") or {}
    message_type = msg_info.get("type") or "meal_log"

    # Determine channel from consecutive no-response escalation
    tier    = 1
    channel = "WHATSAPP"
    if state["consecutive_no_resp"] >= 2 and state["last_nudge_channel"] == "WHATSAPP":
        channel, tier = "VOICE_BOT", 3
    elif state["consecutive_no_resp"] >= 1:
        channel, tier = "APP_NUDGE", 2

    # Generate message via Claude
    context = _build_context(state, message_type)
    result  = call_claude(COMMUNICATION_CRAFTER, context, max_tokens=768)

    if result:
        script        = result.get("script", "")
        quick_replies = result.get("quick_replies", [])
        out_channel   = result.get("channel", channel)
    else:
        fallback      = _FALLBACK_MESSAGES.get(message_type, _FALLBACK_MESSAGES["meal_log"])
        script        = fallback["script"]
        quick_replies = fallback["quick_replies"]
        out_channel   = channel

    # Validate: no raw biomarker numbers in the message
    dangerous = ["7.5", "7.8", "8.2", "6.5", "HbA1c", "%"]
    for d in dangerous:
        if d in script:
            script = script.replace(d, "your sugar level reading")
            print(f"[CommCrafter] GUARDRAIL: removed '{d}' from message")

    # Log nudge event
    nudge_id = db.log_nudge(
        state["mobile_hash"], out_channel, tier,
        msg_info.get("reasoning", "daily_schedule"),
        f"{state['comm_style'].lower()}_v1",
        script, quick_replies
    )

    # Send via appropriate channel
    if out_channel == "WHATSAPP":
        _send_whatsapp(state["mobile_hash"], script, quick_replies)
    elif out_channel == "VOICE_BOT":
        _send_voice(state["mobile_hash"], result or {})

    # Mark as sent
    db.mark_nudge_sent(nudge_id)

    # Update patient state
    db.update_patient(state["mobile_hash"], {
        "last_nudge_channel":  out_channel,
        "last_nudge_at":       datetime.now().isoformat(),
        "last_nudge_responded": 0,
        "consecutive_no_resp": state["consecutive_no_resp"] + 1,
    })

    return {
        "current_message": {
            "type": message_type, "channel": out_channel,
            "script": script, "quick_replies": quick_replies,
            "nudge_id": nudge_id
        },
        "last_nudge_channel":  out_channel,
        "last_nudge_responded": False,
        "consecutive_no_resp": state["consecutive_no_resp"] + 1,
    }
