"""
Interactive Agent Portal API - WITH AGENT 2 PLAN REGENERATION
Backend for testing Agent 2 dynamic behavior
"""
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_PATH = Path("agents/agent_db.sqlite")
DATA_PATH = Path("Data")

# Load user profiles
with open(DATA_PATH / "user_profiles.json") as f:
    USER_PROFILES = json.load(f)

# Psychology-Strategy Matrix (from Agent 2)
PSYCHOLOGY_TYPES = {
    'motivated_tracker': {
        'tone': 'encouraging, progress-focused',
        'channels': ['voice', 'whatsapp', 'push'],
        'weekly_intensity': 'high',
    },
    'anxious_avoider': {
        'tone': 'reassuring, non-judgmental, empathetic',
        'channels': ['whatsapp'],
        'weekly_intensity': 'low',
    },
    'skeptical_passive': {
        'tone': 'evidence-based, factual, no hype',
        'channels': ['whatsapp'],
        'weekly_intensity': 'low',
    },
    'career_driven': {
        'tone': 'efficient, results-oriented',
        'channels': ['push', 'whatsapp'],
        'weekly_intensity': 'medium',
    },
}

def classify_psychology(signal):
    """Classify user psychology type based on signals"""
    adherence = signal['signal_assembly']['adherence']['adherence_rate']
    response = signal['signal_assembly']['communication']['overall_response_rate']
    engagement = signal['signal_assembly']['communication']['engagement_status']
    trend = signal['signal_assembly']['engagement_trend']
    app_activity = signal['signal_assembly']['adherence'].get('app_activity_days', 0)

    # Classification logic
    if adherence >= 0.8 and response >= 0.9:
        return 'career_driven'
    elif adherence >= 0.5 and response >= 0.7:
        return 'motivated_tracker'
    elif adherence < 0.3 and response >= 0.7:
        return 'anxious_avoider'
    else:
        return 'skeptical_passive'

def generate_weekly_plan(psychology_type, priority_focus):
    """Generate 7-day plan based on psychology type"""
    weekday_schedule = {
        'skeptical_passive': [1, 4, 7],  # Days with messages
        'anxious_avoider': [1, 4, 7],
        'motivated_tracker': [1, 2, 3, 4, 5, 6, 7],  # All days
        'career_driven': [1, 3, 5, 7],
    }

    benefits = [
        "Nutritionist Consultation Benefit",
        "Lab Discounts",
        "Teleconsultation",
        "Health Monitoring",
        "Pharmacy Discounts"
    ]

    themes = {
        'skeptical_passive': 'clinical evidence',
        'anxious_avoider': 'support available',
        'motivated_tracker': 'milestone achievement',
        'career_driven': 'efficiency',
    }

    days_with_action = weekday_schedule.get(psychology_type, [1, 4, 7])

    weekly_plan = []
    for day in range(1, 8):
        if day in days_with_action:
            weekly_plan.append({
                "day": day,
                "action_type": "whatsapp" if psychology_type in ['anxious_avoider', 'skeptical_passive'] else "voice" if day % 2 == 0 else "push",
                "benefit_to_push": benefits[(day-1) % len(benefits)],
                "message_theme": themes.get(psychology_type, 'clinical evidence'),
                "tone": PSYCHOLOGY_TYPES[psychology_type]['tone'],
                "opening_frame": f"Message for {psychology_type}"
            })
        else:
            weekly_plan.append({
                "day": day,
                "action_type": "none",
                "benefit_to_push": None,
                "message_theme": "rest day",
                "tone": "",
                "opening_frame": ""
            })

    return weekly_plan

def get_user_signal(user_id):
    """Get current signal snapshot for user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    result = cursor.execute(
        "SELECT signal_json FROM user_signal_snapshots WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    if result:
        return json.loads(result[0])
    return None

def get_user_plan(user_id):
    """Get current intervention plan for user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    result = cursor.execute(
        "SELECT psychology_type, priority_focus, plan_json FROM intervention_plans WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    if result:
        return {
            "psychology_type": result[0],
            "priority_focus": result[1],
            "plan": json.loads(result[2])
        }
    return None

def save_plan(user_id, psychology_type, priority_focus, plan_json):
    """Save plan to database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT OR REPLACE INTO intervention_plans (user_id, psychology_type, priority_focus, plan_json) VALUES (?, ?, ?, ?)",
        (user_id, psychology_type, priority_focus, json.dumps(plan_json))
    )

    conn.commit()
    conn.close()

@app.route('/api/users', methods=['GET'])
def list_users():
    """Get all 5 user profiles with current plans"""
    users_data = []

    for profile in USER_PROFILES:
        user_id = profile['id']
        signal = get_user_signal(user_id)
        plan = get_user_plan(user_id)

        users_data.append({
            "id": user_id,
            "name": profile['name'],
            "program": profile['program'],
            "status": profile['initial_status'],
            "current_metrics": {
                "adherence": signal['signal_assembly']['adherence']['adherence_rate'] if signal else 0,
                "response_rate": signal['signal_assembly']['communication']['overall_response_rate'] if signal else 0,
                "app_activity": signal['signal_assembly']['adherence'].get('app_activity_days', 0) if signal else 0,
                "days_enrolled": signal['signal_assembly']['identity']['days_enrolled'] if signal else 0
            },
            "plan": plan
        })

    return jsonify(users_data)

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Get specific user details"""
    signal = get_user_signal(user_id)
    plan = get_user_plan(user_id)
    profile = next((p for p in USER_PROFILES if p['id'] == user_id), None)

    return jsonify({
        "id": user_id,
        "name": profile['name'] if profile else "Unknown",
        "program": profile['program'] if profile else "Unknown",
        "signal": signal,
        "plan": plan
    })

@app.route('/api/users/<user_id>/update-interaction', methods=['POST'])
def update_interaction(user_id):
    """
    Update user interactions and REGENERATE PLAN WITH AGENT 2
    """
    data = request.json

    # Get current signal and EXISTING plan
    signal = get_user_signal(user_id)
    old_plan_full = get_user_plan(user_id)

    if not signal:
        return jsonify({"error": "User not found"}), 404

    old_psychology = old_plan_full['psychology_type'] if old_plan_full else 'skeptical_passive'
    old_weekly_plan = old_plan_full['plan'] if old_plan_full and 'plan' in old_plan_full else []

    # UPDATE SIGNAL WITH NEW INTERACTION DATA
    signal['signal_assembly']['adherence']['adherence_rate'] = data.get('adherence', signal['signal_assembly']['adherence']['adherence_rate'])
    signal['signal_assembly']['communication']['overall_response_rate'] = data.get('response_rate', signal['signal_assembly']['communication']['overall_response_rate'])
    signal['signal_assembly']['adherence']['app_activity_days'] = data.get('app_activity', signal['signal_assembly']['adherence']['app_activity_days'])

    # Update engagement status
    new_adherence = signal['signal_assembly']['adherence']['adherence_rate']
    new_response = signal['signal_assembly']['communication']['overall_response_rate']
    signal['signal_assembly']['communication']['engagement_status'] = 'high_engagement' if new_adherence > 0.6 else 'low_engagement'

    # Update trajectory
    profile = next((p for p in USER_PROFILES if p['id'] == user_id), None)
    if profile:
        old_adherence = profile['initial_adherence']
        if new_adherence > old_adherence:
            signal['signal_assembly']['engagement_trend'] = 'improving'
        elif new_adherence < old_adherence:
            signal['signal_assembly']['engagement_trend'] = 'declining'

    # SAVE UPDATED SIGNAL
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO user_signal_snapshots (user_id, signal_json) VALUES (?, ?)",
        (user_id, json.dumps(signal))
    )
    conn.commit()
    conn.close()

    # REGENERATE PLAN WITH AGENT 2 LOGIC
    new_psychology = classify_psychology(signal)
    priority_focus = "diet" if new_adherence < 0.5 else "appointments" if new_adherence < 0.7 else "optimization"
    new_plan_json = generate_weekly_plan(new_psychology, priority_focus)

    # SAVE NEW PLAN
    save_plan(user_id, new_psychology, priority_focus, new_plan_json)

    # GET PLAN DETAILS
    old_channels = PSYCHOLOGY_TYPES.get(old_psychology, {}).get('channels', [])
    new_channels = PSYCHOLOGY_TYPES.get(new_psychology, {}).get('channels', [])
    old_tone = PSYCHOLOGY_TYPES.get(old_psychology, {}).get('tone', '')
    new_tone = PSYCHOLOGY_TYPES.get(new_psychology, {}).get('tone', '')

    # DETERMINE WHAT CHANGED
    psychology_changed = old_psychology != new_psychology
    channels_changed = set(old_channels) != set(new_channels)

    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "interaction_description": data.get('description', ''),

        "old_metrics": {
            "adherence": profile['initial_adherence'] if profile else 0,
            "response_rate": profile['initial_response'] if profile else 0,
        },

        "old_plan": {
            "psychology_type": old_psychology,
            "channels": old_channels,
            "tone": old_tone,
            "weekly_plan": old_weekly_plan,
            "priority_focus": old_plan_full['priority_focus'] if old_plan_full else 'diet'
        },

        "new_plan": {
            "psychology_type": new_psychology,
            "channels": new_channels,
            "tone": new_tone,
            "priority_focus": priority_focus,
            "weekly_plan": new_plan_json
        },

        "changes": {
            "psychology_type_changed": psychology_changed,
            "channels_changed": channels_changed,
            "message": f"{'PLAN UPDATED!' if psychology_changed or channels_changed else 'Plan remains the same'}"
        },

        "metrics": {
            "adherence": new_adherence,
            "response_rate": new_response,
            "app_activity": signal['signal_assembly']['adherence']['app_activity_days'],
            "engagement_trend": signal['signal_assembly']['engagement_trend']
        }
    })

@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({"status": "API running with Agent 2 plan regeneration", "users": len(USER_PROFILES)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
