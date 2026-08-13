"""
Generate Daily Recommendations for VYTAL 2026
Runs as part of daily pipeline, stores results in Neon for fast dashboard access
"""
import sys
import os
import pandas as pd
from datetime import datetime
from db_layer import read_table, save_dataframe

sys.stdout.reconfigure(encoding='utf-8')

print("[START] Generate Recommendations")

# Load data
appts = read_table("appt_source")
policy = read_table("policy_data")

if appts is None or appts.empty or policy is None or policy.empty:
    print("[ERROR] Missing data tables")
    sys.exit(1)

# Filter to ALL VYTAL users (not just VYTAL.*26) for accurate enrolled count
policy_vytal_all = policy[policy['mc_product_code'].str.contains('VYTAL', regex=True, na=False)]
enrolled_vytal_all = policy_vytal_all['phr_id'].nunique()

# Date range (dashboard default)
date_from = "2026-06-01"
date_to = "2026-08-07"
appts['appt_date'] = pd.to_datetime(appts['appt_date'], errors='coerce')
appts_filtered = appts[(appts['appt_date'] >= pd.to_datetime(date_from)) & (appts['appt_date'] <= pd.to_datetime(date_to))].copy()

# Calculate metrics
total_appts = len(appts_filtered)
completed = len(appts_filtered[appts_filtered['status'] == 'COM']) if 'status' in appts_filtered.columns else 0
cancelled = len(appts_filtered[appts_filtered['status'] == 'CAN']) if 'status' in appts_filtered.columns else 0

# Service breakdown
diet_total = len(appts_filtered[appts_filtered['speciality'] == 'Dietitian/Nutritionist']) if 'speciality' in appts_filtered.columns else 0
diet_completed = len(appts_filtered[(appts_filtered['speciality'] == 'Dietitian/Nutritionist') & (appts_filtered['status'] == 'COM')]) if 'speciality' in appts_filtered.columns else 0
doctor_total = len(appts_filtered[appts_filtered['speciality'] == 'General Physician']) if 'speciality' in appts_filtered.columns else 0
doctor_completed = len(appts_filtered[(appts_filtered['speciality'] == 'General Physician') & (appts_filtered['status'] == 'COM')]) if 'speciality' in appts_filtered.columns else 0

diet_completion_rate = (diet_completed / diet_total * 100) if diet_total > 0 else 0
doctor_completion_rate = (doctor_completed / doctor_total * 100) if doctor_total > 0 else 0
cancellation_rate = (cancelled / total_appts * 100) if total_appts > 0 else 0

# Cohort distribution
cohort_counts = {}
if 'cohort' in policy_vytal_all.columns:
    cohort_counts = policy_vytal_all['cohort'].value_counts().to_dict()

very_high_count = cohort_counts.get('Very High', 0)
very_high_rate = (very_high_count / enrolled_vytal_all * 100) if enrolled_vytal_all > 0 else 0

# Zero appointments: from ALL appointments (not just filtered date range) for accuracy
unique_appt_users_all = appts['phr_id'].nunique() if 'phr_id' in appts.columns else 0
zero_appt_users = enrolled_vytal_all - unique_appt_users_all
zero_appt_rate = (zero_appt_users / enrolled_vytal_all * 100) if enrolled_vytal_all > 0 else 0

print(f"[OK] Calculated metrics for {enrolled_vytal_all} VYTAL enrolled users")
print(f"  - Zero appointments: {zero_appt_users} ({zero_appt_rate:.1f}%)")
print(f"  - Very High cohort: {very_high_count} ({very_high_rate:.1f}%)")
print(f"  - Diet completion: {diet_completion_rate:.1f}%")
print(f"  - Doctor completion: {doctor_completion_rate:.1f}%")
print(f"  - Cancellation rate: {cancellation_rate:.1f}%")

# Build recommendations
recommendations = []

# Rule 1: Zero Appointment Users (CRITICAL)
if zero_appt_rate > 80:
    recommendations.append({
        "priority": 1,
        "timeline": "Weeks 1-2",
        "title": f"Engage {zero_appt_users:,} users with zero appointments ({zero_appt_rate:.0f}%)",
        "expected_impact": "Increase appointment booking rate by 15-20%",
        "owner": "Care Ops",
        "metric_value": zero_appt_users,
        "metric_pct": round(zero_appt_rate, 1)
    })

# Rule 2: Doctor Performance (HIGH)
if doctor_completion_rate < 40 and diet_completion_rate > 85:
    recommendations.append({
        "priority": 2,
        "timeline": "Week 2-3",
        "title": f"Improve Doctor appointments (currently {doctor_completion_rate:.0f}% completion)",
        "expected_impact": f"Bring Doctor rate to {diet_completion_rate:.0f}% (like Diet)",
        "owner": "Clinical Ops",
        "metric_value": doctor_total,
        "metric_pct": round(doctor_completion_rate, 1)
    })

# Rule 3: Very High Risk Cohort (HIGH)
if very_high_rate > 30:
    recommendations.append({
        "priority": 2,
        "timeline": "Week 1",
        "title": f"Assign care managers to {very_high_count} very high-risk users ({very_high_rate:.0f}%)",
        "expected_impact": "Reduce adverse events, improve health outcomes",
        "owner": "Care Management",
        "metric_value": very_high_count,
        "metric_pct": round(very_high_rate, 1)
    })

# Rule 4: Cancellation Rate (MEDIUM)
if cancellation_rate > 10:
    recommendations.append({
        "priority": 3,
        "timeline": "Week 3-4",
        "title": f"Reduce appointment cancellations ({cancellation_rate:.0f}% rate)",
        "expected_impact": "Improve completion rate by 5-10%",
        "owner": "Care Ops",
        "metric_value": cancelled,
        "metric_pct": round(cancellation_rate, 1)
    })

# Sort by priority
recommendations.sort(key=lambda x: x.get("priority", 5))

# Create DataFrame
df_recommendations = pd.DataFrame(recommendations)
df_recommendations['generated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
df_recommendations['date_range_from'] = date_from
df_recommendations['date_range_to'] = date_to
df_recommendations['enrolled_count'] = enrolled_vytal_all

# Save to Neon
save_dataframe(df_recommendations, "recommendations_vytal_2026", if_exists="replace")

print(f"[OK] Saved {len(recommendations)} recommendations to Neon")
for i, rec in enumerate(recommendations, 1):
    print(f"  {i}. [{rec['priority']}] {rec['title']}")

print("[DONE]")
