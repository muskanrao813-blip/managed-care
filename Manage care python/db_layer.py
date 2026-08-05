"""
PostgreSQL Database Layer for Managed Care Dashboard
Stores all CSV data in PostgreSQL instead of local files.
Supports both local development (SQLite) and production (PostgreSQL on Render).
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, Float, Integer, DateTime, inspect
from datetime import datetime
from pathlib import Path


def get_db_url():
    """Get database URL from environment or use SQLite for local dev"""
    if db_url := os.getenv("DATABASE_URL"):
        return db_url
    # Local development: use SQLite
    db_path = Path(__file__).parent / "dashboard_data.db"
    return f"sqlite:///{db_path}"


engine = create_engine(get_db_url(), pool_pre_ping=True)


def init_schema():
    """Create all tables if they don't exist"""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS programme_allocation (
                id SERIAL PRIMARY KEY,
                phr_id VARCHAR(255),
                mobile_hash VARCHAR(255),
                programme VARCHAR(100),
                cohort VARCHAR(50),
                normalized_score FLOAT,
                scaled_score FLOAT,
                camp_year VARCHAR(10),
                camp_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS comparison_retest (
                id SERIAL PRIMARY KEY,
                phr_id VARCHAR(255),
                programme VARCHAR(100),
                improvement_flag VARCHAR(20),
                score_change FLOAT,
                camp_year_earliest VARCHAR(10),
                camp_year_latest VARCHAR(10),
                earliest_score FLOAT,
                latest_score FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS device_eligibility (
                id SERIAL PRIMARY KEY,
                phr_id VARCHAR(255),
                device_type VARCHAR(100),
                is_eligible BOOLEAN,
                eligibility_reason VARCHAR(255),
                engagement_score FLOAT,
                camp_year VARCHAR(10),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dashboard_cache (
                id SERIAL PRIMARY KEY,
                section_name VARCHAR(100),
                kpi_name VARCHAR(255),
                kpi_value VARCHAR(255),
                metric_data TEXT,
                cache_date DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))


def save_dataframe(df: pd.DataFrame, table_name: str, if_exists: str = "replace"):
    """
    Save DataFrame to database.

    Args:
        df: Pandas DataFrame
        table_name: Name of table to save to
        if_exists: 'fail', 'replace', 'append'
    """
    try:
        df.to_sql(table_name, engine, if_exists=if_exists, index=False)
        print(f"✓ Saved {len(df)} rows to {table_name}")
    except Exception as e:
        print(f"✗ Error saving to {table_name}: {e}")
        raise


def read_table(table_name: str, filters: dict = None) -> pd.DataFrame:
    """
    Read table from database.

    Args:
        table_name: Name of table to read
        filters: Optional dict of {column: value} for WHERE clause
    Returns:
        Pandas DataFrame
    """
    try:
        query = f"SELECT * FROM {table_name}"
        if filters:
            where_clauses = [f"{k}='{v}'" for k, v in filters.items()]
            query += " WHERE " + " AND ".join(where_clauses)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        print(f"✗ Error reading {table_name}: {e}")
        return pd.DataFrame()


def clear_table(table_name: str):
    """Clear all data from a table (used when refreshing daily data)"""
    try:
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {table_name}"))
        print(f"✓ Cleared {table_name}")
    except Exception as e:
        print(f"✗ Error clearing {table_name}: {e}")


def get_last_update(table_name: str) -> datetime:
    """Get timestamp of last data update for a table"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT MAX(updated_at) FROM {table_name}")).fetchone()
        return result[0] if result and result[0] else None
    except:
        return None


# Initialize schema on module load
try:
    init_schema()
except Exception as e:
    print(f"Warning: Could not initialize schema: {e}")
