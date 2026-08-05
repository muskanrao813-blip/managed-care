#!/usr/bin/env python3
"""
Generate AI recommendations via Claude API
Analyzes live Managed Care data and creates fresh recommendations daily

Usage:
  python generate_recommendations_claude.py

Requires:
  ANTHROPIC_API_KEY environment variable set
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime

# Check for API key
if not os.getenv("ANTHROPIC_API_KEY"):
    print("ERROR: ANTHROPIC_API_KEY not set")
    print("Set via: export ANTHROPIC_API_KEY='sk-...'")
    sys.exit(1)

try:
    from anthropic import Anthropic
except ImportError:
    print("ERROR: anthropic package not installed")
    print("Install via: pip install anthropic")
    sys.exit(1)

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

try:
    from db_layer import read_table
except:
    print("ERROR: db_layer import failed")
    sys.exit(1)

print("=" * 80)
print("GENERATING RECOMMENDATIONS VIA CLAUDE AI")
print("=" * 80)

# Load data
print("\n[1] Loading live data from Neon...")
try:
    comp = read_table('comparison_retest')
    dev = read_table('device_eligibility')
    policy = read_table('policy_data')
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

# Calculate metrics
print("[2] Calculating current metrics...")

mc_rows = comp[comp['managed_care_flag'] == 'Y']
non_mc_rows = comp[comp['managed_care_flag'] != 'Y']

mc_rate = (mc_rows['improvement_flag'] == 'Improved').sum() / len(mc_rows) * 100 if len(mc_rows) > 0 else 0
non_mc_rate = (non_mc_rows['improvement_flag'] == 'Improved').sum() / len(non_mc_rows) * 100 if len(non_mc_rows) > 0 else 0
advantage = mc_rate / non_mc_rate if non_mc_rate > 0 else 0

enrolled = len(policy[policy['policy_status'].isin(['COM', 'BOOKED', 'ACT'])].drop_duplicates('mobile_number_hash'))
very_high = len(policy[policy['cohort'] == 'Very High'].drop_duplicates('mobile_number_hash'))
zero_appt = len(dev[dev['appt_booked'] == 0])
hra_done = len(dev[dev['hra_available'] == True])
devices_allocated = len(dev[dev['device_allocated'] == True])

# Build prompt for Claude
data_context = f"""
MANAGED CARE 3.0 — LIVE DATA FOR RECOMMENDATION GENERATION

Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}

KEY METRICS FROM LIVE DATA:
- Enrolled Users: {enrolled:,}
- MC Improvement Rate: {mc_rate:.1f}%
- Non-MC Improvement Rate: {non_mc_rate:.1f}%
- Advantage: {advantage:.1f}×
- Very High Risk Cohort: {very_high:,} users
- Zero Appointment Users: {zero_appt:,}
- HRA Completed: {hra_done:,}
- Devices Allocated: {devices_allocated:,}

IMPROVEMENT BREAKDOWN:
- Improved: {(comp['improvement_flag'] == 'Improved').sum():,}
- Worsened: {(comp['improvement_flag'] == 'Worsened').sum():,}
- No Change: {(comp['improvement_flag'] == 'No Change').sum():,}

Generate 5 specific, actionable recommendations for Managed Care operations based on:
1. Programme effectiveness (MC vs non-MC improvement comparison)
2. Risk management (Very High cohort needs immediate attention)
3. Engagement gaps (high zero-appointment rate indicates low engagement)
4. Health assessment completion (HRA is low)
5. Device deployment progress

Requirements:
- Each recommendation must have: priority (1-5), title, action, expected_impact, owner, timeline
- Recommendations must be specific to current numbers
- Focus on actionable next steps the team can take this week
- Quantify expected impact

Return ONLY valid JSON array (no markdown, no extra text):
[
  {{
    "priority": 1,
    "title": "...",
    "action": "...",
    "expected_impact": "...",
    "owner": "...",
    "timeline": "..."
  }}
]
"""

print("[3] Calling Claude API for recommendations...")
print(f"    Data context: {len(data_context)} characters")

# Initialize Claude client
client = Anthropic()

# Call Claude
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=2000,
    messages=[
        {
            "role": "user",
            "content": data_context
        }
    ],
    system="""You are a healthcare analytics expert for a Managed Care programme.
Generate practical, data-driven recommendations based on current programme metrics.
Each recommendation must be specific, measurable, and actionable.
Return ONLY valid JSON array, no additional text or markdown."""
)

response_text = message.content[0].text.strip()

# Parse recommendations
try:
    # Remove markdown code blocks if present
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]

    recommendations = json.loads(response_text)
    print(f"[4] Generated {len(recommendations)} recommendations")

    # Build complete insights
    insights = {
        "meta": {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "data_source": "Live Neon + Claude AI",
            "model": "claude-3-5-sonnet"
        },
        "metrics": {
            "enrolled": enrolled,
            "very_high_cohort": very_high,
            "overall_mc_improved_pct": round(mc_rate, 2),
            "overall_non_mc_improved_pct": round(non_mc_rate, 2),
            "zero_appt": zero_appt,
            "devices_allocated": devices_allocated,
            "hra_completed": hra_done,
        },
        "insights": {
            "overview": {
                "headline": f"MC users improve at {mc_rate:.1f}% vs {non_mc_rate:.1f}% non-MC ({advantage:.1f}× advantage). {enrolled:,} enrolled.",
                "critical_flag": f"{zero_appt:,} users have zero appointments — immediate outreach needed." if zero_appt > 0 else None,
                "positive_flag": f"MC drives {advantage:.1f}x higher improvement." if advantage > 2 else None
            }
        },
        "recommendations": recommendations
    }

    # Save to file
    output_path = Path(__file__).parent / "claude_insights.json"
    with open(output_path, 'w') as f:
        json.dump(insights, f, indent=2)

    print(f"\n[5] Saved to {output_path}")
    print("\n" + "=" * 80)
    print("✓ COMPLETE — Dashboard has fresh AI recommendations")
    print("=" * 80)

    # Display recommendations
    print("\nGenerated Recommendations:")
    for r in recommendations[:3]:
        print(f"\n  P{r.get('priority', '?')}: {r.get('title', '?')[:60]}...")
    if len(recommendations) > 3:
        print(f"  ... and {len(recommendations) - 3} more")

except json.JSONDecodeError as e:
    print(f"\n✗ ERROR: Claude response not valid JSON")
    print(f"Response: {response_text[:200]}")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    sys.exit(1)
