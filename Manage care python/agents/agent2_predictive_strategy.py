"""
============================================================
AGENT 2 — PREDICTIVE STRATEGY
============================================================
Takes Agent 1 signal snapshots and generates personalized
7-day behavioral plans with psychology-strategy matrix.

Output: InterventionPlan table
  - weekly_plan_json: 7 days × 5 fields (action_type, benefit_to_push, message_theme, tone, opening_frame)
  - psychology_match: which type best matches this user
  - strategy_description: why we chose this approach
  - priority_focus: (diet | appointments | activity | mental_health)
  - adaptation_rules: which thresholds triggered acceleration

Usage:
  python -m agents.agent2_predictive_strategy --limit 50
"""

import sys, os, json, sqlite3
import pandas as pd
from datetime import datetime, date
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = Path(__file__).parent.parent
DATA_DIR = SCRIPT_DIR / "Data"
DB_PATH = SCRIPT_DIR / "agents" / "agent_db.sqlite"

# Psychology-Strategy Matrix
PSYCHOLOGY_TYPES = {
    'motivated_tracker': {
        'tone': 'encouraging, progress-focused',
        'channels': ['voice', 'whatsapp', 'push'],
        'message_themes': ['milestone achievement', 'data insights', 'improvement trends'],
        'opening_frame': "Your progress shows promise. Keep momentum",
        'weekly_intensity': 'high',
    },
    'anxious_avoider': {
        'tone': 'reassuring, non-judgmental, empathetic',
        'channels': ['whatsapp'],
        'message_themes': ['small steps', 'no judgment', 'support available'],
        'opening_frame': "No pressure. We are here for you",
        'weekly_intensity': 'low',
    },
    'family_driven': {
        'tone': 'family-centered, relational',
        'channels': ['voice', 'whatsapp'],
        'message_themes': ['family health', 'shared goals', 'family support'],
        'opening_frame': 'This is for your family wellbeing',
        'weekly_intensity': 'medium',
    },
    'skeptical_passive': {
        'tone': 'evidence-based, factual, no hype',
        'channels': ['whatsapp'],
        'message_themes': ['clinical evidence', 'data-backed benefits', 'transparent info'],
        'opening_frame': 'Here is what the science shows',
        'weekly_intensity': 'low',
    },
    'career_driven': {
        'tone': 'efficient, results-oriented, time-saving',
        'channels': ['push', 'whatsapp'],
        'message_themes': ['efficiency', 'ROI on health', 'time-saving tips'],
        'opening_frame': 'Investing 10 min/day saves health issues',
        'weekly_intensity': 'medium',
    },
    'convenience_seeker': {
        'tone': 'easy, frictionless, minimal effort',
        'channels': ['push', 'whatsapp'],
        'message_themes': ['easy wins', 'quick tips', 'no complex setup'],
        'opening_frame': "Here is the easiest thing to do today",
        'weekly_intensity': 'low',  # Don't overwhelm
    },
}

# SLA Ceiling: when to accelerate follow-ups
SLA_CEILINGS = {
    'diet_compliance_below_40': {'days_to_pull': 7, 'reason': 'Low diet adherence triggers immediate engagement'},
    'trajectory_declining': {'days_to_pull': 14, 'reason': 'Health metrics declining—needs intervention'},
    'medical_alert': {'days_to_pull': 3, 'reason': 'Clinical escalation—immediate contact'},
    'never_engaged': {'days_to_pull': 30, 'reason': 'New user still onboarding'},
}

class StrategyGenerator:
    """Generate personalized intervention plans."""

    def __init__(self):
        self.snapshots_db = self._load_snapshots()

    def _load_snapshots(self):
        """Load signal snapshots from Agent 1 output."""
        snapshots = {}
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, signal_json FROM user_signal_snapshots')
            for user_id, signal_json in cursor.fetchall():
                snapshots[user_id] = json.loads(signal_json)
            conn.close()
        except:
            pass  # DB may not exist yet
        return snapshots

    def generate_plan(self, user_id, signal_snapshot):
        """Generate 7-day intervention plan for one user."""
        plan = {
            'user_id': str(user_id),
            'timestamp': datetime.now().isoformat(),
            'plan_data': {}
        }

        # Assign psychology type (simplified: based on adherence rate)
        adherence_rate = signal_snapshot.get('adherence', {}).get('adherence_rate', 0)
        if adherence_rate > 70:
            psych_type = 'motivated_tracker'
        elif adherence_rate > 40:
            psych_type = 'convenience_seeker'
        elif adherence_rate > 20:
            psych_type = 'anxious_avoider'
        else:
            psych_type = 'skeptical_passive'

        psych_config = PSYCHOLOGY_TYPES.get(psych_type, PSYCHOLOGY_TYPES['skeptical_passive'])

        # Determine priority focus
        biomarkers = signal_snapshot.get('biomarkers', {})
        appts = signal_snapshot.get('appointments', {})
        adherence = signal_snapshot.get('adherence', {})

        if biomarkers.get('risk_band') == 'very_high':
            priority = 'appointments'  # Need clinical intervention ASAP
        elif adherence.get('adherence_rate', 0) < 40:
            priority = 'diet'  # Build basic habit
        elif appts.get('completion_rate', 0) < 60:
            priority = 'appointments'
        else:
            priority = 'activity'

        # Build 7-day weekly plan
        weekly_plan = []
        benefits_rotation = [
            'Nutritionist Consultation Benefit',
            'Teleconsultation',
            'Health Monitoring',
            'Lab Discounts',
            'Wellness Inclinic Consultation Benefit',
        ]

        for day in range(1, 8):
            benefit = benefits_rotation[(day - 1) % len(benefits_rotation)]
            action = self._select_action(day, priority, psych_config)

            day_plan = {
                'day': day,
                'action_type': action,  # none | voice | whatsapp | push
                'benefit_to_push': benefit if action != 'none' else None,
                'message_theme': psych_config['message_themes'][(day - 1) % len(psych_config['message_themes'])],
                'tone': psych_config['tone'],
                'opening_frame': psych_config['opening_frame'],
            }
            weekly_plan.append(day_plan)

        plan['plan_data'] = {
            'psychology_type': psych_type,
            'priority_focus': priority,
            'weekly_plan': weekly_plan,
            'sla_adaptations': self._check_sla_ceiling(signal_snapshot),
            'strategy_narrative': f"User is {psych_type}. Focus on {priority}. Intensity: {psych_config['weekly_intensity']}.",
        }

        return plan

    def _select_action(self, day, priority, psych_config):
        """Select channel for this day based on psychology & intensity."""
        intensity = psych_config['weekly_intensity']
        channels = psych_config['channels']

        if intensity == 'high':
            actions = ['voice', 'whatsapp', 'push']
        elif intensity == 'medium':
            actions = ['whatsapp', 'push', 'none']
        else:  # low
            actions = ['whatsapp', 'none', 'none']

        return actions[(day - 1) % len(actions)]

    def _check_sla_ceiling(self, signal):
        """Check if any SLA ceilings should accelerate follow-ups."""
        adaptations = []

        adherence_rate = signal.get('adherence', {}).get('adherence_rate', 0)
        if adherence_rate < 40:
            adaptations.append(SLA_CEILINGS['diet_compliance_below_40'])

        trajectory = signal.get('engagement_trend', 'unknown')
        if trajectory == 'declining':
            adaptations.append(SLA_CEILINGS['trajectory_declining'])

        appts = signal.get('appointments', {})
        if appts.get('total_scheduled', 0) == 0:
            adaptations.append(SLA_CEILINGS['never_engaged'])

        return adaptations


def generate_plans(user_ids, limit=None):
    """Generate intervention plans for users."""
    generator = StrategyGenerator()

    if limit:
        user_ids = user_ids[:limit]

    plans = []
    for i, user_id in enumerate(user_ids, 1):
        try:
            signal = generator.snapshots_db.get(user_id, {})
            if not signal:
                # Generate minimal signal if not in DB
                signal = {
                    'adherence': {'adherence_rate': 30},
                    'biomarkers': {'risk_band': 'high'},
                    'appointments': {'total_scheduled': 0},
                    'engagement_trend': 'baseline_only',
                }

            plan = generator.generate_plan(user_id, signal)
            plans.append(plan)
            print(f"  {i}/{len(user_ids)} {str(user_id)[:20]}... plan generated ({plan['plan_data']['psychology_type']})")
        except Exception as e:
            print(f"  {i}/{len(user_ids)} {str(user_id)[:20]}... ERROR: {str(e)[:60]}")

    return plans


def save_plans_to_db(plans):
    """Save plans to SQLite."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS intervention_plans (
            id INTEGER PRIMARY KEY,
            user_id TEXT UNIQUE,
            plan_json TEXT,
            generated_at TEXT,
            psychology_type TEXT,
            priority_focus TEXT
        )
    ''')

    for plan in plans:
        cursor.execute('''
            INSERT OR REPLACE INTO intervention_plans
            (user_id, plan_json, generated_at, psychology_type, priority_focus)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            plan['user_id'],
            json.dumps(plan['plan_data']),
            plan['timestamp'],
            plan['plan_data'].get('psychology_type', 'unknown'),
            plan['plan_data'].get('priority_focus', 'unknown'),
        ))

    conn.commit()
    conn.close()
    print(f"\n✅ Saved {len(plans)} intervention plans to SQLite")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--phr', help='Single user ID')
    args = parser.parse_args()

    print("\n" + "="*70)
    print("AGENT 2 — PREDICTIVE STRATEGY: 7-Day Behavioral Plans")
    print("="*70)

    # Get list of users
    impact_df = pd.read_csv(DATA_DIR / "managed_care_program_allocation_2026.csv")

    if args.phr:
        user_ids = [args.phr]
    else:
        user_ids = impact_df['mobile_number_hash'].unique().tolist()

    limit_val = min(args.limit, len(user_ids)) if args.limit else len(user_ids)
    print(f"\nGenerating plans for {limit_val} users...")

    # Generate plans
    plans = generate_plans(user_ids, limit=args.limit)

    # Save to DB
    save_plans_to_db(plans)

    # Export sample JSON
    export_path = DATA_DIR / "agent2_intervention_plans.json"
    with open(export_path, 'w') as f:
        json.dump(plans[:10], f, indent=2)
    print(f"Sample output → {export_path}")

    print("="*70 + "\n")


if __name__ == '__main__':
    main()
