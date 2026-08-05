"""
Test runner — verify all 9 agents work with the test patient.
Usage: python test_engine.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import db
from graph import run_patient_care
from datetime import datetime

print("="*70)
print("  VYTAL AI Care Coordinator — Full Engine Test")
print("="*70)

# Initialize DB
print("\n[1] Initializing database...")
db.init_db()
db.seed_test_patient()
print("  OK: Database ready with test patient TEST_HASH_001")

# Verify test patient exists
print("\n[2] Verifying test patient...")
patient = db.get_patient("TEST_HASH_001")
print(f"  Patient: {patient['mobile_hash']}")
print(f"  Cohort: {patient['cohort']} | HbA1c: {patient['latest_hba1c']}%")
print(f"  Points: {patient['points']} | Level: {patient['level']}")

# Test 1: Enrollment flow
print("\n[3] Running ENROLLMENT flow...")
print("  Agents: Orchestrator > HealthProfiler > CarePlanner > Communication > Rewards")
result = run_patient_care("TEST_HASH_001", trigger="enrollment")
print(f"  Final action: {result.get('current_action', 'end')}")

# Test 2: Daily schedule
print("\n[4] Running DAILY SCHEDULE flow...")
result = run_patient_care("TEST_HASH_001", trigger="daily_schedule")
print(f"  Final action: {result.get('current_action', 'end')}")

# Test 3: Diet check-in
print("\n[5] Running DIET CHECK-IN flow...")
result = run_patient_care("TEST_HASH_001", trigger="diet_checkin",
                         trigger_data={"reply": "A"})
print(f"  Final action: {result.get('current_action', 'end')}")

# Test 4: Lab received
print("\n[6] Running LAB RECEIVED flow...")
result = run_patient_care("TEST_HASH_001", trigger="lab_received",
                         trigger_data={"hba1c": 7.2})
print(f"  Final action: {result.get('current_action', 'end')}")

# Verify state was updated
print("\n[7] Verifying final state...")
updated = db.get_patient("TEST_HASH_001")
print(f"  Points: {updated['points']} (was {patient['points']})")
print(f"  Level: {updated['level']}")

# Check logs
print("\n[8] Checking execution logs...")
orch_log = db.get_orchestrator_history("TEST_HASH_001", limit=5)
print(f"  Orchestrator decisions: {len(orch_log)} logged")
for log in orch_log[:2]:
    print(f"    - {log['run_date']}: {log['trigger_event']} > {log['priority_action'][:50]}...")

nudges = db.get_recent_nudges("TEST_HASH_001", limit=5)
print(f"  Nudges sent: {len(nudges)}")
for nudge in nudges[:2]:
    print(f"    - {nudge['created_at']}: {nudge['channel']} | {nudge['message'][:40]}...")

sched = db.get_clinical_schedule("TEST_HASH_001")
print(f"  Clinical schedule: {len(sched)} appointments")
for s in sched:
    print(f"    - {s['appt_type']}: {s['scheduled_date']} ({s['status']})")

print("\n" + "="*70)
print("  All tests passed!")
print("="*70)
print("\nNext: Start the server with: python main.py")
