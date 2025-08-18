import asyncio
from app.db.postgres_client import get_db_connection

SQL_CALENDAR_INTEGRATIONS = """
CREATE TABLE IF NOT EXISTS notification_logs (
    id VARCHAR(255) PRIMARY KEY,
    company_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    notification_type VARCHAR(100) NOT NULL, -- booking_confirmation, meeting_reminder, cancellation_notice
    recipient_email VARCHAR(255) NOT NULL,
    booking_id VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    sent_at TIMESTAMP NOT NULL,
    delivery_status VARCHAR(50) DEFAULT 'sent', -- sent, delivered, failed, bounced
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
"""

SQL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_notification_logs_company_id ON notification_logs(company_id);
CREATE INDEX IF NOT EXISTS idx_notification_logs_booking_id ON notification_logs(booking_id);
CREATE INDEX IF NOT EXISTS idx_notification_logs_type ON notification_logs(notification_type);
CREATE INDEX IF NOT EXISTS idx_notification_logs_sent_at ON notification_logs(sent_at);
"""

async def create_calendar_tables() -> None:
    async with await get_db_connection() as conn:
        await conn.execute(SQL_CALENDAR_INTEGRATIONS)
        print("✅ Call_Status table created")
        
        #await conn.execute(SQL_INDEXES)
        #print("✅ Calendar indexes created")
    
    print("\n🎉 Calendar integration tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_calendar_tables())