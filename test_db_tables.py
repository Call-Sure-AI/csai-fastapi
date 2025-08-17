import asyncio
from app.db.postgres_client import get_db_connection

SQL_CALENDAR_INTEGRATIONS = """
DROP TABLE IF EXISTS booking CASCADE;

CREATE TABLE booking (
    id VARCHAR(255) PRIMARY KEY,
    campaign_id VARCHAR(255) NOT NULL,
    customer VARCHAR(255) NOT NULL,
    slot_start TIMESTAMP NOT NULL,
    slot_end TIMESTAMP NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    customer_email VARCHAR(255),
    customer_phone VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

"""

SQL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_booking_campaign ON booking(campaign_id);
CREATE INDEX IF NOT EXISTS idx_booking_status ON booking(status);
CREATE INDEX IF NOT EXISTS idx_booking_slot_times ON booking(slot_start, slot_end);
"""

async def create_calendar_tables() -> None:
    async with await get_db_connection() as conn:
        await conn.execute(SQL_CALENDAR_INTEGRATIONS)
        print("✅ calendar_integrations table created")
        
        await conn.execute(SQL_INDEXES)
        print("✅ Calendar indexes created")
    
    print("\n🎉 Calendar integration tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_calendar_tables())