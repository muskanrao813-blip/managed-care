"""
Initialize Managed Care schema in Neon PostgreSQL
Run this ONCE to create the managed_care schema and tables.
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Use Neon connection string
DATABASE_URL = os.getenv("DATABASE_URL",
    "postgresql://neondb_owner:npg_RnjMpJ4DsKY7@ep-icy-tree-af8719ti.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require"
)

engine = create_engine(DATABASE_URL)

SCHEMA_SQL = """
-- Create managed_care schema
CREATE SCHEMA IF NOT EXISTS managed_care;

-- Programme Allocation
CREATE TABLE IF NOT EXISTS managed_care.programme_allocation (
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

-- Comparison & Retest
CREATE TABLE IF NOT EXISTS managed_care.comparison_retest (
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

-- Device Eligibility
CREATE TABLE IF NOT EXISTS managed_care.device_eligibility (
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

-- Dashboard Cache (AI Insights)
CREATE TABLE IF NOT EXISTS managed_care.dashboard_cache (
    id SERIAL PRIMARY KEY,
    section_name VARCHAR(100),
    kpi_name VARCHAR(255),
    kpi_value VARCHAR(255),
    metric_data TEXT,
    cache_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_prog_alloc_phr ON managed_care.programme_allocation(phr_id);
CREATE INDEX IF NOT EXISTS idx_prog_alloc_programme ON managed_care.programme_allocation(programme);
CREATE INDEX IF NOT EXISTS idx_comp_phr ON managed_care.comparison_retest(phr_id);
CREATE INDEX IF NOT EXISTS idx_device_phr ON managed_care.device_eligibility(phr_id);
CREATE INDEX IF NOT EXISTS idx_cache_section ON managed_care.dashboard_cache(section_name);

-- Grant public access (Render can connect)
GRANT USAGE ON SCHEMA managed_care TO PUBLIC;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA managed_care TO PUBLIC;
"""

def init_schema():
    """Initialize managed_care schema in Neon PostgreSQL"""
    try:
        with engine.begin() as conn:
            print("Creating managed_care schema...")
            for statement in SCHEMA_SQL.split(";"):
                if statement.strip():
                    conn.execute(text(statement))

        print("✓ Schema created successfully")

        # Verify tables
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='managed_care'"
            ))
            tables = result.fetchall()
            print(f"✓ Tables created: {len(tables)}")
            for table in tables:
                print(f"  - managed_care.{table[0]}")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  MANAGED CARE — Initialize Neon PostgreSQL Schema")
    print("="*60)
    print(f"\nDatabase: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'Neon'}")
    print("\n")

    if init_schema():
        print("\n" + "="*60)
        print("  ✓ Ready to use! Update db_config.py and run scripts.")
        print("="*60 + "\n")
    else:
        print("\n" + "="*60)
        print("  ✗ Schema creation failed. Check database connection.")
        print("="*60 + "\n")
