# scripts/fix_database_schema.py
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.postgres_client import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_existing_tables():
    """Check what tables and columns already exist"""
    async with await get_db_connection() as conn:
        # Check if leads table exists and its structure
        leads_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'leads'
            )
        """)
        
        if leads_exists:
            # Get column info
            columns = await conn.fetch("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'leads'
                ORDER BY ordinal_position
            """)
            
            logger.info("Existing leads table columns:")
            for col in columns:
                logger.info(f"  - {col['column_name']}: {col['data_type']}")
            
            return True, columns
        
        return False, []

async def drop_and_recreate_tables():
    """Drop existing tables and recreate with correct schema"""
    async with await get_db_connection() as conn:
        try:
            logger.info("Dropping existing tables if they exist...")
            
            # Drop dependent tables first
            drop_tables = [
                "DROP TABLE IF EXISTS lead_integration_sources CASCADE",
                "DROP TABLE IF EXISTS lead_call_logs CASCADE",
                "DROP TABLE IF EXISTS lead_whatsapp_data CASCADE",
                "DROP TABLE IF EXISTS lead_pool_members CASCADE",
                "DROP TABLE IF EXISTS company_lead_pools CASCADE",
                "DROP TABLE IF EXISTS lead_agent_interactions CASCADE",
                "DROP TABLE IF EXISTS lead_distribution_history CASCADE",
                "DROP TABLE IF EXISTS lead_score_history CASCADE",
                "DROP TABLE IF EXISTS lead_nurturing_enrollment CASCADE",
                "DROP TABLE IF EXISTS nurturing_campaigns CASCADE",
                "DROP TABLE IF EXISTS lead_events CASCADE",
                "DROP TABLE IF EXISTS lead_segment_members CASCADE",
                "DROP TABLE IF EXISTS lead_segments CASCADE",
                "DROP TABLE IF EXISTS campaign_leads CASCADE",
                "DROP TABLE IF EXISTS leads CASCADE"
            ]
            
            for drop_query in drop_tables:
                await conn.execute(drop_query)
                logger.info(f"  ✓ {drop_query.split()[4]}")
            
            logger.info("\nCreating tables with correct schema...")
            
            # 1. Create leads table with VARCHAR ID (to match your existing pattern)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id VARCHAR(255) PRIMARY KEY,
                    company_id VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    first_name VARCHAR(100),
                    last_name VARCHAR(100),
                    phone VARCHAR(50),
                    lead_company VARCHAR(255),
                    job_title VARCHAR(255),
                    industry VARCHAR(100),
                    country VARCHAR(100),
                    city VARCHAR(100),
                    state VARCHAR(100),
                    source VARCHAR(50) NOT NULL DEFAULT 'api',
                    source_integration_id VARCHAR(255),
                    status VARCHAR(50) NOT NULL DEFAULT 'new',
                    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
                    score INTEGER DEFAULT 0 CHECK (score >= 0 AND score <= 100),
                    tags JSONB DEFAULT '[]'::jsonb,
                    custom_fields JSONB DEFAULT '{}'::jsonb,
                    assigned_to VARCHAR(255),
                    assigned_agent_id VARCHAR(255),
                    created_by VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    last_contacted_at TIMESTAMP WITH TIME ZONE,
                    converted_at TIMESTAMP WITH TIME ZONE,
                    UNIQUE(company_id, email)
                );
            """)
            logger.info("✓ Created leads table")

            # 2. Campaign-Lead association table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS campaign_leads (
                    id VARCHAR(255) PRIMARY KEY,
                    campaign_id VARCHAR(255) NOT NULL REFERENCES Campaign(id) ON DELETE CASCADE,
                    lead_id VARCHAR(255) NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                    campaign_status VARCHAR(50) DEFAULT 'pending',
                    call_attempts INTEGER DEFAULT 0,
                    last_call_at TIMESTAMP WITH TIME ZONE,
                    email_attempts INTEGER DEFAULT 0,
                    last_email_at TIMESTAMP WITH TIME ZONE,
                    campaign_custom_fields JSONB DEFAULT '{}'::jsonb,
                    added_to_campaign_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    removed_from_campaign_at TIMESTAMP WITH TIME ZONE,
                    campaign_converted_at TIMESTAMP WITH TIME ZONE,
                    UNIQUE(campaign_id, lead_id)
                );
            """)
            logger.info("✓ Created campaign_leads table")

            # 3. Lead segments table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_segments (
                    id VARCHAR(255) PRIMARY KEY,
                    company_id VARCHAR(255) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    criteria JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(255)
                );
            """)
            logger.info("✓ Created lead_segments table")

            # 4. Lead segment members
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_segment_members (
                    lead_id VARCHAR(255) REFERENCES leads(id) ON DELETE CASCADE,
                    segment_id VARCHAR(255) REFERENCES lead_segments(id) ON DELETE CASCADE,
                    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (lead_id, segment_id)
                );
            """)
            logger.info("✓ Created lead_segment_members table")

            # 5. Lead events table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_events (
                    id VARCHAR(255) PRIMARY KEY,
                    lead_id VARCHAR(255) REFERENCES leads(id) ON DELETE CASCADE,
                    campaign_id VARCHAR(255) REFERENCES Campaign(id) ON DELETE SET NULL,
                    agent_id VARCHAR(255),
                    integration_id VARCHAR(255),
                    event_type VARCHAR(100) NOT NULL,
                    event_data JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(255)
                );
            """)
            logger.info("✓ Created lead_events table")

            # 6. Nurturing campaigns table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS nurturing_campaigns (
                    id VARCHAR(255) PRIMARY KEY,
                    company_id VARCHAR(255) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    trigger VARCHAR(50) NOT NULL,
                    schedule JSONB,
                    steps JSONB NOT NULL,
                    active BOOLEAN DEFAULT true,
                    sales_campaign_id VARCHAR(255) REFERENCES Campaign(id) ON DELETE SET NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by VARCHAR(255)
                );
            """)
            logger.info("✓ Created nurturing_campaigns table")

            # Create indexes
            await create_indexes(conn)
            
            logger.info("\n✅ All tables recreated successfully with correct schema!")
            
        except Exception as e:
            logger.error(f"Error recreating tables: {e}")
            raise

async def create_indexes(conn):
    """Create indexes for the tables"""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_leads_company_id ON leads(company_id)",
        "CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(company_id, LOWER(email))",
        "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)",
        "CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source)",
        "CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority)",
        "CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score)",
        "CREATE INDEX IF NOT EXISTS idx_leads_assigned_to ON leads(assigned_to)",
        "CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC)",
        
        "CREATE INDEX IF NOT EXISTS idx_campaign_leads_campaign ON campaign_leads(campaign_id)",
        "CREATE INDEX IF NOT EXISTS idx_campaign_leads_lead ON campaign_leads(lead_id)",
        "CREATE INDEX IF NOT EXISTS idx_campaign_leads_status ON campaign_leads(campaign_status)",
        
        "CREATE INDEX IF NOT EXISTS idx_lead_events_lead_id ON lead_events(lead_id)",
        "CREATE INDEX IF NOT EXISTS idx_lead_events_campaign_id ON lead_events(campaign_id)",
        "CREATE INDEX IF NOT EXISTS idx_lead_events_type ON lead_events(event_type)",
    ]
    
    for index in indexes:
        await conn.execute(index)
    
    logger.info("✓ Created all indexes")

async def migrate_campaign_leads():
    """Migrate Campaign_Lead data to new structure"""
    async with await get_db_connection() as conn:
        try:
            async with conn.transaction():
                logger.info("\nMigrating Campaign_Lead data...")
                
                # Get all campaigns
                campaigns = await conn.fetch("SELECT id, company_id FROM Campaign")
                
                total_migrated = 0
                total_associations = 0
                
                for campaign in campaigns:
                    campaign_id = campaign['id']
                    company_id = campaign['company_id']
                    
                    # Get leads from Campaign_Lead
                    campaign_leads = await conn.fetch("""
                        SELECT * FROM Campaign_Lead WHERE campaign_id = $1
                    """, campaign_id)
                    
                    for lead in campaign_leads:
                        if not lead['email']:
                            continue
                        
                        # Generate new lead ID
                        lead_id = f"LEAD-{lead['id'].split('-')[1]}" if 'LEAD-' in lead['id'] else f"LEAD-{lead['id'][:8].upper()}"
                        
                        # Check if lead exists
                        existing = await conn.fetchrow("""
                            SELECT id FROM leads 
                            WHERE company_id = $1 AND LOWER(email) = LOWER($2)
                        """, company_id, lead['email'])
                        
                        if not existing:
                            # Insert into leads table
                            await conn.execute("""
                                INSERT INTO leads (
                                    id, company_id, email, first_name, last_name, 
                                    phone, lead_company, custom_fields, source, status,
                                    created_at, updated_at
                                ) VALUES (
                                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                                ) ON CONFLICT (company_id, email) DO NOTHING
                            """,
                                lead_id, company_id, lead['email'].lower(),
                                lead['first_name'], lead['last_name'],
                                lead['phone'], lead['company'],
                                lead['custom_fields'], 'campaign_import', 'new',
                                lead['created_at'], lead['updated_at']
                            )
                            total_migrated += 1
                        else:
                            lead_id = existing['id']
                        
                        # Create campaign association
                        assoc_id = f"CL-{campaign_id[-8:]}-{lead_id[-8:]}"
                        existing_assoc = await conn.fetchrow("""
                            SELECT id FROM campaign_leads 
                            WHERE campaign_id = $1 AND lead_id = $2
                        """, campaign_id, lead_id)
                        
                        if not existing_assoc:
                            await conn.execute("""
                                INSERT INTO campaign_leads (
                                    id, campaign_id, lead_id, campaign_status,
                                    call_attempts, last_call_at, campaign_custom_fields,
                                    added_to_campaign_at
                                ) VALUES (
                                    $1, $2, $3, $4, $5, $6, $7, $8
                                ) ON CONFLICT (campaign_id, lead_id) DO NOTHING
                            """,
                                assoc_id, campaign_id, lead_id,
                                lead.get('status', 'pending'),
                                lead.get('call_attempts', 0),
                                lead.get('last_call_at'),
                                lead.get('custom_fields', {}),
                                lead['created_at']
                            )
                            total_associations += 1
                
                logger.info(f"✅ Migration completed!")
                logger.info(f"   - Leads migrated: {total_migrated}")
                logger.info(f"   - Associations created: {total_associations}")
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise

async def main():
    try:
        # Check existing tables
        exists, columns = await check_existing_tables()
        
        if exists:
            logger.info("\n⚠️  Leads table already exists with incompatible schema")
            response = input("Do you want to drop and recreate all lead management tables? (yes/no): ")
            
            if response.lower() == 'yes':
                await drop_and_recreate_tables()
                await migrate_campaign_leads()
            else:
                logger.info("Aborted. Please manually fix the schema or backup your data first.")
        else:
            logger.info("No existing leads table found. Creating fresh schema...")
            await drop_and_recreate_tables()
            await migrate_campaign_leads()
            
    except Exception as e:
        logger.error(f"Failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())