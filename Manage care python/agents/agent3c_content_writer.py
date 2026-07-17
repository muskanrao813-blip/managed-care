"""
============================================================
AGENT 3C — CONTENT WRITER
============================================================
Takes Agent 2 intervention plans and generates personalized
voice scripts, WhatsApp messages, and push notifications.

Medical Guardrails:
  - No medical diagnoses in content
  - No prescription medication names
  - No clinical procedures descriptions
  - Use general wellness language only

Output: ContentGenerationLog table + campaign_content.json
  - voice_script: 60-90 sec multi-stage script
  - whatsapp_hsm: HSM template (160 words max, with dynamic vars)
  - push: Title + body (≤50/80 chars)

Usage:
  python -m agents.agent3c_content_writer --limit 50
"""

import sys, os, json, sqlite3
import pandas as pd
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = Path(__file__).parent.parent
DATA_DIR = SCRIPT_DIR / "Data"
DB_PATH = SCRIPT_DIR / "agents" / "agent_db.sqlite"

# Medical guardrails
BANNED_CLINICAL_TERMS = [
    'diabetes', 'dyslipidemia', 'hypertension', 'insulin', 'metformin',
    'diagnosis', 'prescription', 'medication', 'surgery', 'catheter',
    'ablation', 'stent', 'bypass',
]

BANNED_PHRASES = [
    'you have diabetes',
    'your disease',
    'medication required',
    'clinical trial',
]

class ContentWriter:
    """Generate campaign content for voice/WA/push."""

    def __init__(self):
        self.plans_db = self._load_plans()

    def _load_plans(self):
        """Load intervention plans from Agent 2 output."""
        plans = {}
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, plan_json FROM intervention_plans')
            for user_id, plan_json in cursor.fetchall():
                plans[user_id] = json.loads(plan_json)
            conn.close()
        except:
            pass
        return plans

    def generate_content(self, user_id, plan):
        """Generate content for all days in user's weekly plan."""
        contents = []

        for day_plan in plan.get('weekly_plan', []):
            if day_plan['action_type'] == 'none':
                continue

            content = {
                'user_id': str(user_id),
                'day': day_plan['day'],
                'action_type': day_plan['action_type'],
                'benefit': day_plan.get('benefit_to_push', 'wellness'),
                'generated_at': datetime.now().isoformat(),
            }

            if day_plan['action_type'] == 'voice':
                content['voice_script'] = self._generate_voice_script(
                    day_plan, plan.get('psychology_type', 'skeptical_passive')
                )

            elif day_plan['action_type'] == 'whatsapp':
                content['whatsapp_hsm'] = self._generate_whatsapp(
                    day_plan, plan.get('psychology_type', 'skeptical_passive')
                )

            elif day_plan['action_type'] == 'push':
                content['push'] = self._generate_push(
                    day_plan, plan.get('psychology_type', 'skeptical_passive')
                )

            # Validate against medical guardrails
            if not self._validate_content(content):
                content['validation_status'] = 'failed_guardrail'
            else:
                content['validation_status'] = 'passed'

            contents.append(content)

        return contents

    def _generate_voice_script(self, day_plan, psych_type):
        """Generate voice script (60-90 seconds)."""
        benefit = day_plan.get('benefit_to_push', 'wellness')
        tone = day_plan.get('tone', 'friendly')
        opening = day_plan.get('opening_frame', 'Hi, we wanted to check in')

        scripts = {
            'Nutritionist Consultation Benefit': {
                'intro': f"{opening}. We have a nutritionist ready to help you.",
                'body': "They'll create a personalized meal plan based on your health. Just 20 minutes.",
                'cta': "Would you like to book a consultation? Press 1 for yes.",
                'fallback': "You can also schedule anytime via the app.",
            },
            'Teleconsultation': {
                'intro': f"{opening}. A doctor is available for a quick video call.",
                'body': "Perfect if you have quick questions. Takes just 10 minutes.",
                'cta': "Ready to book? Press 1.",
                'fallback': "Reschedule anytime in the app.",
            },
            'Health Monitoring': {
                'intro': f"{opening}. It's time for your health checkup.",
                'body': "Quick lab tests show us how you're progressing.",
                'cta': "Ready to book? Press 1.",
                'fallback': "Check the app for available slots.",
            },
            'wellness': {
                'intro': f"{opening}.",
                'body': "We're here to support your health goals.",
                'cta': "Any questions? Press 1.",
                'fallback': "Chat with us in the app.",
            },
        }

        script_template = scripts.get(benefit, scripts['wellness'])

        return {
            'full_script': f"{script_template['intro']} {script_template['body']} {script_template['cta']}",
            'intro': script_template['intro'],
            'body': script_template['body'],
            'cta': script_template['cta'],
            'fallback_wa_message': script_template['fallback'],
            'estimated_duration_sec': 75,
            'tone': tone,
        }

    def _generate_whatsapp(self, day_plan, psych_type):
        """Generate WhatsApp HSM (160 words max)."""
        benefit = day_plan.get('benefit_to_push', 'wellness')
        opening = day_plan.get('opening_frame', 'Hi!')

        templates = {
            'Nutritionist Consultation Benefit': {
                'template_name': 'nutrition_consultation_offer',
                'header': 'Personalized Nutrition Plan',
                'body': f"{opening} Your personalized nutrition plan is ready. Our nutritionist will help you understand which foods work best for your health. Book a 20-min consultation today!",
                'footer': 'Reply YES to book or LATER to reschedule',
                'dynamic_vars': ['[NUTRITIONIST_NAME]', '[AVAILABLE_TIME]'],
            },
            'Teleconsultation': {
                'template_name': 'telehealth_offer',
                'header': 'Quick Doctor Chat',
                'body': f"{opening} Have health questions? Chat with a doctor via video call today. 10 minutes, from home. Available now!",
                'footer': 'Reply YES to book',
                'dynamic_vars': ['[DOCTOR_NAME]', '[TIME_SLOT]'],
            },
            'Health Monitoring': {
                'template_name': 'healthcheck_reminder',
                'header': 'Time for Your Checkup',
                'body': f"{opening} It's been 30 days. Let's check your progress with fresh lab results. Slots available nearby this week.",
                'footer': 'Reply YES to book',
                'dynamic_vars': ['[LAB_NAME]', '[APPOINTMENT_DATE]'],
            },
            'wellness': {
                'template_name': 'wellness_checkin',
                'header': 'We Care About You',
                'body': f"{opening} How are you doing? We're here to support your health journey.",
                'footer': 'Reply if you have any questions',
                'dynamic_vars': [],
            },
        }

        template = templates.get(benefit, templates['wellness'])

        return {
            'template_name': template['template_name'],
            'header': template['header'],
            'body': template['body'],
            'footer': template['footer'],
            'dynamic_vars_ordered': template['dynamic_vars'],
            'character_count': len(template['body']),
        }

    def _generate_push(self, day_plan, psych_type):
        """Generate push notification (≤50 title, ≤80 body)."""
        benefit = day_plan.get('benefit_to_push', 'wellness')

        push_options = {
            'Nutritionist Consultation Benefit': {
                'title': 'Nutrition Plan Ready',
                'body': 'Nutritionist is ready to help. Book now!',
                'tap_action': 'app://nutrition/book',
            },
            'Teleconsultation': {
                'title': 'Doctor Available',
                'body': '10-min video call with doctor today',
                'tap_action': 'app://telehealth/available',
            },
            'Health Monitoring': {
                'title': 'Checkup Time',
                'body': 'Book your health monitoring session',
                'tap_action': 'app://health/book',
            },
            'wellness': {
                'title': 'Your Health Matters',
                'body': 'Check your progress',
                'tap_action': 'app://dashboard',
            },
        }

        push = push_options.get(benefit, push_options['wellness'])

        return {
            'title': push['title'][:50],
            'body': push['body'][:80],
            'tap_action': push['tap_action'],
        }

    def _validate_content(self, content):
        """Validate against medical guardrails."""
        text_to_check = json.dumps(content).lower()

        for term in BANNED_CLINICAL_TERMS:
            if term in text_to_check:
                return False

        for phrase in BANNED_PHRASES:
            if phrase.lower() in text_to_check:
                return False

        return True


def generate_all_content(user_ids, limit=None):
    """Generate content for all users."""
    writer = ContentWriter()

    if limit:
        user_ids = user_ids[:limit]

    all_content = []
    for i, user_id in enumerate(user_ids, 1):
        try:
            plan = writer.plans_db.get(user_id)
            if not plan:
                # Generate minimal plan if not found
                plan = {
                    'psychology_type': 'skeptical_passive',
                    'weekly_plan': [
                        {
                            'day': 1,
                            'action_type': 'whatsapp',
                            'benefit_to_push': 'wellness',
                            'tone': 'friendly',
                            'opening_frame': 'Hi there',
                        }
                    ],
                }

            contents = writer.generate_content(user_id, plan)
            all_content.extend(contents)
            print(f"  {i}/{len(user_ids)} {str(user_id)[:20]}... {len(contents)} content pieces")
        except Exception as e:
            print(f"  {i}/{len(user_ids)} {str(user_id)[:20]}... ERROR: {str(e)[:60]}")

    return all_content


def save_content_to_db(all_content):
    """Save content to SQLite."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_generation_log (
            id INTEGER PRIMARY KEY,
            user_id TEXT,
            day INTEGER,
            action_type TEXT,
            content_json TEXT,
            generated_at TEXT,
            validation_status TEXT
        )
    ''')

    for content in all_content:
        cursor.execute('''
            INSERT INTO content_generation_log
            (user_id, day, action_type, content_json, generated_at, validation_status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            content['user_id'],
            content['day'],
            content['action_type'],
            json.dumps(content),
            content['generated_at'],
            content.get('validation_status', 'unknown'),
        ))

    conn.commit()
    conn.close()
    print(f"\n✅ Saved {len(all_content)} content pieces to SQLite")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--phr', help='Single user ID')
    args = parser.parse_args()

    print("\n" + "="*70)
    print("AGENT 3C — CONTENT WRITER: Voice/WA/Push Generation")
    print("="*70)

    # Get list of users
    impact_df = pd.read_csv(DATA_DIR / "managed_care_program_allocation_2026.csv")

    if args.phr:
        user_ids = [args.phr]
    else:
        user_ids = impact_df['mobile_number_hash'].unique().tolist()

    print(f"\nGenerating content for {len(user_ids[:args.limit]) if args.limit else len(user_ids)} users...")

    # Generate content
    all_content = generate_all_content(user_ids, limit=args.limit)

    # Save to DB
    save_content_to_db(all_content)

    # Export sample JSON
    export_path = DATA_DIR / "agent3c_campaign_content.json"
    with open(export_path, 'w') as f:
        json.dump(all_content[:10], f, indent=2)
    print(f"Sample output → {export_path}")

    print("="*70 + "\n")


if __name__ == '__main__':
    main()
