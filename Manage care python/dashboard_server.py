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


@app.route("/api/data/<table_name>")
def get_table_data(table_name):
    """
    Fetch data from database table as JSON.
    Usage: GET /api/data/programme_allocation
    """
    if not read_table:
        return jsonify({"error": "Database not initialized"}), 500

    try:
        df = read_table(table_name)
        if df.empty:
            return jsonify({"data": [], "rows": 0, "message": "No data"})

        # Convert to JSON-serializable format
        data = df.to_dict(orient="records")
        return jsonify({
            "data": data,
            "rows": len(data),
            "columns": list(df.columns),
            "last_updated": str(get_last_update(table_name))
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/data/<table_name>/summary")
def get_table_summary(table_name):
    """
    Get summary statistics for a table.
    Usage: GET /api/data/programme_allocation/summary
    """
    if not read_table:
        return jsonify({"error": "Database not initialized"}), 500

    try:
        df = read_table(table_name)
        if df.empty:
            return jsonify({"summary": {}})

        # Generate summary stats
        summary = {
            "total_rows": len(df),
            "columns": list(df.columns),
            "last_updated": str(get_last_update(table_name)),
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
    print("  MANAGED CARE 3.0 — Dashboard Server (PostgreSQL)")
    print("="*60)
    print(f"\n  📊 Dashboard: http://localhost:{PORT}")
    print(f"  🔌 API Docs: http://localhost:{PORT}/api/status")
    print(f"  🗄️  Database: {os.getenv('DATABASE_URL', 'SQLite (local)')}")
    print("\n  Press Ctrl+C to stop")
    print("="*60 + "\n")

    app.run(host="0.0.0.0", port=PORT, debug=False)
