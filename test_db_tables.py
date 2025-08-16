import asyncio
from app.db.postgres_client import get_db_connection

SQL_CALENDAR_INTEGRATIONS = """
CREATE TABLE IF NOT EXISTS email_templates (
    id VARCHAR(255) PRIMARY KEY,
    company_id VARCHAR(255) NOT NULL,
    created_by VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    subject VARCHAR(500) NOT NULL,
    body TEXT NOT NULL,
    template_type VARCHAR(50) DEFAULT 'campaign',
    variables JSONB DEFAULT '[]'::jsonb,
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, name)
);
"""

SQL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_email_templates_company ON email_templates(company_id);
CREATE INDEX IF NOT EXISTS idx_email_templates_type ON email_templates(template_type);
CREATE INDEX IF NOT EXISTS idx_email_templates_default ON email_templates(is_default) WHERE is_default = TRUE;
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