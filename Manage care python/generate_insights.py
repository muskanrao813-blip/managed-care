#!/usr/bin/env python3
"""
Generate dynamic insights and recommendations from current data
Runs after scripts 01-04 to analyze latest metrics and generate actionable recommendations
"""

import os
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from db_layer import read_table

# Set Neon connection
os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"

print("=" * 80)
print("GENERATING INSIGHTS FROM LIVE DATA")
print("=" * 80)

# Load current data from Neon
print("\n[1] Loading data from Neon...")
comp = read_table('comparison_retest')
dev = read_table('device_eligibility')
policy = read_table('policy_data')
appt = read_table('appointment_utilization')

print(f"  - comparison_retest: {len(comp):,} rows")
print(f"  - device_eligibility: {len(dev):,} rows")
print(f"  - policy_data: {len(policy):,} rows")
print(f"  - appointment_utilization: {len(appt):,} rows")

# Calculate metrics from data
print("\n[2] Calculating metrics...")

# MC vs Non-MC improvement rates
mc_rows = comp[comp['managed_care_flag'] == 'Y'].copy()
non_mc_rows = comp[comp['managed_care_flag'] != 'Y'].copy()

mc_improved = (mc_rows['improvement_flag'] == 'Improved').sum()
mc_total = len(mc_rows)
mc_rate = (mc_improved / mc_total * 100) if mc_total > 0 else 0

non_mc_improved = (non_mc_rows['improvement_flag'] == 'Improved').sum()
non_mc_total = len(non_mc_rows)
non_mc_rate = (non_mc_improved / non_mc_total * 100) if non_mc_total > 0 else 0

advantage = (mc_rate / non_mc_rate) if non_mc_rate > 0 else 0

# Enrolled users
enrolled = len(policy[policy['policy_status'].isin(['COM', 'BOOKED', 'ACT'])].drop_duplicates('mobile_number_hash'))

# Very High cohort
very_high = len(policy[policy['cohort'] == 'Very High'].drop_duplicates('mobile_number_hash'))

# Device eligibility
devices_allocated = len(dev[dev['device_allocated'] == True])
no_device = len(dev[dev['device_allocated'] == False])

# Appointment stats
zero_appt = len(dev[dev['appt_booked'] == 0])
zero_appt_pct = (zero_appt / len(dev) * 100) if len(dev) > 0 else 0

# HRA completion
hra_done = len(dev[dev['hra_available'] == True])

print(f"\n  MC Improvement: {mc_rate:.1f}%")
print(f"  Non-MC Improvement: {non_mc_rate:.1f}%")
print(f"  Advantage: {advantage:.1f}×")
print(f"  Enrolled: {enrolled:,} users")
print(f"  Very High Cohort: {very_high:,}")
print(f"  Devices Allocated: {devices_allocated:,}")
print(f"  Zero Appointments: {zero_appt:,} ({zero_appt_pct:.1f}%)")
print(f"  HRA Completed: {hra_done:,}")

# Generate insights JSON
print("\n[3] Building insights...")

insights = {
    "meta": {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data_source": "Live Neon PostgreSQL",
        "enrolled_year": "2026"
    },
    "metrics": {
        "enrolled": enrolled,
        "very_high_cohort": very_high,
        "overall_mc_improved_pct": round(mc_rate, 2),
        "overall_non_mc_improved_pct": round(non_mc_rate, 2),
        "zero_appt": zero_appt,
        "zero_appt_pct": round(zero_appt_pct, 2),
        "devices_allocated": devices_allocated,
        "hra_completed": hra_done,
    },
    "insights": {
        "overview": {
            "headline": f"MC users improve at {mc_rate:.1f}% vs {non_mc_rate:.1f}% non-MC ({advantage:.1f}× advantage). {enrolled:,} enrolled. {zero_appt:,} need first appointment.",
            "positive_flag": f"MC drives {advantage:.1f}x higher improvement rate — programme efficacy proven." if advantage > 2 else None,
            "critical_flag": f"{zero_appt:,} users ({zero_appt_pct:.1f}%) have zero appointments — immediate outreach needed." if zero_appt > 0 else None
        }
    },
    "recommendations": []
}

# Generate dynamic recommendations based on data
reco_list = []

# Recommendation 1: First appointments
if zero_appt > 0:
    reco_list.append({
        "priority": 1,
        "title": f"Drive first appointment for {zero_appt:,} users with zero bookings",
        "action": f"Send programme-specific booking links to {enrolled:,} VYTAL users. Prioritize Very High ({very_high:,}) and High risk users for care manager calls.",
        "expected_impact": f"First appointment booked for at least {int(zero_appt*0.12):,} users within 30 days",
        "owner": "Product Manager + Care Team",
        "timeline": "This week"
    })

# Recommendation 2: Cohort management
if very_high > 0:
    reco_list.append({
        "priority": 2,
        "title": f"Assign {very_high:,} Very High cohort users to care managers",
        "action": f"Export Very High cohort list. Assign to care managers for bi-weekly teleconsults and monitoring.",
        "expected_impact": f"100% of {very_high:,} Very High users assigned within 2 weeks",
        "owner": "Product Manager",
        "timeline": "Today"
    })

# Recommendation 3: HRA completion
if hra_done < enrolled * 0.25:
    hra_gap = enrolled - hra_done
    reco_list.append({
        "priority": 3,
        "title": f"Push HRA completion — only {hra_done} of {enrolled} done ({round(hra_done/enrolled*100, 1)}%)",
        "action": f"Send in-app push + WhatsApp to {hra_gap:,} users who haven't completed HRA. Unlocks lifestyle assessment.",
        "expected_impact": f"Increase HRA completion to 25% within 30 days",
        "owner": "Product Manager",
        "timeline": "This week"
    })

# Recommendation 4: Device allocation
if devices_allocated > 0:
    reco_list.append({
        "priority": 4,
        "title": f"Dispatch {devices_allocated} allocated devices and schedule Day-7 checks",
        "action": f"{devices_allocated} users are eligible for devices. Coordinate with fulfillment to dispatch and schedule activation check-ins.",
        "expected_impact": f"All {devices_allocated} devices dispatched within 2 weeks",
        "owner": "Product Manager",
        "timeline": "This week"
    })

# Recommendation 5: Weekly monitoring
reco_list.append({
    "priority": 5,
    "title": "Run weekly programme health check across all programmes",
    "action": "Monitor: appointment rate, HRA completion, device activation, cohort assignment. Escalate if any metric declines.",
    "expected_impact": "Early warning signals for drop-offs before next camp cycle",
    "owner": "Product Manager",
    "timeline": "Every Monday"
})

insights["recommendations"] = reco_list

# Save insights
output_path = Path(__file__).parent / "claude_insights.json"
with open(output_path, 'w') as f:
    json.dump(insights, f, indent=2)

print(f"\n[4] Saved insights to {output_path}")
print(f"  - {len(reco_list)} recommendations generated")
print(f"  - Generated at: {insights['meta']['generated_at']}")

print("\n" + "=" * 80)
print("INSIGHTS COMPLETE — Dashboard will show current data and recommendations")
print("=" * 80)
