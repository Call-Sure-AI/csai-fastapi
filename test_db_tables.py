
import asyncio
from app.db.postgres_client import get_db_connection


SQL_METRICS_CURRENT = """
CREATE TABLE IF NOT EXISTS campaign_metrics_current (
    campaign_id       VARCHAR(255) PRIMARY KEY,
    calls_handled     INT DEFAULT 0,
    calls_success     INT DEFAULT 0,
    bookings_made     INT DEFAULT 0,
    revenue_generated NUMERIC DEFAULT 0,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SQL_VIEW = """
CREATE OR REPLACE VIEW v_campaign_realtime AS
SELECT
    campaign_id,
    calls_handled,
    calls_success,
    bookings_made,
    revenue_generated,
    updated_at
FROM campaign_metrics_current;
"""

SQL_METRICS_DAILY = """
CREATE TABLE IF NOT EXISTS campaign_metrics_daily (
    campaign_id        VARCHAR(255),
    date               DATE,
    calls_handled      INT,
    calls_success      INT,
    bookings_made      INT,
    revenue_generated  NUMERIC,
    PRIMARY KEY (campaign_id, date)
);
"""

SQL_CALL_LOG = """
CREATE TABLE IF NOT EXISTS call_log (
    id            SERIAL PRIMARY KEY,
    campaign_id   VARCHAR(255),
    agent_id      VARCHAR(255),
    customer      VARCHAR(255),
    outcome       VARCHAR(50),
    duration_sec  INT,
    started_at    TIMESTAMP,
    recorded_url  TEXT
);
"""

SQL_BOOKING = """
CREATE TABLE IF NOT EXISTS booking (
    id           SERIAL PRIMARY KEY,
    campaign_id  VARCHAR(255),
    customer     VARCHAR(255),
    slot_start   TIMESTAMP,
    slot_end     TIMESTAMP,
    status       VARCHAR(20),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

SQL_MOCK_DATA = """
INSERT INTO campaign_metrics_current (
    campaign_id, calls_handled, calls_success, bookings_made, revenue_generated
) VALUES 
    ('CAMP-FD14E400', 150, 120, 45, 6750.50),
    ('CAMP-CE7C5E80', 89, 72, 28, 4200.00)
ON CONFLICT (campaign_id) DO UPDATE SET
    calls_handled = EXCLUDED.calls_handled,
    calls_success = EXCLUDED.calls_success,
    bookings_made = EXCLUDED.bookings_made,
    revenue_generated = EXCLUDED.revenue_generated,
    updated_at = NOW();
"""


async def create_analytics_tables() -> None:
    async with await get_db_connection() as conn:
        # 1. Create base metrics table first
        await conn.execute(SQL_METRICS_CURRENT)
        print("✅ campaign_metrics_current table created")
        
        # 2. Create view that depends on metrics table
        await conn.execute(SQL_VIEW)
        print("✅ v_campaign_realtime view created")
        
        # 3. Create other tables
        await conn.execute(SQL_METRICS_DAILY)
        print("✅ campaign_metrics_daily table created")
        
        await conn.execute(SQL_CALL_LOG)
        print("✅ call_log table created")
        
        await conn.execute(SQL_BOOKING)
        print("✅ booking table created")
        
        # 4. Insert sample data for testing
        await conn.execute(SQL_MOCK_DATA)
        print("✅ Mock data inserted")

    print("\n🎉 All analytics tables & view created successfully!")


if __name__ == "__main__":
    asyncio.run(create_analytics_tables())