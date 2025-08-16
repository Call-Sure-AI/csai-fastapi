import asyncio
from app.db.postgres_client import get_db_connection

async def create_analytics_tables():
    async with await get_db_connection() as conn:
        await conn.execute("""
            CREATE VIEW v_campaign_realtime AS
            SELECT
                campaign_id,
                calls_handled,
                calls_success,
                bookings_made,
                revenue_generated,
                updated_at
            FROM campaign_metrics_current;

            CREATE TABLE IF NOT EXISTS campaign_metrics_daily (
                campaign_id  VARCHAR(255),
                date         DATE,
                calls_handled INT,
                calls_success INT,
                bookings_made INT,
                revenue_generated NUMERIC,
                PRIMARY KEY (campaign_id, date)
            );

            CREATE TABLE IF NOT EXISTS call_log (
                id           SERIAL PRIMARY KEY,
                campaign_id  VARCHAR(255),
                agent_id     VARCHAR(255),
                customer     VARCHAR(255),
                outcome      VARCHAR(50),
                duration_sec INT,
                started_at   TIMESTAMP,
                recorded_url TEXT
            );

            CREATE TABLE IF NOT EXISTS booking (
                id           SERIAL PRIMARY KEY,
                campaign_id  VARCHAR(255),
                customer     VARCHAR(255),
                slot_start   TIMESTAMP,
                slot_end     TIMESTAMP,
                status       VARCHAR(20),   -- confirmed / cancelled …
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    
    print("Analytics tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_analytics_tables())
