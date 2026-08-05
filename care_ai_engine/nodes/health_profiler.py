"""Agent 2 — Health Profiler: classifies biomarkers, sets clinical_review_needed."""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from state import PatientState
from nodes.llm import call_claude
from prompts.system_prompts import HEALTH_PROFILER
from constants.programme_context import classify_hba1c, PROGRAMME_CONTEXT
import db


def _build_context(state: PatientState, labs: list, hra: dict) -> str:
    trend = db.get_hba1c_trend(state["mobile_hash"])
    return f"""
PATIENT: cohort={state['cohort']}, programme={state['programme']}

HBA1C TREND (oldest to newest):
{json.dumps(trend, indent=2)}

CURRENT LABS (latest values):
{json.dumps(labs[:10], indent=2)}

HRA LIFESTYLE DATA:
{json.dumps(hra, indent=2)}

PREVIOUS HEALTH PROFILE:
{state.get('health_profile') or 'None — first profiling run'}
"""


def _fallback(state: PatientState, labs: list) -> dict:
    """Rule-based profiling when Claude unavailable."""
    hba1c = state.get("latest_hba1c")
    band  = classify_hba1c(hba1c) if hba1c else "Unknown"
    trend = db.get_hba1c_trend(state["mobile_hash"])
    delta = None
    if len(trend) >= 2:
        delta = round(trend[-1]["value"] - trend[-2]["value"], 2)

    prog = PROGRAMME_CONTEXT["DIABETES"]
    device_eligible = False
    device_type = None
    if hba1c:
        if hba1c > 8 and state["cohort"] == "VERY_HIGH":
            device_type, device_eligible = "CGM", True
        elif hba1c >= 6.5:
            device_type, device_eligible = "Glucometer", True

    return {
        "hba1c_band":             band,
        "hba1c_delta":            delta,
        "clinical_review_needed": bool(delta and abs(delta) >= 1.0),
        "device_eligible":        device_eligible,
        "device_type":            device_type,
        "lifestyle_flags": {
            "smoking_risk": False, "alcohol_risk": False,
            "stress_high":  False, "poor_sleep":   False, "overweight": False
        },
        "health_summary":   f"HbA1c {hba1c}% ({band} band). Delta: {delta}.",
        "recommended_next": "doctor_consultation" if (delta and delta >= 1.0) else "monitor"
    }


def health_profiler_node(state: PatientState) -> dict:
    # Pull latest lab data from Trino if mobile_hash is real (not test)
    labs, hra = [], {}
    if not state["mobile_hash"].startswith("TEST"):
        try:
            from tools.trino_client import get_lab_results, get_hra
            lab_result = get_lab_results(state["mobile_hash"])
            labs = lab_result.get("lab_results", [])
            latest_hba1c = lab_result.get("latest_hba1c")
            hba1c_trend  = lab_result.get("hba1c_trend", [])

            # Sync new lab results to local DB
            for lr in labs:
                if lr.get("value") and lr.get("loinc_id"):
                    db.log_lab_result(
                        state["mobile_hash"], state.get("phr_id", ""),
                        str(lr.get("test_date", ""))[:10],
                        lr["loinc_id"], lr.get("test_name", ""),
                        float(lr["value"]), lr.get("units", "")
                    )
            if latest_hba1c:
                db.update_patient(state["mobile_hash"], {"latest_hba1c": latest_hba1c})

            if state.get("phr_id"):
                hra = get_hra(state["phr_id"])
        except Exception as e:
            print(f"[HealthProfiler] Trino fetch failed: {e}")
    else:
        # Test patient — use data from local DB
        labs = db.get_hba1c_trend(state["mobile_hash"])
        latest_hba1c = state.get("latest_hba1c")

    context = _build_context(state, labs, hra)
    result  = call_claude(HEALTH_PROFILER, context, max_tokens=512) or _fallback(state, labs)

    # Persist health profile to DB
    profile_json = json.dumps(result)
    updates = {
        "health_profile":         profile_json,
        "hba1c_band":             result.get("hba1c_band"),
        "hba1c_delta":            result.get("hba1c_delta"),
        "clinical_review_needed": 1 if result.get("clinical_review_needed") else 0,
        "device_eligible":        1 if result.get("device_eligible") else 0,
        "device_type":            result.get("device_type"),
    }
    db.update_patient(state["mobile_hash"], updates)

    return {
        "health_profile":         profile_json,
        "hba1c_band":             result.get("hba1c_band"),
        "hba1c_delta":            result.get("hba1c_delta"),
        "clinical_review_needed": result.get("clinical_review_needed", False),
        "device_eligible":        result.get("device_eligible", False),
        "device_type":            result.get("device_type"),
    }
