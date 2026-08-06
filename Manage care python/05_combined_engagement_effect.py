"""
Combined Engagement Effect Analysis
Segments 2025 retested users by device + appointment + managed care combinations
Shows improvement breakdown for each segment
"""
import sys
import os
import urllib
import pandas as pd
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "Data")
os.makedirs(DATA_DIR, exist_ok=True)

from config import TRINO_HOST, TRINO_USER, TRINO_PASSWORD
pw = urllib.parse.quote_plus(TRINO_PASSWORD)
eng = create_engine(f'trino://{TRINO_USER}:{pw}@{TRINO_HOST}:443/system?http_scheme=https')

def load_csv(filename):
    """Load CSV from Data folder, case-insensitive. Handle empty files."""
    path = None
    if os.path.exists(os.path.join(DATA_DIR, filename)):
        path = os.path.join(DATA_DIR, filename)
    else:
        for f in os.listdir(DATA_DIR):
            if f.lower() == filename.lower():
                path = os.path.join(DATA_DIR, f)
                break
    if path:
        try:
            return pd.read_csv(path)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
    return pd.DataFrame()

print("=" * 70)
print("  COMBINED ENGAGEMENT EFFECT - 2025 & 2026")
print("=" * 70)

# ============================================================
# YEAR 2025
# ============================================================
print("\n[2025] Loading data files...")

# Check if required CSVs exist - if not, skip
csv_path = os.path.join(DATA_DIR, "managed_care_comparison.csv")
if not os.path.exists(csv_path):
    print("[INFO] Required CSV files not found - skipping engagement analysis")

    # Create empty output and exit
    output_df = pd.DataFrame({
        'segment': ['No Data'],
        'count': [0],
        'avg_improvement': [0]
    })
    output_df.to_csv(os.path.join(DATA_DIR, 'managed_care_engagement_effect_2025.csv'), index=False)
    print("[OK] Saved empty output")
    exit(0)

df_comp = load_csv("managed_care_comparison.csv")

# Filter for 2025 camp year - check which date column exists
if 'latest_camp_date' in df_comp.columns:
    df_comp = df_comp[df_comp['latest_camp_date'].astype(str).str.startswith('2025')].copy()
elif 'camp_date' in df_comp.columns:
    df_comp = df_comp[df_comp['camp_date'].astype(str).str.startswith('2025')].copy()
elif 'year' in df_comp.columns:
    df_comp = df_comp[df_comp['year'] == 2025].copy()

# Remove rows with empty improvement_flag (no retested data)
if 'improvement_flag' in df_comp.columns:
    df_comp = df_comp[df_comp['improvement_flag'].notna() & (df_comp['improvement_flag'] != '')].copy()

# Filter to ONLY managed care enrolled users
if 'managed_care_flag' in df_comp.columns:
    df_comp = df_comp[df_comp['managed_care_flag'] == 'Y'].copy()

df_device = load_csv("managed_care_device_delivered_2025.csv")
df_appt = load_csv("managed_care_appt_utilization.csv")
df_appt = df_appt[df_appt['year'] == 2025] if not df_appt.empty else df_appt

print(f"  Comparison (2025 retested, MC enrolled only): {len(df_comp):,} rows")
print(f"  Device delivered: {len(df_device):,} rows")
print(f"  Appointments (2025): {len(df_appt):,} rows")

# If no data, create empty output and exit
if df_comp.empty or len(df_comp) == 0:
    print("\n[WARNING] No 2025 comparison data available - skipping analysis")

    # Create empty output file
    output_df = pd.DataFrame({
        'segment': ['No Data'],
        'count': [0],
        'avg_improvement': [0]
    })
    output_df.to_csv(os.path.join(DATA_DIR, 'managed_care_engagement_effect_2025.csv'), index=False)
    print("[OK] Saved empty output")
    exit(0)

# Create indicator columns - check column exists first
device_col = 'mobile_number_hash' if 'mobile_number_hash' in df_comp.columns else 'phone'
df_comp['had_device'] = df_comp[device_col].isin(df_device[device_col].unique()) if device_col in df_device.columns and not df_device.empty else False
df_comp['had_appt'] = df_comp[device_col].isin(df_appt[device_col].unique()) if device_col in df_appt.columns and not df_appt.empty else False

# Classify into segments
def classify_engagement(row):
    has_device = row['had_device']
    has_appt = row['had_appt']

    if has_device and has_appt:
        return "Device + Appointment"
    elif has_appt and not has_device:
        return "Appointment Only"
    else:
        return "Neither"

df_comp['engagement_segment'] = df_comp.apply(classify_engagement, axis=1)

# Analysis for 2025
segments_2025 = []
for segment in ["Device + Appointment", "Appointment Only", "Neither"]:
    subset = df_comp[df_comp['engagement_segment'] == segment]
    if len(subset) == 0:
        continue

    # Count by improvement_flag
    improved = len(subset[subset['improvement_flag'] == 'Improved'])
    worsened = len(subset[subset['improvement_flag'] == 'Worsened'])
    no_change = len(subset[subset['improvement_flag'] == 'No change'])
    no_risk = len(subset[subset['improvement_flag'] == 'No Risk'])

    total = len(subset)
    improved_pct = round(100 * improved / total, 1) if total > 0 else 0
    worsened_pct = round(100 * worsened / total, 1) if total > 0 else 0
    no_change_pct = round(100 * no_change / total, 1) if total > 0 else 0

    segments_2025.append({
        'year': 2025,
        'engagement_segment': segment,
        'total_users': total,
        'improved': improved,
        'improved_pct': improved_pct,
        'worsened': worsened,
        'worsened_pct': worsened_pct,
        'no_change': no_change,
        'no_change_pct': no_change_pct,
        'no_risk': no_risk
    })

df_result_2025 = pd.DataFrame(segments_2025)
print(f"\n2025 Engagement Effect:")
print(df_result_2025.to_string(index=False))

# ============================================================
# YEAR 2026 - Blank placeholder
# ============================================================
print("\n[2026] Placeholder (no device data yet)...")
segments_2026 = []
for segment in ["Device + Appointment", "Appointment Only", "Neither"]:
    segments_2026.append({
        'year': 2026,
        'engagement_segment': segment,
        'total_users': None,
        'improved': None,
        'improved_pct': None,
        'worsened': None,
        'worsened_pct': None,
        'no_change': None,
        'no_change_pct': None,
        'no_risk': None
    })

df_result_2026 = pd.DataFrame(segments_2026)

# ============================================================
# COMBINE & SAVE
# ============================================================
df_result = pd.concat([df_result_2025, df_result_2026], ignore_index=True)

output_path = os.path.join(DATA_DIR, "managed_care_engagement_effect.csv")
df_result.to_csv(output_path, index=False)
print(f"\n✓ Saved {output_path} — {len(df_result):,} rows")
print("\nDone.")
