import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db.postgres_client import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_lead_management_tables():
    """Create all tables for the comprehensive lead management system"""
    
    async with await get_db_connection() as conn:
        try:
            # 1. Main leads table (master repository)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    company_id UUID NOT NULL,
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
                    source_integration_id UUID,
                    status VARCHAR(50) NOT NULL DEFAULT 'new',
                    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
                    score INTEGER DEFAULT 0 CHECK (score >= 0 AND score <= 100),
                    tags JSONB DEFAULT '[]'::jsonb,
                    custom_fields JSONB DEFAULT '{}'::jsonb,
                    assigned_to UUID,
                    assigned_agent_id UUID,
                    created_by UUID,
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
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    campaign_id VARCHAR(50) NOT NULL,
                    lead_id UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                    campaign_status VARCHAR(50) DEFAULT 'pending',
                    call_attempts INTEGER DEFAULT 0,
                    last_call_at TIMESTAMP WITH TIME ZONE,
                    email_attempts INTEGER DEFAULT 0,
                    last_email_at TIMESTAMP WITH TIME ZONE,
                    campaign_custom_fields JSONB DEFAULT '{}'::jsonb,
                    added_to_campaign_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    removed_from_campaign_at TIMESTAMP WITH TIME ZONE,
                    campaign_converted_at TIMESTAMP WITH TIME ZONE,
                    UNIQUE(campaign_id, lead_id),
                    FOREIGN KEY (campaign_id) REFERENCES Campaign(id) ON DELETE CASCADE
                );
            """)
            logger.info("✓ Created campaign_leads association table")

            # 3. Lead segments table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_segments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    company_id UUID NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    criteria JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by UUID
                );
            """)
            logger.info("✓ Created lead_segments table")

            # 4. Lead segment members
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_segment_members (
                    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
                    segment_id UUID REFERENCES lead_segments(id) ON DELETE CASCADE,
                    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (lead_id, segment_id)
                );
            """)
            logger.info("✓ Created lead_segment_members table")

            # 5. Lead events table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_events (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
                    campaign_id VARCHAR(50),
                    agent_id UUID,
                    integration_id UUID,
                    event_type VARCHAR(100) NOT NULL,
                    event_data JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by UUID,
                    FOREIGN KEY (campaign_id) REFERENCES Campaign(id) ON DELETE SET NULL
                );
            """)
            logger.info("✓ Created lead_events table")

            # 6. Nurturing campaigns table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS nurturing_campaigns (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    company_id UUID NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    trigger VARCHAR(50) NOT NULL,
                    schedule JSONB,
                    steps JSONB NOT NULL,
                    active BOOLEAN DEFAULT true,
                    sales_campaign_id VARCHAR(50),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_by UUID,
                    FOREIGN KEY (sales_campaign_id) REFERENCES Campaign(id) ON DELETE SET NULL
                );
            """)
            logger.info("✓ Created nurturing_campaigns table")

            # 7. Lead nurturing enrollment
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_nurturing_enrollment (
                    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
                    nurturing_campaign_id UUID REFERENCES nurturing_campaigns(id) ON DELETE CASCADE,
                    sales_campaign_id VARCHAR(50),
                    enrolled_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    current_step INTEGER DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'active',
                    completed_at TIMESTAMP WITH TIME ZONE,
                    PRIMARY KEY (lead_id, nurturing_campaign_id),
                    FOREIGN KEY (sales_campaign_id) REFERENCES Campaign(id) ON DELETE SET NULL
                );
            """)
            logger.info("✓ Created lead_nurturing_enrollment table")

            # 8. Lead scoring history
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_score_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
                    campaign_id VARCHAR(50),
                    previous_score INTEGER,
                    new_score INTEGER,
                    scoring_factors JSONB,
                    scored_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    scored_by UUID,
                    FOREIGN KEY (campaign_id) REFERENCES Campaign(id) ON DELETE SET NULL
                );
            """)
            logger.info("✓ Created lead_score_history table")

            # 9. Lead distribution history
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_distribution_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
                    campaign_id VARCHAR(50),
                    assigned_from UUID,
                    assigned_to UUID,
                    distribution_method VARCHAR(50),
                    distribution_metadata JSONB,
                    distributed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES Campaign(id) ON DELETE SET NULL
                );
            """)
            logger.info("✓ Created lead_distribution_history table")

            # 10. Lead import history
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_import_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    campaign_id VARCHAR(50),
                    company_id UUID NOT NULL,
                    import_type VARCHAR(50),
                    imported_count INTEGER,
                    failed_count INTEGER,
                    duplicate_count INTEGER,
                    import_metadata JSONB,
                    imported_by UUID,
                    imported_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES Campaign(id) ON DELETE SET NULL
                );
            """)
            logger.info("✓ Created lead_import_history table")

            # 11. Lead-Agent interactions
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_agent_interactions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
                    agent_id UUID,
                    campaign_id VARCHAR(50),
                    interaction_type VARCHAR(50),
                    interaction_data JSONB DEFAULT '{}'::jsonb,
                    duration_seconds INTEGER,
                    outcome VARCHAR(50),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES Campaign(id) ON DELETE SET NULL
                );
            """)
            logger.info("✓ Created lead_agent_interactions table")

            # 12. Company lead pools
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS company_lead_pools (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    company_id UUID NOT NULL,
                    pool_name VARCHAR(255) NOT NULL,
                    description TEXT,
                    criteria JSONB DEFAULT '{}'::jsonb,
                    is_active BOOLEAN DEFAULT true,
                    created_by UUID,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            logger.info("✓ Created company_lead_pools table")

            # 13. Lead pool members
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_pool_members (
                    pool_id UUID REFERENCES company_lead_pools(id) ON DELETE CASCADE,
                    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
                    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (pool_id, lead_id)
                );
            """)
            logger.info("✓ Created lead_pool_members table")

            # 14. Lead WhatsApp data
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_whatsapp_data (
                    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE PRIMARY KEY,
                    whatsapp_number VARCHAR(50),
                    whatsapp_business_id VARCHAR(255),
                    opt_in_status BOOLEAN DEFAULT false,
                    opt_in_date TIMESTAMP WITH TIME ZONE,
                    last_message_at TIMESTAMP WITH TIME ZONE,
                    conversation_id VARCHAR(255),
                    metadata JSONB DEFAULT '{}'::jsonb
                );
            """)
            logger.info("✓ Created lead_whatsapp_data table")

            # 15. Lead call logs
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_call_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
                    campaign_id VARCHAR(50),
                    agent_id UUID,
                    call_id VARCHAR(255),
                    duration_seconds INTEGER,
                    recording_url TEXT,
                    transcript TEXT,
                    sentiment_score DECIMAL(3,2),
                    outcome VARCHAR(50),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES Campaign(id) ON DELETE SET NULL
                );
            """)
            logger.info("✓ Created lead_call_logs table")

            # 16. Lead integration sources
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS lead_integration_sources (
                    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
                    integration_id UUID,
                    integration_data JSONB DEFAULT '{}'::jsonb,
                    imported_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (lead_id, integration_id)
                );
            """)
            logger.info("✓ Created lead_integration_sources table")

            logger.info("✅ All lead management tables created successfully!")

        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise

async def create_indexes():
    """Create all indexes for optimal query performance"""
    
    async with await get_db_connection() as conn:
        try:
            # Indexes for leads table
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_leads_company_id ON leads(company_id)",
                "CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(company_id, LOWER(email))",
                "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)",
                "CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source)",
                "CREATE INDEX IF NOT EXISTS idx_leads_source_integration ON leads(source_integration_id)",
                "CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority)",
                "CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score)",
                "CREATE INDEX IF NOT EXISTS idx_leads_assigned_to ON leads(assigned_to)",
                "CREATE INDEX IF NOT EXISTS idx_leads_assigned_agent ON leads(assigned_agent_id)",
                "CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_leads_updated_at ON leads(updated_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_leads_tags ON leads USING GIN(tags)",
                "CREATE INDEX IF NOT EXISTS idx_leads_custom_fields ON leads USING GIN(custom_fields)",
                
                # Indexes for campaign_leads
                "CREATE INDEX IF NOT EXISTS idx_campaign_leads_campaign ON campaign_leads(campaign_id)",
                "CREATE INDEX IF NOT EXISTS idx_campaign_leads_lead ON campaign_leads(lead_id)",
                "CREATE INDEX IF NOT EXISTS idx_campaign_leads_status ON campaign_leads(campaign_status)",
                "CREATE INDEX IF NOT EXISTS idx_campaign_leads_added_at ON campaign_leads(added_to_campaign_at DESC)",
                
                # Indexes for lead_events
                "CREATE INDEX IF NOT EXISTS idx_lead_events_lead_id ON lead_events(lead_id)",
                "CREATE INDEX IF NOT EXISTS idx_lead_events_campaign_id ON lead_events(campaign_id)",
                "CREATE INDEX IF NOT EXISTS idx_lead_events_agent_id ON lead_events(agent_id)",
                "CREATE INDEX IF NOT EXISTS idx_lead_events_type ON lead_events(event_type)",
                "CREATE INDEX IF NOT EXISTS idx_lead_events_created_at ON lead_events(created_at DESC)",
                
                # Indexes for other tables
                "CREATE INDEX IF NOT EXISTS idx_lead_segments_company ON lead_segments(company_id)",
                "CREATE INDEX IF NOT EXISTS idx_lead_segment_members_segment ON lead_segment_members(segment_id)",
                "CREATE INDEX IF NOT EXISTS idx_lead_segment_members_lead ON lead_segment_members(lead_id)",
                "CREATE INDEX IF NOT EXISTS idx_nurturing_campaigns_company ON nurturing_campaigns(company_id)",
                "CREATE INDEX IF NOT EXISTS idx_lead_score_history_lead ON lead_score_history(lead_id)",
                "CREATE INDEX IF NOT EXISTS idx_lead_score_history_campaign ON lead_score_history(campaign_id)",
                "CREATE INDEX IF NOT EXISTS idx_lead_agent_interactions_lead ON lead_agent_interactions(lead_id)",
                "CREATE INDEX IF NOT EXISTS idx_lead_agent_interactions_agent ON lead_agent_interactions(agent_id)",
                "CREATE INDEX IF NOT EXISTS idx_lead_call_logs_lead ON lead_call_logs(lead_id)",
                "CREATE INDEX IF NOT EXISTS idx_lead_call_logs_campaign ON lead_call_logs(campaign_id)",
                "CREATE INDEX IF NOT EXISTS idx_company_lead_pools_company ON company_lead_pools(company_id)"
            ]
            
            for index in indexes:
                await conn.execute(index)
                logger.info(f"✓ Created index: {index.split('idx_')[1].split(' ')[0]}")
            
            logger.info("✅ All indexes created successfully!")
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            raise

async def create_views():
    """Create views for reporting and analytics"""
    
    async with await get_db_connection() as conn:
        try:
            # Campaign lead performance view
            await conn.execute("""
                CREATE OR REPLACE VIEW v_campaign_lead_performance AS
                SELECT 
                    cl.campaign_id,
                    c.campaign_name,
                    COUNT(DISTINCT cl.lead_id) as total_leads,
                    COUNT(DISTINCT CASE WHEN cl.campaign_status = 'contacted' THEN cl.lead_id END) as contacted_leads,
                    COUNT(DISTINCT CASE WHEN cl.campaign_status = 'qualified' THEN cl.lead_id END) as qualified_leads,
                    COUNT(DISTINCT CASE WHEN cl.campaign_status = 'converted' THEN cl.lead_id END) as converted_leads,
                    AVG(l.score) as avg_lead_score,
                    SUM(cl.call_attempts) as total_call_attempts,
                    SUM(cl.email_attempts) as total_email_attempts
                FROM campaign_leads cl
                JOIN Campaign c ON c.id = cl.campaign_id
                JOIN leads l ON l.id = cl.lead_id
                GROUP BY cl.campaign_id, c.campaign_name;
            """)
            logger.info("✓ Created v_campaign_lead_performance view")

            # Lead engagement view
            await conn.execute("""
                CREATE OR REPLACE VIEW v_lead_engagement AS
                SELECT 
                    l.id as lead_id,
                    l.email,
                    l.first_name,
                    l.last_name,
                    l.score,
                    COUNT(DISTINCT cl.campaign_id) as campaigns_count,
                    COUNT(DISTINCT le.id) as total_events,
                    MAX(le.created_at) as last_activity,
                    ARRAY_AGG(DISTINCT c.campaign_name) as campaigns
                FROM leads l
                LEFT JOIN campaign_leads cl ON cl.lead_id = l.id
                LEFT JOIN lead_events le ON le.lead_id = l.id
                LEFT JOIN Campaign c ON c.id = cl.campaign_id
                GROUP BY l.id, l.email, l.first_name, l.last_name, l.score;
            """)
            logger.info("✓ Created v_lead_engagement view")

            logger.info("✅ All views created successfully!")
            
        except Exception as e:
            logger.error(f"Error creating views: {e}")
            raise

async def main():
    """Main function to create all tables, indexes, and views"""
    try:
        logger.info("Starting lead management database setup...")
        
        # Create tables
        await create_lead_management_tables()
        
        # Create indexes
        await create_indexes()
        
        # Create views
        await create_views()
        
        logger.info("🎉 Lead management database setup completed successfully!")
        
    except Exception as e:
        logger.error(f"Failed to set up lead management database: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())