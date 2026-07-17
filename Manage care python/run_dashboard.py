"""
============================================================
MANAGED CARE 3.0 — Dashboard Server
============================================================
Run this script to open the dashboard with live CSV data.

Run: python run_dashboard.py
Then open: http://localhost:8000
============================================================
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import http.server
import socketserver
import webbrowser
import os
from datetime import datetime
import threading


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Serve each request in a new thread so concurrent CSV fetches don't queue."""
    allow_reuse_address = True
    daemon_threads = True

# ── CONFIG ────────────────────────────────────────────────
PORT = 8001

# Serve files from this script's folder
SERVE_DIR = os.path.dirname(os.path.abspath(__file__))

# Dashboard file name — serve v3 (sidebar with date/year selectors)
DASHBOARD_FILE = "managed_care_dashboard_v3.html"
if not os.path.exists(os.path.join(SERVE_DIR, DASHBOARD_FILE)):
    for alt in ["managed_care_dashboard_final.html", "managed_care_dashboard.html"]:
        if os.path.exists(os.path.join(SERVE_DIR, alt)):
            DASHBOARD_FILE = alt
            print(f"  Using fallback dashboard file: {alt}")
            break
# ─────────────────────────────────────────────────────────


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    def end_headers(self):
        # Prevent browser caching so CSV updates always reflect immediately
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def log_message(self, format, *args):
        if args[1] not in ('200', '304'):
            print(f"  {args[0]} {args[1]}")


if __name__ == "__main__":
    os.chdir(SERVE_DIR)

    print("\n" + "="*55)
    print("  MANAGED CARE 3.0 — Dashboard Server")
    print("="*55)
    print(f"\n  Serving from: {SERVE_DIR}")
    print(f"  Dashboard   : http://localhost:{PORT}/{DASHBOARD_FILE}")
    print(f"  Data folder : {os.path.join(SERVE_DIR, 'Data')}")
    print("\n  Press Ctrl+C to stop the server")
    print("="*55)

    # Check HTML exists in serve directory
    html_path = os.path.join(SERVE_DIR, DASHBOARD_FILE)
    if not os.path.exists(html_path):
        print(f"\n  ❌ Dashboard HTML not found at: {html_path}")
        print(f"  ➡  Copy managed_care_dashboard_final.html into:")
        print(f"     {SERVE_DIR}")
        print(f"\n  Opening folder listing instead: http://localhost:{PORT}")
        DASHBOARD_FILE_OPEN = ''
    else:
        print(f"  ✅ Dashboard found: {html_path}")
        DASHBOARD_FILE_OPEN = DASHBOARD_FILE

    # Auto-detect data folder (handles Data/ data/ DATA/ variations)
    data_dir = None
    for candidate in ["Data", "data", "DATA"]:
        candidate_path = os.path.join(SERVE_DIR, candidate)
        if os.path.isdir(candidate_path):
            data_dir = candidate_path
            print(f"\n  ✅ Data folder found: {candidate_path}")
            break

    if data_dir is None:
        print(f"\n  ❌ No data folder found in: {SERVE_DIR}")
        print(f"     Create a 'Data' folder there and run the scripts first.")
        data_dir = os.path.join(SERVE_DIR, "Data")

    # Check what folder name was found and update HTML DATA_FOLDER if needed
    folder_name = os.path.basename(data_dir)
    html_path_check = os.path.join(SERVE_DIR, DASHBOARD_FILE)
    if os.path.exists(html_path_check):
        with open(html_path_check, 'r', encoding='utf-8') as hf:
            html_content = hf.read()
        # Fix DATA_FOLDER in HTML to match actual folder name
        import re
        current = re.search(r"const DATA_FOLDER = '(.*?)';", html_content)
        correct  = f"'./{folder_name}/'"
        if current and current.group(1) != f"./{folder_name}/":
            html_content = re.sub(
                r"const DATA_FOLDER = '.*?';",
                f"const DATA_FOLDER = './{folder_name}/';",
                html_content
            )
            with open(html_path_check, 'w', encoding='utf-8') as hf:
                hf.write(html_content)
            print(f"  ✅ DATA_FOLDER in HTML updated to './{folder_name}/'")

    expected = [
        "managed_care_program_allocation.csv",
        "managed_care_impact_scores.csv",
        "managed_care_comparison.csv",
        "managed_care_device_eligibility.csv",
        "claude_insights.json",
    ]
    print("\n  CSV / JSON status:")
    all_found = True
    for fname in expected:
        path = os.path.join(data_dir, fname)
        if os.path.exists(path):
            size = os.path.getsize(path)
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
            print(f"    ✅ {fname:<45} {size:>10,} bytes  (updated {mtime})")
        else:
            required = fname != "claude_insights.json"
            print(f"    {'❌' if required else '⚠️ '} {fname} — {'NOT FOUND — run scripts first' if required else 'optional — run Script 4'}")
            if required: all_found = False

    if not all_found:
        print("\n  ⚠️  Some required CSVs missing. Run scripts 01-03 first.")
    else:
        print("\n  ✅ All required CSVs found — dashboard will show live data")

    print(f"\n  Full paths being served:")
    print(f"    HTML : {os.path.join(SERVE_DIR, DASHBOARD_FILE)}")
    print(f"    Data : {data_dir}")

    # Start server — try ports 8000-8010 if one is busy
    httpd = None
    for port in range(8000, 8010):
        try:
            httpd = ThreadedTCPServer(("", port), Handler)
            PORT = port
            break
        except OSError:
            print(f"  Port {port} busy, trying {port+1}...")

    if httpd is None:
        print("  ❌ Could not find a free port. Close other terminals and retry.")
        raise SystemExit(1)

    url = f"http://localhost:{PORT}/{DASHBOARD_FILE_OPEN}"
    print(f"\n  ✅ Server started at: http://localhost:{PORT}")
    print(f"  Dashboard : {url}")
    print(f"  Debug page: http://localhost:{PORT}/debug.html")
    print(f"\n  Files in scripts folder:")
    for f in sorted(os.listdir(SERVE_DIR)):
        if f.endswith(('.html','.py','.json')) and not f.startswith('.'):
            print(f"    {f}")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  Server stopped.")
    finally:
        httpd.server_close()
