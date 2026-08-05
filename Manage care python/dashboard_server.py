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

    # Convert NaN to None for JSON serialization
    df = df.where(pd.notna(df), None)

    # Convert to JSON-serializable format
    data = df.to_dict(orient="records")
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
        summary["numeric_stats"][col] = {
            "mean": float(df[col].mean()),
            "min": float(df[col].min()),
            "max": float(df[col].max()),
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
