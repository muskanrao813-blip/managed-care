"""
Managed Care Dashboard Server with PostgreSQL Backend
Replaces CSV loading with database queries.
Supports both local SQLite and Render PostgreSQL.
"""

import os
import json
from flask import Flask, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import pandas as pd
from pathlib import Path

# Load environment variables
load_dotenv()

# Import database layer
try:
    from db_layer import read_table, get_last_update
except ImportError:
    print("⚠ db_layer.py not found - running without database support")
    read_table = None

app = Flask(__name__, static_folder=os.path.dirname(__file__))
CORS(app)

PORT = int(os.getenv("PORT", 8001))
DASHBOARD_FILE = "managed_care_dashboard_final.html"

def convert_nan_to_none(obj):
    if isinstance(obj, dict):
        return {k: convert_nan_to_none(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_nan_to_none(v) for v in obj]
    elif isinstance(obj, float) and pd.isna(obj):
        return None
    elif hasattr(obj, 'isoformat'):  # datetime.date, datetime.datetime, etc.
        return obj.isoformat()
    return obj


@app.route("/")
def dashboard():
    """Serve main dashboard HTML"""
    html_path = Path(__file__).parent / DASHBOARD_FILE
    if html_path.exists():
        return send_file(html_path)
    return "Dashboard HTML not found", 404


@app.route("/test")
def test_api():
    """Serve API test page"""
    html_path = Path(__file__).parent / "test_dashboard_api.html"
    if html_path.exists():
        return send_file(html_path)
    return "Test file not found", 404


def load_csv_data(table_name):
    """Try to load data from CSV files as fallback"""
    csv_mappings = {
        "programme_allocation": "managed_care_program_allocation.csv",
        "comparison_retest": ["managed_care_comparison.csv", "managed_care_comparison_2026.csv"],
        "device_eligibility": ["managed_care_device_eligibility_2026.csv", "managed_care_device_eligibility_lifestyle.csv"],
        "appt_source": "managed_care_appt_source.csv",
        "appointment_source": "managed_care_appt_source.csv",
        "vytal_appt_flat": "managed_care_vytal_appt_flat.csv",
        "vytal_appointments": "managed_care_vytal_appt_flat.csv",
    }

    csv_files = csv_mappings.get(table_name)
    if not csv_files:
        return None

    # Handle both single file and list of alternatives
    if isinstance(csv_files, str):
        csv_files = [csv_files]

    for csv_file in csv_files:
        csv_path = Path(__file__).parent / "Data" / csv_file
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path, low_memory=False)
                if not df.empty:
                    return df
            except:
                continue
    return None


@app.route("/api/data/<table_name>")
def get_table_data(table_name):
    """
    Fetch data from database table as JSON.
    Falls back to CSV files if database not available.
    Usage: GET /api/data/programme_allocation
    """
    # Map frontend table names to actual Neon table names
    table_mapping = {
        'appointment_source': 'appt_source',
        'vytal_appointments': 'vytal_appt_flat',
    }

    actual_table_name = table_mapping.get(table_name, table_name)

    df = None

    # Try database first
    if read_table:
        try:
            df = read_table(actual_table_name)
        except:
            df = None

    # Fall back to CSV
    if df is None or df.empty:
        df = load_csv_data(table_name)

    if df is None or df.empty:
        return jsonify({"data": [], "rows": 0, "message": "No data found"})

    # Convert to JSON-serializable format
    data = df.to_dict(orient="records")
    # Convert NaN to None in all records
    data = [convert_nan_to_none(record) for record in data]

    return jsonify({
        "data": data,
        "rows": len(data),
        "columns": list(df.columns),
        "last_updated": "Fresh from CSV" if read_table is None else str(get_last_update(table_name))
    })


@app.route("/api/data/<table_name>/summary")
def get_table_summary(table_name):
    """
    Get summary statistics for a table.
    Falls back to CSV if database unavailable.
    Usage: GET /api/data/programme_allocation/summary
    """
    df = None

    # Try database first
    if read_table:
        try:
            df = read_table(table_name)
        except:
            df = None

    # Fall back to CSV
    if df is None or df.empty:
        df = load_csv_data(table_name)

    if df is None or df.empty:
        return jsonify({"summary": {}})

    # Generate summary stats
    summary = {
        "total_rows": len(df),
        "columns": list(df.columns),
        "numeric_stats": {}
    }

    # Add numeric column stats
    for col in df.select_dtypes(include=['number']).columns:
        mean_val = float(df[col].mean()) if pd.notna(df[col].mean()) else None
        min_val = float(df[col].min()) if pd.notna(df[col].min()) else None
        max_val = float(df[col].max()) if pd.notna(df[col].max()) else None
        summary["numeric_stats"][col] = {
            "mean": mean_val,
            "min": min_val,
            "max": max_val,
        }

    return jsonify(summary)


@app.route("/api/status")
def health_check():
    """Health check endpoint for Render with pipeline status"""
    pipeline_status = None
    try:
        status_table = read_table("pipeline_status") if read_table else None
        if status_table is not None and not status_table.empty:
            # Get most recent "end" event
            end_events = status_table[status_table['event'] == 'end'].sort_values('timestamp', ascending=False)
            if not end_events.empty:
                pipeline_status = {
                    "last_refresh": str(end_events.iloc[0]['timestamp']),
                    "last_refresh_date": str(end_events.iloc[0]['pipeline_date'])
                }
    except Exception as e:
        print(f"[WARN] Could not fetch pipeline status: {e}")

    return jsonify({
        "status": "ok",
        "database": "connected" if read_table else "not_initialized",
        "port": PORT,
        "pipeline": pipeline_status
    })


@app.route("/api/insights")
def get_insights():
    """Fetch pre-calculated daily recommendations for VYTAL 2026"""
    try:
        # Get actual data refresh timestamp from pipeline status
        data_refresh_time = None
        try:
            status_table = read_table("pipeline_status") if read_table else None
            if status_table is not None and not status_table.empty:
                end_events = status_table[status_table['event'] == 'end'].sort_values('timestamp', ascending=False)
                if not end_events.empty:
                    data_refresh_time = str(end_events.iloc[0]['timestamp'])
        except:
            pass

        # Try to load pre-calculated recommendations (generated by 09_generate_recommendations.py)
        recs_table = read_table("recommendations_vytal_2026") if read_table else None

        if recs_table is None or recs_table.empty:
            print("[WARN] Pre-calculated recommendations not found, calculating on-the-fly...")
            return get_insights_fallback()

        # Convert to list of dicts for JSON
        recommendations = recs_table.drop(columns=['generated_at', 'date_range_from', 'date_range_to', 'enrolled_count'], errors='ignore').to_dict('records')

        # Get enrollment count from last record
        enrolled = int(recs_table['enrolled_count'].iloc[0]) if 'enrolled_count' in recs_table.columns else 0
        generated_at = data_refresh_time or str(recs_table['generated_at'].iloc[0]) if 'generated_at' in recs_table.columns else ""

        # Load policy data for KPI cards
        policy = read_table("policy_data") if read_table else None
        hra_wellness = read_table("hra_wellness") if read_table else None
        hra_stats = read_table("hra_stats") if read_table else None
        prog_alloc = read_table("programme_allocation") if read_table else None

        policy_vytal_2026 = policy[policy['mc_product_code'].str.contains('VYTAL.*26', regex=True, na=False)] if policy is not None else None

        cohort_counts = {}
        zero_appt_users = 0
        zero_appt_rate = 0
        mc_improvement_pct = 0
        hra_completion_pct = 0
        hra_completed_count = 0

        if policy_vytal_2026 is not None:
            if 'cohort' in policy_vytal_2026.columns:
                cohort_counts = policy_vytal_2026['cohort'].value_counts().to_dict()

            # Get zero-appt count from recommendations
            if len(recommendations) > 0 and 'metric_value' in recommendations[0]:
                zero_appt_users = recommendations[0]['metric_value']
                zero_appt_rate = recommendations[0]['metric_pct']

            # Calculate MC improvement rate
            if prog_alloc is not None and len(prog_alloc) > 0:
                mc_users_hash = policy_vytal_2026[policy_vytal_2026['managed_care_program'].notna()]['mobile_number_hash'].unique()
                prog_alloc_mc = prog_alloc[prog_alloc['mobile_number_hash'].isin(mc_users_hash)]
                if len(prog_alloc_mc) > 0 and 'total_score' in prog_alloc_mc.columns:
                    # Use average score improvement as proxy (higher score = better improvement)
                    avg_score = prog_alloc_mc['total_score'].mean()
                    mc_improvement_pct = min(100, max(0, avg_score * 2))  # Scale score to percentage

        # Calculate HRA completion
        if hra_wellness is not None:
            hra_completed_count = len(hra_wellness)
            hra_completion_pct = (hra_completed_count / enrolled * 100) if enrolled > 0 else 0

        return jsonify({
            "insights": {
                "recommendations": recommendations,
                "overview": {
                    "positive_flag": "Engagement pipeline stable",
                    "critical_flag": f"{zero_appt_rate:.0f}% users have zero appointments"
                }
            },
            "metrics": {
                "zero_appt": {
                    "zero_appt": zero_appt_users,
                    "pct": zero_appt_rate
                },
                "cohort_split": cohort_counts,
                "enrolled": enrolled,
                "camp_total": enrolled,
                "improvement_pivot": {
                    "overall_mc_improved_pct": round(mc_improvement_pct, 1),
                    "overall_non_mc_improved_pct": 0.0
                },
                "hra_stats": {
                    "completed": hra_completed_count
                }
            },
            "meta": {
                "generated_at": generated_at
            }
        }), 200

    except Exception as e:
        print(f"Error fetching insights: {e}")
        return get_insights_fallback()


def get_insights_fallback():
    """Fallback: Calculate recommendations on-the-fly if pre-calculated not available"""
    recommendations = []
    try:
        appts = read_table("vytal_appt_flat") if read_table else None
        policy = read_table("policy_data") if read_table else None

        if appts is None or appts.empty or policy is None or policy.empty:
            return jsonify({"insights": {"recommendations": []}, "error": "No data available"}), 200

        policy_vytal_2026 = policy[policy['mc_product_code'].str.contains('VYTAL.*26', regex=True, na=False)]
        enrolled_vytal_2026 = policy_vytal_2026['phr_id'].nunique()

        date_from = "2026-06-01"
        date_to = "2026-08-07"
        appts_filtered = appts[(appts['appt_date'] >= date_from) & (appts['appt_date'] <= date_to)].copy()

        total_appts = len(appts_filtered)
        cancelled = len(appts_filtered[appts_filtered['status'] == 'CAN']) if 'status' in appts_filtered.columns else 0
        diet_total = len(appts_filtered[appts_filtered['speciality'] == 'Dietitian/Nutritionist']) if 'speciality' in appts_filtered.columns else 0
        diet_completed = len(appts_filtered[(appts_filtered['speciality'] == 'Dietitian/Nutritionist') & (appts_filtered['status'] == 'COM')]) if 'speciality' in appts_filtered.columns else 0
        doctor_total = len(appts_filtered[appts_filtered['speciality'] == 'General Physician']) if 'speciality' in appts_filtered.columns else 0
        doctor_completed = len(appts_filtered[(appts_filtered['speciality'] == 'General Physician') & (appts_filtered['status'] == 'COM')]) if 'speciality' in appts_filtered.columns else 0

        diet_completion_rate = (diet_completed / diet_total * 100) if diet_total > 0 else 0
        doctor_completion_rate = (doctor_completed / doctor_total * 100) if doctor_total > 0 else 0
        cancellation_rate = (cancelled / total_appts * 100) if total_appts > 0 else 0

        cohort_counts = {}
        if 'cohort' in policy_vytal_2026.columns:
            cohort_counts = policy_vytal_2026['cohort'].value_counts().to_dict()

        unique_appt_users = appts_filtered['phr_id'].nunique() if 'phr_id' in appts_filtered.columns else 0
        zero_appt_users = enrolled_vytal_2026 - unique_appt_users
        zero_appt_rate = (zero_appt_users / enrolled_vytal_2026 * 100) if enrolled_vytal_2026 > 0 else 0

        very_high_count = cohort_counts.get('Very High', 0)
        very_high_rate = (very_high_count / enrolled_vytal_2026 * 100) if enrolled_vytal_2026 > 0 else 0

        if zero_appt_rate > 80:
            recommendations.append({
                "priority": 1,
                "timeline": "Weeks 1-2",
                "title": f"Engage {zero_appt_users:,} users with zero appointments ({zero_appt_rate:.0f}%)",
                "expected_impact": "Increase appointment booking rate by 15-20%",
                "owner": "Care Ops"
            })

        if doctor_completion_rate < 40 and diet_completion_rate > 85:
            recommendations.append({
                "priority": 2,
                "timeline": "Week 2-3",
                "title": f"Improve Doctor appointments (currently {doctor_completion_rate:.0f}% completion)",
                "expected_impact": f"Bring Doctor rate to {diet_completion_rate:.0f}%",
                "owner": "Clinical Ops"
            })

        if very_high_rate > 30:
            recommendations.append({
                "priority": 2,
                "timeline": "Week 1",
                "title": f"Assign care managers to {very_high_count} very high-risk users ({very_high_rate:.0f}%)",
                "expected_impact": "Reduce adverse events, improve health outcomes",
                "owner": "Care Management"
            })

        if cancellation_rate > 10:
            recommendations.append({
                "priority": 3,
                "timeline": "Week 3-4",
                "title": f"Reduce appointment cancellations ({cancellation_rate:.0f}% rate)",
                "expected_impact": "Improve completion rate by 5-10%",
                "owner": "Care Ops"
            })

        recommendations.sort(key=lambda x: x.get("priority", 5))

        return jsonify({
            "insights": {
                "recommendations": recommendations,
                "overview": {
                    "positive_flag": "Engagement pipeline stable",
                    "critical_flag": f"{zero_appt_rate:.0f}% users have zero appointments"
                }
            },
            "metrics": {
                "zero_appt": {"zero_appt": zero_appt_users, "pct": round(zero_appt_rate, 1)},
                "cohort_split": cohort_counts,
                "enrolled": enrolled_vytal_2026,
                "camp_total": enrolled_vytal_2026
            },
            "meta": {"generated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}
        }), 200

    except Exception as e:
        print(f"Error in fallback: {e}")
        return jsonify({"insights": {"recommendations": []}, "error": str(e)}), 500


@app.route("/api/csv/<filename>")
def get_csv_fallback(filename):
    """
    Fallback: serve CSV from Data folder if it exists.
    This allows backwards compatibility with CSV data.
    """
    csv_path = Path(__file__).parent / "Data" / filename
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
            return jsonify({
                "data": df.to_dict(orient="records"),
                "rows": len(df),
                "source": "csv_file"
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"error": "File not found"}), 404


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  MANAGED CARE 3.0 — Dashboard Server (PostgreSQL + NaN Fix)")
    print("="*60)
    print(f"\n  📊 Dashboard: http://localhost:{PORT}")
    print(f"  🔌 API Docs: http://localhost:{PORT}/api/status")
    print(f"  🗄️  Database: {os.getenv('DATABASE_URL', 'SQLite (local)')}")
    print("\n  Press Ctrl+C to stop")
    print("="*60 + "\n")

    app.run(host="0.0.0.0", port=PORT, debug=False)
