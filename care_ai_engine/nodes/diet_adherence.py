"""Agent 6 — Diet Adherence: evaluates diet check-in replies, tracks compliance."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from state import PatientState
from nodes.llm import call_claude
from prompts.system_prompts import DIET_ADHERENCE
import db
from datetime import datetime


def diet_adherence_node(state: PatientState) -> dict:
    trigger_data = state.get("trigger_data") or {}
    reply        = trigger_data.get("reply", "B").strip().upper()

    # Map common response variants
    if reply in ("A", "A - GOING WELL", "GOING WELL", "GOOD", "GREAT"):
        checkin_response = "A"
    elif reply in ("B", "B - MOSTLY FOLLOWING", "MOSTLY", "OK"):
        checkin_response = "B"
    else:
        checkin_response = "C"

    # Get last 3 responses from DB
    c = db.conn()
    rows = c.execute("""
        SELECT value FROM user_logs
        WHERE mobile_hash=? AND log_type='diet_checkin'
        ORDER BY created_at DESC LIMIT 3
    """, (state["mobile_hash"],)).fetchall()
    c.close()

    import json
    recent_responses = [json.loads(r["value"]).get("response", "B") for r in rows]
    consecutive_c    = sum(1 for r in recent_responses if r == "C")

    context = f"""
PATIENT CHECKIN RESPONSE: {checkin_response}

RECENT RESPONSES (last 3 weeks): {recent_responses}
CONSECUTIVE 'STRUGGLING' RESPONSES: {consecutive_c}

PATIENT PROFILE:
  cohort: {state['cohort']}
  psych_stage: {state['psych_stage']}
  comm_style: {state['comm_style']}
  barrier: {state['barrier']}

PROGRAMME DIETARY FOCUS:
  Low GI, 5 small meals, reduce refined carbs (rice, maida, sugar), increase fibre
  High-risk foods: white rice, fruit juice, sweets, cold drinks, maida products
"""
    result = call_claude(DIET_ADHERENCE, context, max_tokens=384)

    if not result:
        # Fallback by response
        if checkin_response == "A":
            result = {
                "compliance_flag": "good", "deviation_detected": False,
                "high_risk_deviation": False,
                "response_message": "Bahut achha Rajesh ji! You are doing great with your diet. Keep it up — consistency is what drives your sugar levels down!",
                "substitute_suggestion": None,
                "dietician_followup_needed": False, "points_to_award": 10
            }
        elif checkin_response == "B":
            result = {
                "compliance_flag": "moderate", "deviation_detected": True,
                "high_risk_deviation": False,
                "response_message": "Good effort! Even mostly following your diet plan is progress. One small tip: try replacing white rice with ragi or cauliflower rice — same satisfaction, much better for your sugar levels.",
                "substitute_suggestion": "Replace white rice with ragi roti",
                "dietician_followup_needed": False, "points_to_award": 5
            }
        else:
            result = {
                "compliance_flag": "poor", "deviation_detected": True,
                "high_risk_deviation": True,
                "response_message": "No worries — everyone has tough weeks. The most important thing is you logged it! One small change this week: try having 5 small meals instead of 3 large ones. Your dietician will help you plan this in your next session.",
                "substitute_suggestion": "5 small meals instead of 3 large ones",
                "dietician_followup_needed": consecutive_c >= 2, "points_to_award": 2
            }

    # Log the check-in
    db.log_user_activity(
        state["mobile_hash"], "diet_checkin",
        {"response": checkin_response, "compliance": result.get("compliance_flag")},
        datetime.now().strftime("%Y-%m-%d")
    )

    # Award points
    pts = result.get("points_to_award", 5)
    if pts > 0:
        db.add_points(state["mobile_hash"], pts)

    # Schedule dietician follow-up if needed
    if result.get("dietician_followup_needed"):
        sched = db.get_clinical_schedule(state["mobile_hash"])
        has_diet = any(s["appt_type"] == "DIETICIAN" and s["status"] == "PENDING" for s in sched)
        if not has_diet:
            from datetime import timedelta
            follow_up = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            c = db.conn()
            c.execute("""
                INSERT INTO clinical_schedule (mobile_hash, appt_type, scheduled_date, status, source)
                VALUES (?,?,?,?,?)
            """, (state["mobile_hash"], "DIETICIAN", follow_up, "PENDING", "diet_adherence_trigger"))
            c.commit()
            c.close()

    # Send response back to patient
    from nodes.communication_crafter import _send_whatsapp
    _send_whatsapp(state["mobile_hash"], result["response_message"],
                   ["Thank you!", "Book dietician", "More tips"])

    nudge_id = db.log_nudge(
        state["mobile_hash"], "WHATSAPP", 1, "diet_checkin_response",
        "diet_adherence_v1", result["response_message"],
        ["Thank you!", "Book dietician", "More tips"]
    )
    db.mark_nudge_sent(nudge_id)

    return {
        "points":          state["points"] + pts,
        "current_message": {"type": "diet_response", "script": result["response_message"]},
    }
