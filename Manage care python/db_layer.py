"""
PostgreSQL Database Layer for Managed Care Dashboard
Connects to Neon PostgreSQL (shared with Dietician QA project)
Uses managed_care schema for organization.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# Neon PostgreSQL connection (shared database)
DATABASE_URL = os.getenv("DATABASE_URL",
    "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# All tables use managed_care schema
SCHEMA = "managed_care"

def qualified_table_name(name):
    """Return schema-qualified table name"""
    return f"{SCHEMA}.{name}"


def save_dataframe(df: pd.DataFrame, table_name: str, if_exists: str = "replace"):
    """
    Save DataFrame to managed_care schema.

    Args:
        df: Pandas DataFrame
        table_name: Table name (without schema prefix)
        if_exists: 'fail', 'replace', 'append'
    """
    try:
        # Fix: Convert phone columns to string (prevents "bigint out of range" error)
        for col in df.columns:
            if 'phone' in col.lower():
                df[col] = df[col].astype(str)

        q_name = qualified_table_name(table_name)
        print(f"[DB] Connecting to {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'unknown'}...")
        print(f"[DB] Saving {len(df)} rows to {q_name}...")
        df.to_sql(table_name, engine, schema=SCHEMA, if_exists=if_exists, index=False)
        print(f"[DB] SUCCESS: Saved {len(df)} rows to {q_name}")
    except Exception as e:
        q_name = qualified_table_name(table_name)
        print(f"[DB] FAILED saving to {q_name}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise


def read_table(table_name: str, filters: dict = None) -> pd.DataFrame:
    """
    Read table from managed_care schema.
    Returns empty DataFrame if table doesn't exist (graceful degradation).

    Args:
        table_name: Table name (without schema prefix)
        filters: Optional dict of {column: value} for WHERE clause
    Returns:
        Pandas DataFrame
    """
    try:
        q_name = qualified_table_name(table_name)
        query = f"SELECT * FROM {q_name}"
        if filters:
            where_clauses = [f"{k}='{v}'" for k, v in filters.items()]
            query += " WHERE " + " AND ".join(where_clauses)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        # Silently return empty DataFrame if table doesn't exist
        # (This is expected during early runs when not all tables are populated)
        return pd.DataFrame()


def clear_table(table_name: str):
    """Clear all data from a table (used when refreshing daily data)"""
    try:
        q_name = qualified_table_name(table_name)
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {q_name}"))
        print(f"✓ Cleared {q_name}")
    except Exception as e:
        q_name = qualified_table_name(table_name)
        print(f"✗ Error clearing {q_name}: {e}")


def get_last_update(table_name: str) -> datetime:
    """Get timestamp of last data update for a table"""
    try:
        q_name = qualified_table_name(table_name)
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT MAX(updated_at) FROM {q_name}")).fetchone()
        return result[0] if result and result[0] else None
    except:
        return None
