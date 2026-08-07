"""
Combined Engagement Effect Analysis
Segments 2025 retested users by device + appointment + managed care combinations
Shows improvement breakdown for each segment
Reads from Neon PostgreSQL (not local CSVs)
"""
import sys
import os
import pandas as pd
from sqlalchemy import create_engine, text
from db_layer import save_dataframe

sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "Data")
os.makedirs(DATA_DIR, exist_ok=True)

# Neon PostgreSQL connection
DATABASE_URL = os.getenv("DATABASE_URL",
    "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"
)
neon_engine = create_engine(DATABASE_URL)

print("=" * 70)
print("  COMBINED ENGAGEMENT EFFECT - 2025 & 2026")
print("=" * 70)

# ============================================================
# YEAR 2025 - Read from Neon
# ============================================================
print("\n[2025] Loading data from Neon PostgreSQL...")

try:
    # Read from Neon tables
    with neon_engine.connect() as conn:
        df_comp = pd.read_sql_table("comparison_retest", conn, schema="managed_care")
        df_device = pd.read_sql_table("device_delivered", conn, schema="managed_care")
        df_appt = pd.read_sql_table("appointment_utilization", conn, schema="managed_care")

    # Filter for 2025 camp year
    if 'latest_camp_date' in df_comp.columns:
        df_comp = df_comp[df_comp['latest_camp_date'].astype(str).str.contains('2025', na=False)].copy()
    elif 'year' in df_comp.columns:
        df_comp = df_comp[df_comp['year'] == 2025].copy()

    # Remove rows with empty improvement_flag
    if 'improvement_flag' in df_comp.columns:
        df_comp = df_comp[df_comp['improvement_flag'].notna() & (df_comp['improvement_flag'] != '')].copy()

    # Filter MC enrolled users
    if 'managed_care_flag' in df_comp.columns:
        df_comp = df_comp[df_comp['managed_care_flag'] == 'Y'].copy()

    # Filter appointments for 2025
    if 'year' in df_appt.columns:
        df_appt = df_appt[df_appt['year'] == 2025].copy()

    print(f"  Comparison (2025 retested, MC enrolled only): {len(df_comp):,} rows")
    print(f"  Device delivered: {len(df_device):,} rows")
    print(f"  Appointments (2025): {len(df_appt):,} rows")

except Exception as e:
    print(f"[ERROR] Failed to read from Neon: {e}")
    print("[OK] Saving empty output and exiting")

    # Create empty output
    output_df = pd.DataFrame({
        'segment': ['No Data'],
        'count': [0],
        'avg_improvement': [0]
    })
    output_df.to_csv(os.path.join(DATA_DIR, 'managed_care_engagement_effect_2025.csv'), index=False)
    save_dataframe(output_df, "engagement_effect_2025", if_exists="replace")
    exit(0)

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
save_dataframe(df_result, "engagement_effect", if_exists="replace")
print(f"\n✓ Saved {output_path} — {len(df_result):,} rows")
print("\nDone.")
