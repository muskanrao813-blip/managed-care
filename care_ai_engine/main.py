"""
Main entry point for AI Care Coordinator engine.
Starts: Orchestrator scheduler + FastAPI webhook server.
"""

import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request, HTTPException
from datetime import datetime, timedelta
import json
import db
from graph import run_patient_care
from tools.trino_client import get_all_vytal_diabetes_patients

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER — Daily orchestrator run for all patients
# ─────────────────────────────────────────────────────────────────────────────

scheduler = BackgroundScheduler()


def daily_orchestrator_job():
    """Run orchestrator for all VYTAL patients daily at 09:00 AM."""
    print(f"\n[SCHEDULER] Daily orchestrator run at {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    try:
        # Get all enrolled patients
        patients = db.get_all_patients()
        if not patients:
            print("  [INFO] No patients found")
            return

        print(f"  Processing {len(patients)} patients...")
        for patient in patients:
            mobile_hash = patient["mobile_hash"]
            try:
                result = run_patient_care(mobile_hash, trigger="daily_schedule")
                print(f"    OK: {mobile_hash[:10]}*** | Action: {result.get('current_action', 'end')}")
            except Exception as e:
                print(f"    ERR: {mobile_hash[:10]}*** | {str(e)[:80]}")

    except Exception as e:
        print(f"  [ERROR] Daily orchestrator job failed: {e}")


def weekly_psychology_job():
    """Update psychology profiles weekly (Tuesday 10 AM)."""
    print(f"\n[SCHEDULER] Weekly psychology refresh at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    patients = db.get_all_patients()
    for patient in patients:
        try:
            run_patient_care(patient["mobile_hash"], trigger="weekly_psych")
        except Exception as e:
            print(f"  ERR: {patient['mobile_hash'][:10]}*** | {e}")


def monthly_progress_job():
    """Generate monthly reports (1st of month at 08:00 AM)."""
    print(f"\n[SCHEDULER] Monthly progress reports at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    patients = db.get_all_patients()
    for patient in patients:
        try:
            run_patient_care(patient["mobile_hash"], trigger="monthly_progress")
        except Exception as e:
            print(f"  ERR: {patient['mobile_hash'][:10]}*** | {e}")


def init_scheduler():
    """Initialize background scheduler."""
    if not scheduler.running:
        # Daily orchestrator at 09:00 AM
        scheduler.add_job(daily_orchestrator_job, "cron", hour=9, minute=0,
                         id="daily_orchestrator", replace_existing=True)

        # Weekly psychology on Tuesday at 10:00 AM
        scheduler.add_job(weekly_psychology_job, "cron", day_of_week=1, hour=10, minute=0,
                         id="weekly_psychology", replace_existing=True)

        # Monthly progress on 1st of month at 08:00 AM
        scheduler.add_job(monthly_progress_job, "cron", day=1, hour=8, minute=0,
                         id="monthly_progress", replace_existing=True)

        scheduler.start()
        print("[SCHEDULER] Initialized with 3 jobs")


# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI — Webhook server for WhatsApp / voice replies
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="VYTAL AI Care Coordinator")


@app.on_event("startup")
async def startup():
    """Initialize DB and scheduler on app start."""
    db.init_db()
    db.seed_test_patient()
    init_scheduler()
    print("[APP] Started at", datetime.now())


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request):
    """
    Incoming WhatsApp message via WATI / Gupshup webhook.
    Expected JSON:
      {
        "mobile_hash": "xxx",
        "message_type": "text|quick_reply",
        "text": "user's reply",
        "timestamp": "YYYY-MM-DD HH:MM:SS"
      }
    """
    try:
        payload = await request.json()
        mobile_hash  = payload.get("mobile_hash")
        message_type = payload.get("message_type", "text")
        text         = payload.get("text", "").strip()

        if not mobile_hash:
            raise HTTPException(status_code=400, detail="mobile_hash required")

        print(f"[WEBHOOK] WhatsApp from {mobile_hash[:10]}***: {text[:50]}...")

        # Determine trigger from message content
        trigger = "wa_reply"
        trigger_data = {"reply": text, "message_type": message_type}

        # Special case: diet check-in responses (A/B/C)
        if text.upper() in ("A", "B", "C"):
            trigger = "diet_checkin"

        # Run through graph
        result = run_patient_care(mobile_hash, trigger=trigger, trigger_data=trigger_data)

        # Mark nudge as responded
        db.mark_nudge_responded(mobile_hash, text)

        return {
            "status": "success",
            "action": result.get("current_action"),
            "message": f"Reply logged. Thank you!"
        }

    except Exception as e:
        print(f"[WEBHOOK ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhooks/voice")
async def voice_webhook(request: Request):
    """
    Incoming voice bot completion webhook via Exotel.
    Expected JSON:
      {
        "mobile_hash": "xxx",
        "call_duration": 120,
        "dtmf_input": "1",  (optional)
        "transcript": "user said yes"
      }
    """
    try:
        payload = await request.json()
        mobile_hash = payload.get("mobile_hash")
        dtmf        = payload.get("dtmf_input")
        transcript  = payload.get("transcript", "")

        if not mobile_hash:
            raise HTTPException(status_code=400, detail="mobile_hash required")

        print(f"[WEBHOOK] Voice from {mobile_hash[:10]}***: DTMF={dtmf}, Transcript={transcript[:50]}...")

        trigger_data = {
            "response_type": "dtmf" if dtmf else "transcript",
            "dtmf": dtmf,
            "transcript": transcript
        }

        result = run_patient_care(mobile_hash, trigger="voice_reply", trigger_data=trigger_data)
        db.mark_nudge_responded(mobile_hash, transcript or dtmf or "voice_response")

        return {
            "status": "success",
            "action": result.get("current_action")
        }

    except Exception as e:
        print(f"[WEBHOOK ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhooks/lab_result")
async def lab_result_webhook(request: Request):
    """
    Incoming lab result via Redcliffe / lab provider webhook.
    Triggers health profiler run.
    """
    try:
        payload = await request.json()
        mobile_hash = payload.get("mobile_hash")
        lab_data    = payload.get("lab_data", {})

        if not mobile_hash:
            raise HTTPException(status_code=400, detail="mobile_hash required")

        print(f"[WEBHOOK] Lab result from {mobile_hash[:10]}***: {lab_data}")

        result = run_patient_care(mobile_hash, trigger="lab_received", trigger_data=lab_data)

        return {
            "status": "success",
            "action": result.get("current_action")
        }

    except Exception as e:
        print(f"[WEBHOOK ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/patients")
async def get_patients():
    """List all patients (for dashboard)."""
    patients = db.get_all_patients()
    return {
        "total": len(patients),
        "patients": patients
    }


@app.get("/patient/{mobile_hash}")
async def get_patient(mobile_hash: str):
    """Get patient details and state."""
    patient = db.get_patient(mobile_hash)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    sched = db.get_clinical_schedule(mobile_hash)
    counts = db.get_consultation_counts(mobile_hash)
    eng = db.get_engagement_signals(mobile_hash, days=7)

    return {
        "patient": patient,
        "schedule": sched,
        "consultations": counts,
        "engagement": eng
    }


@app.get("/escalations")
async def get_escalations():
    """Get open escalations (for SG Agent queue)."""
    escalations = db.get_escalation_queue()
    return {
        "total": len(escalations),
        "escalations": escalations
    }


@app.post("/admin/enroll")
async def admin_enroll(request: Request):
    """
    Admin endpoint to enrol a new patient.
    POST JSON:
      {
        "mobile_hash": "...",
        "phr_id": "...",
        "product_code": "VYTAL0126",
        "cohort": "VERY_HIGH",
        "gender": "M"
      }
    """
    try:
        payload = await request.json()
        mobile_hash = payload.get("mobile_hash")
        if not mobile_hash:
            raise HTTPException(status_code=400, detail="mobile_hash required")

        # Check if already exists
        existing = db.get_patient(mobile_hash)
        if existing:
            raise HTTPException(status_code=409, detail="Patient already enrolled")

        # Create patient record
        from state import default_state
        new_patient = default_state(
            mobile_hash,
            payload.get("cohort", "HIGH"),
            payload.get("product_code", "VYTAL0126")
        )
        new_patient.update({
            "phr_id": payload.get("phr_id"),
            "gender": payload.get("gender"),
            "policy_start_date": datetime.now().strftime("%Y-%m-%d"),
        })

        c = db.conn()
        c.execute("""
            INSERT INTO patients (
                mobile_hash, phr_id, product_code, cohort, programme,
                policy_start_date, gender
            ) VALUES (?,?,?,?,?,?,?)
        """, (mobile_hash, new_patient.get("phr_id"), new_patient.get("product_code"),
              new_patient.get("cohort"), "DIABETES",
              new_patient.get("policy_start_date"), new_patient.get("gender")))
        c.commit()
        c.close()

        # Run onboarding flow
        result = run_patient_care(mobile_hash, trigger="enrollment")

        return {
            "status": "enrolled",
            "mobile_hash": mobile_hash,
            "action": result.get("current_action")
        }

    except Exception as e:
        print(f"[ADMIN ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    print(f"[MAIN] Starting VYTAL AI Care Coordinator on port {port}...")
    print(f"  Database: {db.DB_PATH}")
    print(f"  Scheduler: 3 jobs configured")
    print(f"  Endpoints:")
    print(f"    POST /webhooks/whatsapp")
    print(f"    POST /webhooks/voice")
    print(f"    POST /webhooks/lab_result")
    print(f"    GET  /health")
    print(f"    GET  /patients")
    print(f"    GET  /patient/{{mobile_hash}}")
    print(f"    GET  /escalations")
    print(f"    POST /admin/enroll")

    uvicorn.run(app, host="0.0.0.0", port=port)
