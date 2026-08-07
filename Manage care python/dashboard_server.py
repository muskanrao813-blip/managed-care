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
    """Health check endpoint for Render"""
    return jsonify({
        "status": "ok",
        "database": "connected" if read_table else "not_initialized",
        "port": PORT
    })


@app.route("/api/insights")
def get_insights():
    """Generate data-driven recommendations based on static rules"""
    recommendations = []

    try:
        # Load dashboard data
        appts = read_table("vytal_appt_flat") if read_table else None
        cohorts = read_table("impact_scores") if read_table else None
        policy = read_table("policy_data") if read_table else None

        if appts is None or appts.empty:
            return jsonify({"recommendations": [], "error": "No appointment data available"}), 200

        # Calculate key metrics
        total_appts = len(appts)
        completed = len(appts[appts['status'] == 'COM']) if 'status' in appts.columns else 0
        cancelled = len(appts[appts['status'] == 'CANCELLED']) if 'status' in appts.columns else 0
        booked = len(appts[appts['status'] == 'BOOKED']) if 'status' in appts.columns else 0

        # Service type breakdown
        diet_total = len(appts[appts['speciality'] == 'Diet']) if 'speciality' in appts.columns else 0
        diet_completed = len(appts[(appts['speciality'] == 'Diet') & (appts['status'] == 'COM')]) if 'speciality' in appts.columns and 'status' in appts.columns else 0
        doctor_total = len(appts[appts['speciality'] != 'Diet']) if 'speciality' in appts.columns else 0
        doctor_completed = len(appts[(appts['speciality'] != 'Diet') & (appts['status'] == 'COM')]) if 'speciality' in appts.columns and 'status' in appts.columns else 0

        diet_completion_rate = (diet_completed / diet_total * 100) if diet_total > 0 else 0
        doctor_completion_rate = (doctor_completed / doctor_total * 100) if doctor_total > 0 else 0
        overall_completion_rate = (completed / total_appts * 100) if total_appts > 0 else 0
        cancellation_rate = (cancelled / total_appts * 100) if total_appts > 0 else 0

        # Cohort distribution
        cohort_counts = {}
        if cohorts is not None and 'cohort' in cohorts.columns:
            cohort_counts = cohorts['cohort'].value_counts().to_dict()

        enrolled_users = len(policy) if policy is not None else len(cohorts) if cohorts is not None else 0
        zero_appt_users = enrolled_users - len(appts['phr_id'].unique()) if 'phr_id' in appts.columns else 0
        zero_appt_rate = (zero_appt_users / enrolled_users * 100) if enrolled_users > 0 else 0

        # Rule 1: Service Type Performance
        if doctor_completion_rate < 40 and diet_completion_rate > 85:
            recommendations.append({
                "priority": "high",
                "category": "Service Quality",
                "title": "Doctor Appointments Underperforming",
                "description": f"Diet completion rate is {diet_completion_rate:.1f}% but Doctor completion is only {doctor_completion_rate:.1f}%. Investigate appointment barriers and no-show reasons.",
                "action": "Review doctor appointment process, identify cancellation drivers",
                "metric": f"Diet: {diet_completion_rate:.1f}% vs Doctor: {doctor_completion_rate:.1f}%"
            })

        # Rule 2: Cohort Risk Management - Missing cohort
        very_high_count = cohort_counts.get('Very High', 0)
        missing_count = cohort_counts.get('missing', 0)
        total_cohort = sum(cohort_counts.values()) if cohort_counts else 0
        missing_rate = (missing_count / total_cohort * 100) if total_cohort > 0 else 0

        if missing_rate > 50:
            recommendations.append({
                "priority": "high",
                "category": "Risk Management",
                "title": "Incomplete Risk Assessment",
                "description": f"{missing_rate:.1f}% of users have not been risk-classified. Prioritize cohort assessment to enable targeted interventions.",
                "action": "Launch cohort risk assessment campaign for unclassified users",
                "metric": f"{missing_count} unclassified out of {total_cohort} users"
            })

        # Rule 3: Very High Risk Cohort Intervention
        very_high_rate = (very_high_count / total_cohort * 100) if total_cohort > 0 else 0
        if very_high_rate > 30:
            recommendations.append({
                "priority": "high",
                "category": "Clinical Intervention",
                "title": "High-Risk Segment Requires Intensive Intervention",
                "description": f"{very_high_rate:.1f}% of users are in Very High risk cohort. Recommend intensive intervention including frequent dietician consultations and device allocation.",
                "action": "Prioritize very high-risk users for device allocation and weekly follow-ups",
                "metric": f"{very_high_count} very high-risk users"
            })

        # Rule 4: Engagement Gaps - Zero Appointment Users
        if zero_appt_rate > 80:
            recommendations.append({
                "priority": "critical",
                "category": "Engagement",
                "title": "Majority of Enrolled Users Have No Appointments",
                "description": f"{zero_appt_rate:.1f}% of enrolled users have not booked any appointments. Launch engagement campaign to improve program awareness and accessibility.",
                "action": "Increase marketing outreach, simplify appointment booking, offer incentives",
                "metric": f"{zero_appt_users:,} users with zero appointments"
            })

        # Rule 5: Cancellation Rate Monitoring
        if cancellation_rate > 10:
            recommendations.append({
                "priority": "medium",
                "category": "Quality Monitoring",
                "title": "High Cancellation Rate Detected",
                "description": f"Cancellation rate is {cancellation_rate:.1f}%. Investigate reasons (scheduling conflicts, accessibility, user preference) and implement retention strategies.",
                "action": "Analyze cancellation patterns, offer rescheduling reminders, improve slot availability",
                "metric": f"{cancelled} cancellations out of {total_appts} appointments"
            })

        # Rule 6: Completion Rate Target
        if overall_completion_rate < 75:
            recommendations.append({
                "priority": "medium",
                "category": "Quality Monitoring",
                "title": "Appointment Completion Below Target",
                "description": f"Current completion rate is {overall_completion_rate:.1f}%. Target is 75%+. Enhance follow-up protocols and reminders.",
                "action": "Implement SMS/WhatsApp reminders, track no-shows, follow up with incomplete users",
                "metric": f"{completed} completed out of {total_appts} appointments"
            })

        # Rule 7: Booked Appointment Pipeline
        if booked < total_appts * 0.05:
            recommendations.append({
                "priority": "medium",
                "category": "Capacity Planning",
                "title": "Low Booked Appointment Pipeline",
                "description": f"Only {booked} appointments are currently booked ({booked/total_appts*100:.1f}%). Ensure adequate appointment slots to meet demand.",
                "action": "Increase dietician and doctor appointment availability for next 30 days",
                "metric": f"{booked} booked appointments (< 5% of total)"
            })

        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        recommendations.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 4))

        return jsonify({
            "recommendations": recommendations,
            "metrics": {
                "total_appointments": total_appts,
                "completed": completed,
                "completion_rate": round(overall_completion_rate, 1),
                "cancellation_rate": round(cancellation_rate, 1),
                "diet_completion": round(diet_completion_rate, 1),
                "doctor_completion": round(doctor_completion_rate, 1),
                "zero_appointment_users": zero_appt_users,
                "zero_appointment_rate": round(zero_appt_rate, 1)
            }
        }), 200

    except Exception as e:
        print(f"Error generating insights: {e}")
        return jsonify({"recommendations": [], "error": str(e)}), 500


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
