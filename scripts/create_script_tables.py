import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db.postgres_client import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_script_management_tables():
    """Create all tables for the script management system"""
    
    async with await get_db_connection() as conn:
        try:
            # 1. Script templates table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_templates (
                    id VARCHAR(50) PRIMARY KEY,
                    company_id UUID NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    category VARCHAR(100),
                    tags JSONB DEFAULT '[]'::jsonb,
                    flow JSONB NOT NULL,
                    preview_image TEXT,
                    is_public BOOLEAN DEFAULT true,
                    is_active BOOLEAN DEFAULT true,
                    usage_count INTEGER DEFAULT 0,
                    created_by UUID,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            logger.info("✓ Created script_templates table")

            # 2. Main scripts table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS scripts (
                    id VARCHAR(50) PRIMARY KEY,
                    company_id UUID NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    template_id VARCHAR(50) REFERENCES script_templates(id) ON DELETE SET NULL,
                    flow JSONB NOT NULL,
                    status VARCHAR(50) DEFAULT 'draft',
                    version INTEGER DEFAULT 1,
                    is_active BOOLEAN DEFAULT false,
                    tags JSONB DEFAULT '[]'::jsonb,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    created_by UUID,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    published_at TIMESTAMP WITH TIME ZONE,
                    archived_at TIMESTAMP WITH TIME ZONE,
                    CONSTRAINT scripts_status_check CHECK (status IN ('draft', 'published', 'archived', 'testing'))
                );
            """)
            logger.info("✓ Created scripts table")

            # 3. Script versions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_versions (
                    id VARCHAR(50) PRIMARY KEY,
                    script_id VARCHAR(50) NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
                    version INTEGER NOT NULL,
                    flow JSONB NOT NULL,
                    status VARCHAR(50) DEFAULT 'draft',
                    changes TEXT,
                    created_by UUID,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    published_at TIMESTAMP WITH TIME ZONE,
                    UNIQUE(script_id, version),
                    CONSTRAINT script_versions_status_check CHECK (status IN ('draft', 'published', 'archived', 'testing'))
                );
            """)
            logger.info("✓ Created script_versions table")

            # 4. Script executions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_executions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    script_id VARCHAR(50) NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
                    version INTEGER,
                    session_id VARCHAR(255),
                    user_id UUID,
                    lead_id UUID,
                    campaign_id VARCHAR(50),
                    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP WITH TIME ZONE,
                    status VARCHAR(50) DEFAULT 'running',
                    last_node_id VARCHAR(100),
                    execution_data JSONB DEFAULT '{}'::jsonb,
                    error_message TEXT,
                    total_nodes_executed INTEGER DEFAULT 0,
                    CONSTRAINT script_executions_status_check CHECK (status IN ('running', 'completed', 'failed', 'abandoned', 'timeout'))
                );
            """)
            logger.info("✓ Created script_executions table")

            # 5. Script node executions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_node_executions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    execution_id UUID REFERENCES script_executions(id) ON DELETE CASCADE,
                    script_id VARCHAR(50) NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
                    node_id VARCHAR(100) NOT NULL,
                    node_type VARCHAR(50),
                    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    duration_ms INTEGER,
                    input_data JSONB DEFAULT '{}'::jsonb,
                    output_data JSONB DEFAULT '{}'::jsonb,
                    error_occurred BOOLEAN DEFAULT false,
                    error_message TEXT
                );
            """)
            logger.info("✓ Created script_node_executions table")

            # 6. Script events table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_events (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    script_id VARCHAR(50) NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
                    event_type VARCHAR(100) NOT NULL,
                    event_data JSONB DEFAULT '{}'::jsonb,
                    created_by UUID,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            logger.info("✓ Created script_events table")

            # 7. Script analytics aggregates table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_analytics (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    script_id VARCHAR(50) NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
                    date DATE NOT NULL,
                    total_executions INTEGER DEFAULT 0,
                    successful_completions INTEGER DEFAULT 0,
                    failed_executions INTEGER DEFAULT 0,
                    abandoned_executions INTEGER DEFAULT 0,
                    avg_duration_seconds DECIMAL(10,2),
                    unique_users INTEGER DEFAULT 0,
                    node_metrics JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(script_id, date)
                );
            """)
            logger.info("✓ Created script_analytics table")

            # 8. Script categories table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_categories (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    company_id UUID NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    parent_category_id UUID REFERENCES script_categories(id) ON DELETE CASCADE,
                    icon VARCHAR(50),
                    color VARCHAR(7),
                    sort_order INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(company_id, name)
                );
            """)
            logger.info("✓ Created script_categories table")

            # 9. Script test runs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_test_runs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    script_id VARCHAR(50) NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
                    version INTEGER,
                    test_data JSONB DEFAULT '{}'::jsonb,
                    test_results JSONB DEFAULT '{}'::jsonb,
                    validation_errors JSONB DEFAULT '[]'::jsonb,
                    validation_warnings JSONB DEFAULT '[]'::jsonb,
                    passed BOOLEAN DEFAULT false,
                    tested_by UUID,
                    tested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            logger.info("✓ Created script_test_runs table")

            # 10. Script shares table (for collaboration)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_shares (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    script_id VARCHAR(50) NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
                    shared_with_user_id UUID,
                    shared_with_company_id UUID,
                    permission_level VARCHAR(50) DEFAULT 'view',
                    shared_by UUID,
                    shared_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    CONSTRAINT script_shares_permission_check CHECK (permission_level IN ('view', 'edit', 'admin'))
                );
            """)
            logger.info("✓ Created script_shares table")

            # 11. Script variables table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_variables (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    script_id VARCHAR(50) NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
                    variable_name VARCHAR(100) NOT NULL,
                    variable_type VARCHAR(50),
                    default_value TEXT,
                    description TEXT,
                    is_required BOOLEAN DEFAULT false,
                    validation_rules JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(script_id, variable_name)
                );
            """)
            logger.info("✓ Created script_variables table")

            # 12. Script node templates table (reusable nodes)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_node_templates (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    company_id UUID NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    node_type VARCHAR(50) NOT NULL,
                    content JSONB NOT NULL,
                    category VARCHAR(100),
                    tags JSONB DEFAULT '[]'::jsonb,
                    is_public BOOLEAN DEFAULT false,
                    created_by UUID,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            logger.info("✓ Created script_node_templates table")

            # 13. Script execution context table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_execution_context (
                    execution_id UUID REFERENCES script_executions(id) ON DELETE CASCADE,
                    context_key VARCHAR(255) NOT NULL,
                    context_value JSONB,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (execution_id, context_key)
                );
            """)
            logger.info("✓ Created script_execution_context table")

            # 14. Script webhooks table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_webhooks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    script_id VARCHAR(50) NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
                    webhook_url TEXT NOT NULL,
                    event_types JSONB DEFAULT '[]'::jsonb,
                    headers JSONB DEFAULT '{}'::jsonb,
                    is_active BOOLEAN DEFAULT true,
                    secret_key TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            logger.info("✓ Created script_webhooks table")

            # 15. Script comments table (for collaboration)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS script_comments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    script_id VARCHAR(50) NOT NULL REFERENCES scripts(id) ON DELETE CASCADE,
                    node_id VARCHAR(100),
                    comment_text TEXT NOT NULL,
                    created_by UUID,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    resolved BOOLEAN DEFAULT false,
                    resolved_by UUID,
                    resolved_at TIMESTAMP WITH TIME ZONE
                );
            """)
            logger.info("✓ Created script_comments table")

            logger.info("✅ All script management tables created successfully!")

        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise

async def create_indexes():
    """Create all indexes for optimal query performance"""
    
    async with await get_db_connection() as conn:
        try:
            indexes = [
                # Script templates indexes
                "CREATE INDEX IF NOT EXISTS idx_script_templates_company_id ON script_templates(company_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_templates_category ON script_templates(category)",
                "CREATE INDEX IF NOT EXISTS idx_script_templates_is_public ON script_templates(is_public)",
                "CREATE INDEX IF NOT EXISTS idx_script_templates_tags ON script_templates USING GIN(tags)",
                
                # Scripts indexes
                "CREATE INDEX IF NOT EXISTS idx_scripts_company_id ON scripts(company_id)",
                "CREATE INDEX IF NOT EXISTS idx_scripts_template_id ON scripts(template_id)",
                "CREATE INDEX IF NOT EXISTS idx_scripts_status ON scripts(status)",
                "CREATE INDEX IF NOT EXISTS idx_scripts_is_active ON scripts(is_active)",
                "CREATE INDEX IF NOT EXISTS idx_scripts_created_at ON scripts(created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_scripts_published_at ON scripts(published_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_scripts_tags ON scripts USING GIN(tags)",
                "CREATE INDEX IF NOT EXISTS idx_scripts_metadata ON scripts USING GIN(metadata)",
                
                # Script versions indexes
                "CREATE INDEX IF NOT EXISTS idx_script_versions_script_id ON script_versions(script_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_versions_status ON script_versions(status)",
                "CREATE INDEX IF NOT EXISTS idx_script_versions_created_at ON script_versions(created_at DESC)",
                
                # Script executions indexes
                "CREATE INDEX IF NOT EXISTS idx_script_executions_script_id ON script_executions(script_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_executions_session_id ON script_executions(session_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_executions_user_id ON script_executions(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_executions_lead_id ON script_executions(lead_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_executions_campaign_id ON script_executions(campaign_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_executions_status ON script_executions(status)",
                "CREATE INDEX IF NOT EXISTS idx_script_executions_started_at ON script_executions(started_at DESC)",
                
                # Script node executions indexes
                "CREATE INDEX IF NOT EXISTS idx_script_node_executions_execution_id ON script_node_executions(execution_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_node_executions_script_id ON script_node_executions(script_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_node_executions_node_id ON script_node_executions(node_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_node_executions_executed_at ON script_node_executions(executed_at DESC)",
                
                # Script events indexes
                "CREATE INDEX IF NOT EXISTS idx_script_events_script_id ON script_events(script_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_events_event_type ON script_events(event_type)",
                "CREATE INDEX IF NOT EXISTS idx_script_events_created_at ON script_events(created_at DESC)",
                
                # Script analytics indexes
                "CREATE INDEX IF NOT EXISTS idx_script_analytics_script_id_date ON script_analytics(script_id, date DESC)",
                
                # Other indexes
                "CREATE INDEX IF NOT EXISTS idx_script_categories_company_id ON script_categories(company_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_categories_parent ON script_categories(parent_category_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_test_runs_script_id ON script_test_runs(script_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_shares_script_id ON script_shares(script_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_shares_shared_with_user ON script_shares(shared_with_user_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_shares_shared_with_company ON script_shares(shared_with_company_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_variables_script_id ON script_variables(script_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_node_templates_company_id ON script_node_templates(company_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_webhooks_script_id ON script_webhooks(script_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_comments_script_id ON script_comments(script_id)",
                "CREATE INDEX IF NOT EXISTS idx_script_comments_node_id ON script_comments(node_id)"
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
            # Script performance view
            await conn.execute("""
                CREATE OR REPLACE VIEW v_script_performance AS
                SELECT 
                    s.id as script_id,
                    s.name as script_name,
                    s.status,
                    s.version,
                    COUNT(DISTINCT se.id) as total_executions,
                    COUNT(DISTINCT CASE WHEN se.status = 'completed' THEN se.id END) as successful_completions,
                    COUNT(DISTINCT CASE WHEN se.status = 'failed' THEN se.id END) as failed_executions,
                    COUNT(DISTINCT CASE WHEN se.status = 'abandoned' THEN se.id END) as abandoned_executions,
                    AVG(EXTRACT(EPOCH FROM (se.completed_at - se.started_at))) as avg_duration_seconds,
                    MAX(se.started_at) as last_execution_at
                FROM scripts s
                LEFT JOIN script_executions se ON s.id = se.script_id
                GROUP BY s.id, s.name, s.status, s.version;
            """)
            logger.info("✓ Created v_script_performance view")

            # Node execution statistics view
            await conn.execute("""
                CREATE OR REPLACE VIEW v_node_execution_stats AS
                SELECT 
                    sne.script_id,
                    sne.node_id,
                    sne.node_type,
                    COUNT(*) as execution_count,
                    AVG(sne.duration_ms) as avg_duration_ms,
                    MAX(sne.duration_ms) as max_duration_ms,
                    MIN(sne.duration_ms) as min_duration_ms,
                    COUNT(CASE WHEN sne.error_occurred THEN 1 END) as error_count,
                    (COUNT(CASE WHEN sne.error_occurred THEN 1 END)::FLOAT / COUNT(*)::FLOAT * 100) as error_rate
                FROM script_node_executions sne
                GROUP BY sne.script_id, sne.node_id, sne.node_type;
            """)
            logger.info("✓ Created v_node_execution_stats view")

            # Script usage by company view
            await conn.execute("""
                CREATE OR REPLACE VIEW v_script_usage_by_company AS
                SELECT 
                    s.company_id,
                    COUNT(DISTINCT s.id) as total_scripts,
                    COUNT(DISTINCT CASE WHEN s.status = 'published' THEN s.id END) as published_scripts,
                    COUNT(DISTINCT CASE WHEN s.is_active THEN s.id END) as active_scripts,
                    COUNT(DISTINCT st.id) as templates_created,
                    COUNT(DISTINCT se.id) as total_executions_all_time,
                    MAX(s.created_at) as last_script_created,
                    MAX(se.started_at) as last_execution_at
                FROM scripts s
                LEFT JOIN script_templates st ON st.company_id = s.company_id
                LEFT JOIN script_executions se ON se.script_id = s.id
                GROUP BY s.company_id;
            """)
            logger.info("✓ Created v_script_usage_by_company view")

            # Daily script analytics view
            await conn.execute("""
                CREATE OR REPLACE VIEW v_daily_script_analytics AS
                SELECT 
                    DATE(se.started_at) as execution_date,
                    se.script_id,
                    COUNT(*) as daily_executions,
                    COUNT(DISTINCT se.user_id) as unique_users,
                    COUNT(DISTINCT se.lead_id) as unique_leads,
                    COUNT(CASE WHEN se.status = 'completed' THEN 1 END) as completions,
                    AVG(EXTRACT(EPOCH FROM (se.completed_at - se.started_at))) as avg_duration_seconds
                FROM script_executions se
                WHERE se.started_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY DATE(se.started_at), se.script_id;
            """)
            logger.info("✓ Created v_daily_script_analytics view")

            logger.info("✅ All views created successfully!")
            
        except Exception as e:
            logger.error(f"Error creating views: {e}")
            raise

async def create_functions():
    """Create helper functions and triggers"""
    
    async with await get_db_connection() as conn:
        try:
            # Function to update updated_at timestamp
            await conn.execute("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """)
            logger.info("✓ Created update_updated_at_column function")

            # Triggers for updated_at
            triggers = [
                "CREATE TRIGGER update_script_templates_updated_at BEFORE UPDATE ON script_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
                "CREATE TRIGGER update_scripts_updated_at BEFORE UPDATE ON scripts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
                "CREATE TRIGGER update_script_analytics_updated_at BEFORE UPDATE ON script_analytics FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
                "CREATE TRIGGER update_script_categories_updated_at BEFORE UPDATE ON script_categories FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
                "CREATE TRIGGER update_script_node_templates_updated_at BEFORE UPDATE ON script_node_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
                "CREATE TRIGGER update_script_webhooks_updated_at BEFORE UPDATE ON script_webhooks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
                "CREATE TRIGGER update_script_comments_updated_at BEFORE UPDATE ON script_comments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()"
            ]
            
            for trigger in triggers:
                try:
                    await conn.execute(trigger)
                    logger.info(f"✓ Created trigger: {trigger.split('CREATE TRIGGER ')[1].split(' ')[0]}")
                except Exception as e:
                    if "already exists" in str(e):
                        logger.info(f"⚠ Trigger already exists: {trigger.split('CREATE TRIGGER ')[1].split(' ')[0]}")
                    else:
                        raise

            # Function to validate script flow
            await conn.execute("""
                CREATE OR REPLACE FUNCTION validate_script_flow(flow JSONB)
                RETURNS BOOLEAN AS $$
                BEGIN
                    -- Check if flow has required fields
                    IF flow->>'nodes' IS NULL OR flow->>'edges' IS NULL THEN
                        RETURN FALSE;
                    END IF;
                    
                    -- Check if flow has at least one node
                    IF jsonb_array_length(flow->'nodes') < 1 THEN
                        RETURN FALSE;
                    END IF;
                    
                    RETURN TRUE;
                END;
                $$ language 'plpgsql';
            """)
            logger.info("✓ Created validate_script_flow function")

            # Function to calculate script completion rate
            await conn.execute("""
                CREATE OR REPLACE FUNCTION calculate_script_completion_rate(p_script_id VARCHAR)
                RETURNS DECIMAL AS $$
                DECLARE
                    total_executions INTEGER;
                    completed_executions INTEGER;
                BEGIN
                    SELECT COUNT(*) INTO total_executions
                    FROM script_executions
                    WHERE script_id = p_script_id;
                    
                    SELECT COUNT(*) INTO completed_executions
                    FROM script_executions
                    WHERE script_id = p_script_id AND status = 'completed';
                    
                    IF total_executions = 0 THEN
                        RETURN 0;
                    END IF;
                    
                    RETURN (completed_executions::DECIMAL / total_executions::DECIMAL) * 100;
                END;
                $$ language 'plpgsql';
            """)
            logger.info("✓ Created calculate_script_completion_rate function")

            logger.info("✅ All functions and triggers created successfully!")
            
        except Exception as e:
            logger.error(f"Error creating functions: {e}")
            raise

async def insert_default_data():
    """Insert default categories and templates"""
    
    async with await get_db_connection() as conn:
        try:
            # Insert default categories
            await conn.execute("""
                INSERT INTO script_categories (name, description, icon, color, sort_order)
                VALUES 
                    ('Sales', 'Sales and outreach scripts', 'phone', '#4CAF50', 1),
                    ('Support', 'Customer support scripts', 'support', '#2196F3', 2),
                    ('Survey', 'Survey and feedback scripts', 'poll', '#FF9800', 3),
                    ('Onboarding', 'User onboarding scripts', 'person_add', '#9C27B0', 4),
                    ('Marketing', 'Marketing and promotion scripts', 'campaign', '#F44336', 5)
                ON CONFLICT DO NOTHING;
            """)
            logger.info("✓ Inserted default categories")

            # Insert a sample template
            await conn.execute("""
                INSERT INTO script_templates (id, company_id, name, description, category, flow, is_public)
                VALUES (
                    'TMPL-DEFAULT-001',
                    '00000000-0000-0000-0000-000000000000'::UUID,
                    'Basic Greeting Script',
                    'A simple greeting script template',
                    'Sales',
                    '{
                        "nodes": [
                            {
                                "id": "start",
                                "type": "start",
                                "label": "Start",
                                "position": {"x": 100, "y": 100},
                                "connections": ["greeting"]
                            },
                            {
                                "id": "greeting",
                                "type": "message",
                                "label": "Greeting",
                                "content": {"text": "Hello! How can I help you today?"},
                                "position": {"x": 300, "y": 100},
                                "connections": ["end"]
                            },
                            {
                                "id": "end",
                                "type": "end",
                                "label": "End",
                                "position": {"x": 500, "y": 100},
                                "connections": []
                            }
                        ],
                        "edges": [],
                        "variables": {},
                        "settings": {}
                    }'::jsonb,
                    true
                ) ON CONFLICT DO NOTHING;
            """)
            logger.info("✓ Inserted sample template")

            logger.info("✅ Default data inserted successfully!")
            
        except Exception as e:
            logger.error(f"Error inserting default data: {e}")
            # Non-critical error, continue

async def main():
    """Main function to create all tables, indexes, views, and functions"""
    try:
        logger.info("🚀 Starting script management database setup...")
        logger.info("=" * 60)
        
        # Create tables
        logger.info("📊 Creating tables...")
        await create_script_management_tables()
        
        # Create indexes
        logger.info("\n🔍 Creating indexes...")
        await create_indexes()
        
        # Create views
        logger.info("\n👁️ Creating views...")
        await create_views()
        
        # Create functions and triggers
        logger.info("\n⚙️ Creating functions and triggers...")
        await create_functions()
        
        # Insert default data
        logger.info("\n📝 Inserting default data...")
        await insert_default_data()
        
        logger.info("=" * 60)
        logger.info("🎉 Script management database setup completed successfully!")
        logger.info("✅ All tables, indexes, views, and functions are ready to use!")
        
    except Exception as e:
        logger.error(f"❌ Failed to set up script management database: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())