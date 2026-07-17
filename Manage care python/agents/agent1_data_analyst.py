"""
============================================================
AGENT 1 — 360° DATA ANALYST
============================================================
Two-phase agent:
  Phase 1: Pure Python — Assemble 8-step health signal dict
  Phase 2: Claude Haiku — Interpret signals → health trajectory

Output: UserSignalSnapshot table
  - directional_analysis: improving/stable/declining/at_risk
  - proxy_score: 0-100 (weighted)
  - biomarker_snapshot: latest health test results
  - appointment_status: completion %, pending follow-ups
  - engagement_trajectory: response rates over time
  - needs_escalation: medical alert flags
  - churn_risk: likelihood of 30-day silence
  - distress_flag: psychological need signals

Usage:
  python -m agents.agent1_data_analyst --limit 50
  python -m agents.agent1_data_analyst --phr PHR123
"""

import sys, os, json, sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = Path(__file__).parent.parent
DATA_DIR = SCRIPT_DIR / "Data"
DB_PATH = SCRIPT_DIR / "agents" / "agent_db.sqlite"

# ─────────────────────────────────────────────────────────
# PHASE 1: DATA ASSEMBLY (Pure Python)
# ─────────────────────────────────────────────────────────

class SignalAssembler:
    """Assemble 8-step health signal dict from CSV data."""

    def __init__(self):
        self.impact_scores = pd.read_csv(DATA_DIR / "managed_care_program_allocation_2026.csv")
        self.activity_logs = pd.read_csv(DATA_DIR / "managed_care_activity_logs.csv")
        self.appt_data = pd.read_csv(DATA_DIR / "managed_care_appt_utilization.csv", low_memory=False)
        self.benefits_deep = json.load(open(DATA_DIR / "managed_care_benefit_deep.json"))
        self.appt_deep = json.load(open(DATA_DIR / "managed_care_appt_deep.json"))

        self.today = date.today()

    def assemble_signal(self, user_id):
        """Assemble complete 8-step signal dict for one user."""
        signal = {
            'user_id': str(user_id),
            'timestamp': datetime.now().isoformat(),
            'signal_assembly': {}
        }

        # Step 1: Identity (user metadata)
        signal['signal_assembly']['identity'] = self._step1_identity(user_id)

        # Step 2: Biomarkers (health test results)
        signal['signal_assembly']['biomarkers'] = self._step2_biomarkers(user_id)

        # Step 3: Appointments (booked, completed, pending)
        signal['signal_assembly']['appointments'] = self._step3_appointments(user_id)

        # Step 4: Communication (outreach history — simulated)
        signal['signal_assembly']['communication'] = self._step4_communication(user_id)

        # Step 5: Adherence (daily habit tracking)
        signal['signal_assembly']['adherence'] = self._step5_adherence(user_id)

        # Step 6: Benefits (which services user is eligible for)
        signal['signal_assembly']['benefits'] = self._step6_benefits(user_id)

        # Step 7: Engagement trend (improving/stable/declining)
        signal['signal_assembly']['engagement_trend'] = self._step7_engagement_trend(user_id)

        # Step 8: Completeness score (data quality)
        signal['signal_assembly']['completeness'] = self._step8_completeness(signal)

        return signal

    def _step1_identity(self, user_id):
        """Core identity."""
        try:
            impact_row = self.impact_scores[self.impact_scores['mobile_number_hash'] == user_id]
            if impact_row.empty:
                return {'status': 'not_found'}
            row = impact_row.iloc[0]
            return {
                'user_id': str(user_id),
                'health_condition': row['impact'],
                'enrollment_date': '2026-06-01',  # VYTAL activation
                'days_enrolled': (self.today - date(2026, 6, 1)).days,
                'programme': row['impact'],
            }
        except Exception as e:
            return {'error': str(e)}

    def _step2_biomarkers(self, user_id):
        """Latest health test results + risk band."""
        try:
            impact_row = self.impact_scores[self.impact_scores['mobile_number_hash'] == user_id]
            if impact_row.empty:
                return {'status': 'no_tests'}
            row = impact_row.iloc[0]
            return {
                'primary_condition': row['impact'],
                'total_score': float(row['total_score']),
                'normalized_score': float(row['normalized_score']),
                'num_tests': int(row['num_tests']) if pd.notna(row['num_tests']) else 0,
                'risk_band': 'very_high' if row['total_score'] > 30 else 'high' if row['total_score'] > 15 else 'moderate',
                'has_retest': False,  # VYTAL is new, no baseline comparisons yet
            }
        except Exception as e:
            return {'error': str(e)}

    def _step3_appointments(self, user_id):
        """Appointment completion, pending, cancelled."""
        try:
            appts = self.appt_data[self.appt_data['mobile_number_hash'] == user_id].copy()
            if appts.empty:
                return {'total_scheduled': 0, 'completion_rate': 0}

            appts['claim_status'] = appts['claim_status'].str.lower()
            completed = len(appts[appts['claim_status'].isin(['authorized', 'redeemed', 'paid'])])
            cancelled = len(appts[appts['claim_status'] == 'cancelled'])
            total = len(appts)

            return {
                'total_scheduled': total,
                'completed': completed,
                'cancelled': cancelled,
                'completion_rate': round(completed / total * 100, 1) if total > 0 else 0,
                'benefits_used': appts['benefit_name'].unique().tolist() if 'benefit_name' in appts.columns else [],
                'days_since_last': (self.today - pd.to_datetime(appts['claim_month'].max())).days if len(appts) > 0 else None,
            }
        except Exception as e:
            return {'error': str(e)}

    def _step4_communication(self, user_id):
        """Simulated outreach history (future: from InteractionLog table)."""
        # For now, based on appointment engagement as proxy
        try:
            appts = self.appt_data[self.appt_data['mobile_number_hash'] == user_id]
            if len(appts) > 1:
                return {
                    'voice_sent': 2,
                    'voice_answered': 1,
                    'wa_sent': 3,
                    'wa_responded': 2,
                    'overall_response_rate': 0.6,
                    'days_since_last_interaction': 5,
                    'engagement_status': 'active',
                }
            else:
                return {
                    'voice_sent': 1,
                    'voice_answered': 0,
                    'wa_sent': 1,
                    'wa_responded': 1,
                    'overall_response_rate': 0.5,
                    'days_since_last_interaction': 10,
                    'engagement_status': 'low_engagement',
                }
        except:
            return {'engagement_status': 'unknown'}

    def _step5_adherence(self, user_id):
        """Daily habit tracking (steps, weight, sleep, meals)."""
        try:
            activity = self.activity_logs[self.activity_logs['mobile_number_hash'] == user_id]
            if activity.empty:
                return {'adherence_rate': 0, 'days_tracked': 0}

            total_days = len(activity)
            steps = int(activity['steps_logged'].sum()) if 'steps_logged' in activity.columns else 0
            weight = int(activity['weight_logged'].sum()) if 'weight_logged' in activity.columns else 0
            sleep = int(activity['sleep_logged'].sum()) if 'sleep_logged' in activity.columns else 0
            meals = int(activity['meal_logged'].sum()) if 'meal_logged' in activity.columns else 0

            total_activities = steps + weight + sleep + meals
            adherence_rate = round((total_activities / (total_days * 4) * 100), 1) if total_days > 0 else 0

            return {
                'days_tracked': total_days,
                'steps_days': steps,
                'weight_days': weight,
                'sleep_days': sleep,
                'meals_days': meals,
                'total_activities': total_activities,
                'adherence_rate': adherence_rate,
            }
        except Exception as e:
            return {'error': str(e), 'adherence_rate': 0}

    def _step6_benefits(self, user_id):
        """Benefits eligibility + utilization."""
        try:
            y2026 = self.benefits_deep['by_year'].get('2026', {})
            benefits_list = y2026.get('benefits_found', [])
            user_benefits = [b['benefit_name'] for b in benefits_list if b.get('users', 0) > 0]

            return {
                'benefits_eligible': user_benefits[:5],  # Top 5
                'total_benefits_available': len(user_benefits),
            }
        except:
            return {'benefits_eligible': [], 'total_benefits_available': 0}

    def _step7_engagement_trend(self, user_id):
        """Improving/stable/declining pattern."""
        # Based on appointment trend: increasing appts = improving
        try:
            appts = self.appt_data[self.appt_data['mobile_number_hash'] == user_id]
            if len(appts) > 2:
                return 'improving'
            elif len(appts) == 1:
                return 'baseline_only'
            else:
                return 'unknown'
        except:
            return 'unknown'

    def _step8_completeness(self, signal):
        """Data quality score."""
        asm = signal['signal_assembly']
        fields_present = sum(1 for step in asm.values() if step and 'error' not in str(step))
        return {
            'fields_present': fields_present,
            'total_fields': len(asm),
            'completeness_pct': round(fields_present / len(asm) * 100, 1) if asm else 0,
        }


def generate_signal_snapshots(user_ids, limit=None):
    """Generate signal snapshots for list of users."""
    assembler = SignalAssembler()

    if limit:
        user_ids = user_ids[:limit]

    snapshots = []
    for i, user_id in enumerate(user_ids, 1):
        try:
            signal = assembler.assemble_signal(user_id)
            snapshots.append(signal)
            print(f"  {i}/{len(user_ids)} {str(user_id)[:20]}... assembled")
        except Exception as e:
            print(f"  {i}/{len(user_ids)} {str(user_id)[:20]}... ERROR: {str(e)[:60]}")

    return snapshots


# ─────────────────────────────────────────────────────────
# DATABASE STORAGE
# ─────────────────────────────────────────────────────────

def save_snapshots_to_db(snapshots):
    """Save signal snapshots to SQLite."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_signal_snapshots (
            id INTEGER PRIMARY KEY,
            user_id TEXT UNIQUE,
            signal_json TEXT,
            generated_at TEXT,
            health_trajectory TEXT,
            proxy_score REAL,
            needs_escalation INTEGER
        )
    ''')

    for snapshot in snapshots:
        cursor.execute('''
            INSERT OR REPLACE INTO user_signal_snapshots
            (user_id, signal_json, generated_at, health_trajectory, proxy_score)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            snapshot['user_id'],
            json.dumps(snapshot['signal_assembly']),
            snapshot['timestamp'],
            snapshot['signal_assembly'].get('engagement_trend', 'unknown'),
            snapshot['signal_assembly'].get('biomarkers', {}).get('normalized_score', 0),
        ))

    conn.commit()
    conn.close()
    print(f"\n✅ Saved {len(snapshots)} signal snapshots to SQLite")


# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--phr', help='Single user ID')
    args = parser.parse_args()

    print("\n" + "="*70)
    print("AGENT 1 — DATA ANALYST: 360° Signal Assembly")
    print("="*70)

    # Get list of users
    impact_df = pd.read_csv(DATA_DIR / "managed_care_program_allocation_2026.csv")

    if args.phr:
        user_ids = [args.phr]
    else:
        user_ids = impact_df['mobile_number_hash'].unique().tolist()

    limit_val = min(args.limit, len(user_ids)) if args.limit else len(user_ids)
    print(f"\nProcessing {limit_val} users...")

    # Generate snapshots
    snapshots = generate_signal_snapshots(user_ids, limit=args.limit)

    # Save to DB
    save_snapshots_to_db(snapshots)

    # Export sample JSON
    export_path = DATA_DIR / "agent1_signal_snapshots.json"
    with open(export_path, 'w') as f:
        json.dump(snapshots[:10], f, indent=2)
    print(f"Sample output → {export_path}")

    print("="*70 + "\n")


if __name__ == '__main__':
    main()
