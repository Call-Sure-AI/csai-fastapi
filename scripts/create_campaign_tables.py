import asyncio
from app.db.postgres_client import get_db_connection

async def create_campaign_tables():
    async with await get_db_connection() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS Campaign (
                id VARCHAR(255) PRIMARY KEY,
                campaign_name VARCHAR(255) NOT NULL,
                description TEXT,
                company_id VARCHAR(255) NOT NULL,
                created_by VARCHAR(255) NOT NULL,
                status VARCHAR(50) DEFAULT 'active',
                leads_count INTEGER DEFAULT 0,
                csv_file_path TEXT,
                data_mapping JSONB,
                booking_config JSONB,
                automation_config JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS Campaign_Lead (
                id VARCHAR(255) PRIMARY KEY,
                campaign_id VARCHAR(255) REFERENCES Campaign(id) ON DELETE CASCADE,
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                email VARCHAR(255),
                phone VARCHAR(50),
                company VARCHAR(255),
                custom_fields JSONB DEFAULT '{}',
                call_attempts INTEGER DEFAULT 0,
                last_call_at TIMESTAMP,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS Campaign_Activity (
                id VARCHAR(255) PRIMARY KEY,
                campaign_id VARCHAR(255) REFERENCES Campaign(id) ON DELETE CASCADE,
                lead_id VARCHAR(255) REFERENCES Campaign_Lead(id) ON DELETE CASCADE,
                activity_type VARCHAR(50) NOT NULL, -- 'call', 'email', 'meeting_scheduled'
                status VARCHAR(50) NOT NULL, -- 'success', 'failed', 'pending'
                details JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_campaign_company_id ON Campaign(company_id);
            CREATE INDEX IF NOT EXISTS idx_campaign_lead_campaign_id ON Campaign_Lead(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_campaign_lead_status ON Campaign_Lead(status);
            CREATE INDEX IF NOT EXISTS idx_campaign_activity_campaign_id ON Campaign_Activity(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_campaign_activity_lead_id ON Campaign_Activity(lead_id);
        """)
    
    print("Campaign tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_campaign_tables())
