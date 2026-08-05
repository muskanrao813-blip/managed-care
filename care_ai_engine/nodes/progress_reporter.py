"""Agent 8 — Progress Reporter: monthly adherence score + progress message."""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from state import PatientState
from nodes.llm import call_claude
from prompts.system_prompts import PROGRESS_REPORTER
import db
from datetime import datetime


def _compute_scores(state: PatientState) -> dict:
    """Rule-based adherence score computation."""
    # Clinical score (0-30): based on HbA1c band
    band_scores = {"Normal": 30, "Moderate": 25, "High": 20, "Very High": 10}
    clinical = band_scores.get(state.get("hba1c_band", "High"), 20)

    # Engagement score (0-25): consultations attended
    counts = db.get_consultation_counts(state["mobile_hash"])
    total_consults = counts["doctor_used"] + counts["dietician_used"]
    engagement = 25 if total_consults >= 3 else 12 if total_consults >= 1 else 0

    # Intent score (0-25): log adherence
    eng = db.get_engagement_signals(state["mobile_hash"], days=30)
    meal_rate  = eng["meal_logs"] / 30
    step_rate  = eng["step_logs"] / 30
    intent = min(25, int(meal_rate * 14 + step_rate * 8 + eng["mood_logs"] * 3))

    # Lifestyle score (0-20): penalty-based
    lifestyle = 20
    if state.get("is_smoker"):    lifestyle -= 10
    if state.get("alcohol_risk"): lifestyle -= 5
    if state.get("stress_high"):  lifestyle -= 3
    if state.get("poor_sleep"):   lifestyle -= 2
    lifestyle = max(0, lifestyle)

    total = clinical * 0.30 + engagement * 0.25 + intent * 0.25 + lifestyle * 0.20
    total = round(min(100, total), 1)

    band = ("High" if total > 75 else "Moderate" if total >= 50
            else "Low" if total >= 30 else "Very Low")

    # HbA1c direction
    trend = db.get_hba1c_trend(state["mobile_hash"])
    direction = "Stable"
    if len(trend) >= 2:
        delta = trend[-1]["value"] - trend[-2]["value"]
        direction = "Improving" if delta < 0 else "Worsening" if delta > 0 else "Stable"

    return {
        "clinical_score":    clinical,
        "engagement_score":  engagement,
        "intent_score":      intent,
        "lifestyle_score":   lifestyle,
        "total_score":       total,
        "score_band":        band,
        "delta_from_last":   None,
        "clinical_direction": direction,
    }


def progress_reporter_node(state: PatientState) -> dict:
    score_month = datetime.now().strftime("%Y-%m")

    # Check if already generated this month
    c = db.conn()
    existing = c.execute("""
        SELECT id FROM adherence_scores
        WHERE mobile_hash=? AND score_month=?
    """, (state["mobile_hash"], score_month)).fetchone()
    c.close()

    if existing:
        print(f"[ProgressReporter] Score already generated for {score_month}")
        return {}

    # Compute scores
    scores = _compute_scores(state)

    # Build context for Claude-generated narrative
    counts = db.get_consultation_counts(state["mobile_hash"])
    context = f"""
PATIENT:
  cohort: {state['cohort']}
  motivation_type: {state['motivation_type']}
  comm_style: {state['comm_style']}
  points: {state['points']}
  level: {state['level']}

MONTHLY SCORES:
  clinical_score: {scores['clinical_score']} / 30
  engagement_score: {scores['engagement_score']} / 25
  intent_score: {scores['intent_score']} / 25
  lifestyle_score: {scores['lifestyle_score']} / 20
  total_score: {scores['total_score']} / 100
  score_band: {scores['score_band']}

CLINICAL:
  sugar_levels_direction: {scores['clinical_direction']}  (NEVER mention raw values)
  hba1c_band: {state.get('hba1c_band', 'Unknown')}
  doctor_consultations: {counts['doctor_used']} of {state['doctor_max']}
  dietician_consultations: {counts['dietician_used']} of {state['dietician_max']}
  hra_completed: {state.get('hra_completed', False)}
"""
    result = call_claude(PROGRESS_REPORTER, context, max_tokens=512)

    if not result:
        emoji_band = {"High": "Excellent", "Moderate": "Good", "Low": "Building", "Very Low": "Starting"}
        direction_msg = {
            "Improving": "Your sugar levels are moving in the right direction!",
            "Stable":    "Your sugar levels are stable — keep maintaining your routine.",
            "Worsening": "Your sugar levels need some attention — your doctor will guide you."
        }
        whatsapp_report = (
            f"Your VYTAL Monthly Health Summary:\n"
            f"Sugar levels: {scores['clinical_direction']}\n"
            f"Consultations this year: Doctor {counts['doctor_used']}/{state['doctor_max']}\n"
            f"Adherence score: {scores['total_score']}/100 ({scores['score_band']})\n"
            f"{direction_msg.get(scores['clinical_direction'], '')}\n"
            f"Next focus: Complete your diet consultation if not done yet."
        )
        result = {**scores, "whatsapp_report": whatsapp_report,
                  "next_focus": "Book diet consultation and log meals daily"}

    # Save score to DB
    c = db.conn()
    c.execute("""
        INSERT INTO adherence_scores
        (mobile_hash, score_month, clinical_score, engagement_score,
         intent_score, lifestyle_score, total_score, score_band)
        VALUES (?,?,?,?,?,?,?,?)
    """, (state["mobile_hash"], score_month,
          result.get("clinical_score",   scores["clinical_score"]),
          result.get("engagement_score", scores["engagement_score"]),
          result.get("intent_score",     scores["intent_score"]),
          result.get("lifestyle_score",  scores["lifestyle_score"]),
          result.get("total_score",      scores["total_score"]),
          result.get("score_band",       scores["score_band"])))
    c.commit()
    c.close()

    # Send WhatsApp progress report
    from nodes.communication_crafter import _send_whatsapp
    _send_whatsapp(
        state["mobile_hash"],
        result.get("whatsapp_report", ""),
        ["View full report", "My score breakdown", "Next steps"]
    )

    nudge_id = db.log_nudge(
        state["mobile_hash"], "WHATSAPP", 1, "monthly_progress",
        "progress_report_v1", result.get("whatsapp_report", ""),
        ["View full report", "My score breakdown", "Next steps"]
    )
    db.mark_nudge_sent(nudge_id)

    return {
        "current_message": {
            "type":   "monthly_report",
            "score":  result.get("total_score", scores["total_score"]),
            "band":   result.get("score_band",  scores["score_band"]),
            "report": result.get("whatsapp_report", "")
        }
    }
