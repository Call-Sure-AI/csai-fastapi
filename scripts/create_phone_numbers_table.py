# scripts/create_phone_numbers_table.py
"""
Database migration script to create the phone_numbers table
Run this script to set up the phone numbers table in your PostgreSQL database
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

CREATE_TABLE_SQL = """
-- Phone Numbers Table
-- Stores phone numbers purchased from Twilio, Exotel, etc. and connected to agents

CREATE TABLE IF NOT EXISTS phone_numbers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Phone number details
    phone_number VARCHAR(20) NOT NULL,
    friendly_name VARCHAR(100),
    provider VARCHAR(20) NOT NULL CHECK (provider IN ('twilio', 'exotel', 'plivo')),
    provider_sid VARCHAR(100),
    
    -- Connection to agent (stored as string, no FK constraint)
    agent_id VARCHAR(100),
    agent_name VARCHAR(255),
    
    -- Company ownership (stored as string, no FK constraint)
    company_id VARCHAR(100) NOT NULL,
    
    -- Status and billing
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'pending', 'deleted')),
    monthly_cost DECIMAL(10, 2) DEFAULT 0.00,
    
    -- Location info
    country VARCHAR(5),
    region VARCHAR(100),
    locality VARCHAR(100),
    
    -- Capabilities
    capabilities JSONB DEFAULT '{"voice": true, "sms": false, "mms": false}',
    
    -- Provider credentials (should be encrypted in production)
    credentials JSONB,
    
    -- Webhook configuration
    voice_webhook_url TEXT,
    sms_webhook_url TEXT,
    
    -- Billing dates
    purchased_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    renews_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_phone_number_per_company UNIQUE (phone_number, company_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_phone_numbers_company_id ON phone_numbers(company_id);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_agent_id ON phone_numbers(agent_id);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_provider ON phone_numbers(provider);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_status ON phone_numbers(status);
CREATE INDEX IF NOT EXISTS idx_phone_numbers_phone ON phone_numbers(phone_number);

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_phone_numbers_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS phone_numbers_updated_at ON phone_numbers;
CREATE TRIGGER phone_numbers_updated_at
    BEFORE UPDATE ON phone_numbers
    FOR EACH ROW
    EXECUTE FUNCTION update_phone_numbers_updated_at();

-- Comments for documentation
COMMENT ON TABLE phone_numbers IS 'Stores phone numbers purchased from telephony providers and connected to AI agents';
COMMENT ON COLUMN phone_numbers.provider IS 'Telephony provider: twilio, exotel, or plivo';
COMMENT ON COLUMN phone_numbers.provider_sid IS 'Provider-specific identifier for the phone number';
COMMENT ON COLUMN phone_numbers.credentials IS 'Encrypted API credentials for the provider';
COMMENT ON COLUMN phone_numbers.capabilities IS 'Phone number capabilities: voice, sms, mms';
"""

DROP_TABLE_SQL = """
DROP TRIGGER IF EXISTS phone_numbers_updated_at ON phone_numbers;
DROP FUNCTION IF EXISTS update_phone_numbers_updated_at();
DROP TABLE IF EXISTS phone_numbers CASCADE;
"""


async def create_table():
    """Create the phone_numbers table"""
    print("Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        print("Creating phone_numbers table...")
        await conn.execute(CREATE_TABLE_SQL)
        print("✅ Table created successfully!")
        
        # Verify table exists
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'phone_numbers'
            )
        """)
        
        if result:
            print("✅ Verified: phone_numbers table exists")
            
            # Show table structure
            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'phone_numbers'
                ORDER BY ordinal_position
            """)
            
            print("\n📋 Table structure:")
            for col in columns:
                print(f"   - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
        
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        raise
    finally:
        await conn.close()


async def drop_table():
    """Drop the phone_numbers table"""
    print("Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        print("Dropping phone_numbers table...")
        await conn.execute(DROP_TABLE_SQL)
        print("✅ Table dropped successfully!")
        
    except Exception as e:
        print(f"❌ Error dropping table: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--drop":
        print("⚠️  WARNING: This will delete the phone_numbers table and all data!")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            asyncio.run(drop_table())
        else:
            print("Cancelled.")
    else:
        asyncio.run(create_table())