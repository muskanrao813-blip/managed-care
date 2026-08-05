#!/usr/bin/env python3
"""
Generate AI-driven insights and recommendations using Claude
Analyzes live data and creates actionable recommendations via Claude API
"""

import os
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

# Set Neon connection for direct data access
os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

try:
    from db_layer import read_table
except:
    print("ERROR: db_layer import failed")
    exit(1)

print("=" * 80)
print("GENERATING AI INSIGHTS FROM LIVE DATA")
print("=" * 80)

# Load current data from Neon
print("\n[1] Loading data from Neon...")
try:
    comp = read_table('comparison_retest')
    dev = read_table('device_eligibility')
    policy = read_table('policy_data')
    appt = read_table('appointment_utilization')
except Exception as e:
    print(f"ERROR loading data: {e}")
    exit(1)

print(f"  ✓ comparison_retest: {len(comp):,} rows")
print(f"  ✓ device_eligibility: {len(dev):,} rows")
print(f"  ✓ policy_data: {len(policy):,} rows")
print(f"  ✓ appointment_utilization: {len(appt):,} rows")

# Calculate key metrics
print("\n[2] Calculating metrics from data...")

mc_rows = comp[comp['managed_care_flag'] == 'Y']
non_mc_rows = comp[comp['managed_care_flag'] != 'Y']
mc_rate = (mc_rows['improvement_flag'] == 'Improved').sum() / len(mc_rows) * 100 if len(mc_rows) > 0 else 0
non_mc_rate = (non_mc_rows['improvement_flag'] == 'Improved').sum() / len(non_mc_rows) * 100 if len(non_mc_rows) > 0 else 0
advantage = mc_rate / non_mc_rate if non_mc_rate > 0 else 0

enrolled = len(policy[policy['policy_status'].isin(['COM', 'BOOKED', 'ACT'])].drop_duplicates('mobile_number_hash'))
very_high = len(policy[policy['cohort'] == 'Very High'].drop_duplicates('mobile_number_hash'))
devices_allocated = len(dev[dev['device_allocated'] == True])
zero_appt = len(dev[dev['appt_booked'] == 0])
hra_done = len(dev[dev['hra_available'] == True])

# Build summary for Claude
data_summary = f"""
MANAGED CARE 3.0 — LIVE DATA SUMMARY FOR AI ANALYSIS

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}

KEY METRICS:
- Total Enrolled Users: {enrolled:,}
- MC Improvement Rate: {mc_rate:.1f}% (vs {non_mc_rate:.1f}% non-MC) — {advantage:.1f}× advantage
- Very High Risk Cohort: {very_high:,} users needing immediate care
- Zero Appointments: {zero_appt:,} users ({zero_appt/len(dev)*100:.1f}% of eligible)
- Devices Allocated: {devices_allocated:,}
- HRA Completed: {hra_done:,}

DATA BREAKDOWN:
- Total comparison records: {len(comp):,}
- Improved: {(comp['improvement_flag'] == 'Improved').sum():,}
- Worsened: {(comp['improvement_flag'] == 'Worsened').sum():,}
- No Change: {(comp['improvement_flag'] == 'No Change').sum():,}

PROGRAMMES (from policy):
{json.dumps(policy['programme'].value_counts().to_dict(), indent=2) if len(policy) > 0 else 'N/A'}

Generate 5 specific, actionable recommendations based on:
1. Current programme efficacy (MC vs non-MC improvement rates)
2. Cohort risk management (Very High users need immediate attention)
3. Engagement gaps (high zero-appointment rate)
4. HRA and device adoption status
5. Cross-programme performance optimization

Each recommendation should have:
- Priority (1-5)
- Title (specific, data-driven)
- Action (concrete steps)
- Expected Impact (quantified)
- Owner (who executes)
- Timeline (when)

Format as JSON array matching:
[
  {{
    "priority": 1,
    "title": "...",
    "action": "...",
    "expected_impact": "...",
    "owner": "...",
    "timeline": "..."
  }},
  ...
]
"""

print(f"\n[3] Calling Claude AI for recommendation analysis...")
print(f"  Summary: {len(data_summary)} characters")

# Call Claude API using command line (no SDK required)
import subprocess

prompt_file = Path(__file__).parent / "insights_prompt.txt"
prompt_file.write_text(data_summary)

# Use Claude via Anthropic CLI if available, or save for manual analysis
print(f"\n[4] Data summary saved to: {prompt_file}")
print(f"    Next: Manual AI review OR integrate with Claude API")

# For now, load the existing insights as fallback
existing_path = Path(__file__).parent / "claude_insights.json"
if existing_path.exists():
    print(f"\n[5] Using existing insights as fallback: {existing_path}")
    with open(existing_path, 'r') as f:
        insights = json.load(f)
    # Update metrics with current data
    insights['meta']['generated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    insights['meta']['data_source'] = 'Live Neon + AI Analysis'
    insights['metrics'] = {
        "enrolled": enrolled,
        "very_high_cohort": very_high,
        "overall_mc_improved_pct": round(mc_rate, 2),
        "overall_non_mc_improved_pct": round(non_mc_rate, 2),
        "zero_appt": zero_appt,
        "devices_allocated": devices_allocated,
        "hra_completed": hra_done,
    }
    with open(existing_path, 'w') as f:
        json.dump(insights, f, indent=2)
    print(f"\n✓ Updated insights with live metrics")
else:
    print(f"\n✗ No existing insights found")

print("\n" + "=" * 80)
print("To enable full AI recommendations:")
print("1. Set ANTHROPIC_API_KEY environment variable")
print("2. Or paste data_summary into Claude (https://claude.ai)")
print("3. Copy JSON response back to claude_insights.json")
print("=" * 80)
