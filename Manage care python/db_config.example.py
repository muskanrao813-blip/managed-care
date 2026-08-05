"""
Database Configuration for Managed Care Scripts
Copy this file to db_config.py and fill in your connection details.

For Render: Get connection string from Render PostgreSQL service
For Local: Leave as-is to use SQLite
"""

import os

# ── OPTION 1: Use Environment Variable (Recommended for Render) ──
# Set DATABASE_URL in Render environment:
# postgresql://user:password@host:5432/managed_care
DATABASE_URL = os.getenv("DATABASE_URL", None)

# ── OPTION 2: Local SQLite (Development) ──
# Uncomment if no DATABASE_URL set:
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./dashboard_data.db"

# ── OPTION 3: PostgreSQL Connection Details (Local) ──
# Uncomment and fill in if you want to specify connection details:
# DATABASE_URL = "postgresql://username:password@localhost:5432/managed_care"

print(f"[DB] Using: {DATABASE_URL.split('@')[0] if '@' in DATABASE_URL else 'SQLite'}")
