# scripts\create_campaign_tables.py
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

            CREATE TABLE IF NOT EXISTS campaign_slot_configuration (
                id VARCHAR(255) PRIMARY KEY,
                campaign_id VARCHAR(255) REFERENCES Campaign(id) ON DELETE CASCADE,
                company_id VARCHAR(255) NOT NULL,
                
                -- Slot mode
                slot_mode VARCHAR(50) DEFAULT 'dynamic' CHECK (slot_mode IN ('predefined', 'dynamic', 'hybrid')),
                
                -- Business hours (JSONB format: {"mon": {"start": "09:00", "end": "18:00"}, ...})
                business_hours JSONB DEFAULT '{"mon": {"start": "09:00", "end": "18:00"}, "tue": {"start": "09:00", "end": "18:00"}, "wed": {"start": "09:00", "end": "18:00"}, "thu": {"start": "09:00", "end": "18:00"}, "fri": {"start": "09:00", "end": "18:00"}}'::jsonb,
                timezone VARCHAR(50) DEFAULT 'UTC',
                
                -- Slot settings
                slot_duration_minutes INTEGER DEFAULT 30,
                buffer_minutes INTEGER DEFAULT 0,
                
                -- Capacity management (CRITICAL for multiple closers)
                max_bookings_per_slot INTEGER DEFAULT 1,
                allow_overbooking BOOLEAN DEFAULT FALSE,
                
                -- Customization
                allow_custom_times BOOLEAN DEFAULT FALSE,
                
                -- Predefined slots (JSONB array: [{"day": "monday", "times": ["09:00", "11:00", "14:00"]}, ...])
                predefined_slots JSONB DEFAULT '[]'::jsonb,
                
                -- Closer/Agent assignments (JSONB: [{"closer_id": "user_123", "name": "John", "shifts": [{"day": "monday", "start": "09:00", "end": "18:00"}]}])
                closer_shifts JSONB DEFAULT '[]'::jsonb,
                
                -- Multiple bookings flag
                allow_multiple_bookings_per_customer BOOLEAN DEFAULT FALSE,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(campaign_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_slot_config_campaign ON campaign_slot_configuration(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_slot_config_company ON campaign_slot_configuration(company_id);
            CREATE INDEX IF NOT EXISTS idx_campaign_company_id ON Campaign(company_id);
            CREATE INDEX IF NOT EXISTS idx_campaign_lead_campaign_id ON Campaign_Lead(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_campaign_lead_status ON Campaign_Lead(status);
            CREATE INDEX IF NOT EXISTS idx_campaign_activity_campaign_id ON Campaign_Activity(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_campaign_activity_lead_id ON Campaign_Activity(lead_id);
        """)
    
    print("Campaign tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_campaign_tables())
