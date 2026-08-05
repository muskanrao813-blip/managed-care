"""
Database Configuration for Managed Care Scripts
Uses Neon PostgreSQL (shared with Dietician QA project)
Connects to managed_care schema.
"""

import os

# ── Neon PostgreSQL (Production) ──
# Shared database with Dietician QA project
DATABASE_URL = os.getenv("DATABASE_URL",
    "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"
)

# ── Override with environment variable if needed ──
# export DATABASE_URL="postgresql://..."

print(f"[DB] Connected to Neon PostgreSQL (managed_care schema)")
