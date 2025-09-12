import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.db.postgres_client import get_db_connection

async def create_scheduling_tables():
    async with await get_db_connection() as conn:
        # Availability Templates
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS availability_templates (
                id VARCHAR PRIMARY KEY,
                company_id VARCHAR NOT NULL,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                schedule_type VARCHAR(50),
                timezone VARCHAR(50),
                is_default BOOLEAN DEFAULT FALSE,
                user_id VARCHAR,
                team_id VARCHAR,
                monday JSONB,
                tuesday JSONB,
                wednesday JSONB,
                thursday JSONB,
                friday JSONB,
                saturday JSONB,
                sunday JSONB,
                slot_duration_minutes INT,
                advance_booking_days INT,
                minimum_notice_hours INT,
                created_by VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_avail_templates_company ON availability_templates(company_id);
            CREATE INDEX IF NOT EXISTS idx_avail_templates_user ON availability_templates(user_id);
            CREATE INDEX IF NOT EXISTS idx_avail_templates_team ON availability_templates(team_id);
        """)
        
        # Booking Rules
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS booking_rules (
                id VARCHAR PRIMARY KEY,
                company_id VARCHAR NOT NULL,
                name VARCHAR(255),
                description TEXT,
                rule_type VARCHAR(50),
                is_active BOOLEAN DEFAULT TRUE,
                priority INT DEFAULT 0,
                parameters JSONB,
                applies_to_all BOOLEAN DEFAULT FALSE,
                user_ids TEXT[],
                team_ids TEXT[],
                meeting_type_ids TEXT[],
                created_by VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_booking_rules_company ON booking_rules(company_id);
            CREATE INDEX IF NOT EXISTS idx_booking_rules_type ON booking_rules(rule_type);
            CREATE INDEX IF NOT EXISTS idx_booking_rules_active ON booking_rules(is_active);
        """)
        
        # Recurring Availability
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS recurring_availability (
                id VARCHAR PRIMARY KEY,
                company_id VARCHAR NOT NULL,
                name VARCHAR(255),
                user_id VARCHAR,
                day_of_week VARCHAR(20),
                time_blocks JSONB,
                effective_from DATE,
                effective_until DATE,
                is_active BOOLEAN DEFAULT TRUE,
                repeat_pattern VARCHAR(50),
                exceptions DATE[],
                created_by VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_recurring_avail_company ON recurring_availability(company_id);
            CREATE INDEX IF NOT EXISTS idx_recurring_avail_user ON recurring_availability(user_id);
            CREATE INDEX IF NOT EXISTS idx_recurring_avail_day ON recurring_availability(day_of_week);
        """)
        
        # Schedule Overrides
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schedule_overrides (
                id VARCHAR PRIMARY KEY,
                company_id VARCHAR NOT NULL,
                user_id VARCHAR,
                override_type VARCHAR(50),
                start_date DATE,
                end_date DATE,
                start_time TIME,
                end_time TIME,
                reason TEXT,
                is_all_day BOOLEAN DEFAULT TRUE,
                replacement_user_id VARCHAR,
                created_by VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_schedule_overrides_company ON schedule_overrides(company_id);
            CREATE INDEX IF NOT EXISTS idx_schedule_overrides_user ON schedule_overrides(user_id);
            CREATE INDEX IF NOT EXISTS idx_schedule_overrides_dates ON schedule_overrides(start_date, end_date);
        """)
        
        # Buffer Rules
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS buffer_rules (
                id VARCHAR PRIMARY KEY,
                company_id VARCHAR NOT NULL,
                name VARCHAR(255),
                user_id VARCHAR,
                team_id VARCHAR,
                meeting_type VARCHAR(100),
                buffer_before_minutes INT DEFAULT 0,
                buffer_after_minutes INT DEFAULT 15,
                applies_to_all_meetings BOOLEAN DEFAULT TRUE,
                is_active BOOLEAN DEFAULT TRUE,
                created_by VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_buffer_rules_company ON buffer_rules(company_id);
            CREATE INDEX IF NOT EXISTS idx_buffer_rules_user ON buffer_rules(user_id);
            CREATE INDEX IF NOT EXISTS idx_buffer_rules_team ON buffer_rules(team_id);
        """)
        
        # Team Schedules
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS team_schedules (
                id VARCHAR PRIMARY KEY,
                company_id VARCHAR NOT NULL,
                team_id VARCHAR,
                name VARCHAR(255),
                assignment_method VARCHAR(50),
                allow_member_preference BOOLEAN DEFAULT TRUE,
                collective_availability BOOLEAN DEFAULT FALSE,
                min_team_members_available INT DEFAULT 1,
                rotation_settings JSONB,
                skill_requirements TEXT[],
                member_ids TEXT[],
                created_by VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_team_schedules_company ON team_schedules(company_id);
            CREATE INDEX IF NOT EXISTS idx_team_schedules_team ON team_schedules(team_id);
        """)
        
        # Resources
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                id VARCHAR PRIMARY KEY,
                company_id VARCHAR NOT NULL,
                name VARCHAR(255),
                resource_type VARCHAR(100),
                capacity INT DEFAULT 1,
                location VARCHAR(255),
                cost DECIMAL(10,2),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_resources_company ON resources(company_id);
            CREATE INDEX IF NOT EXISTS idx_resources_type ON resources(resource_type);
            CREATE INDEX IF NOT EXISTS idx_resources_active ON resources(is_active);
        """)
        
        # Resource Bookings
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS resource_bookings (
                id VARCHAR PRIMARY KEY,
                booking_id VARCHAR,
                resource_id VARCHAR,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_resource_bookings_booking ON resource_bookings(booking_id);
            CREATE INDEX IF NOT EXISTS idx_resource_bookings_resource ON resource_bookings(resource_id);
            CREATE INDEX IF NOT EXISTS idx_resource_bookings_times ON resource_bookings(start_time, end_time);
        """)
        
        # Schedule Policies
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schedule_policies (
                id VARCHAR PRIMARY KEY,
                company_id VARCHAR NOT NULL,
                name VARCHAR(255),
                description TEXT,
                policy_type VARCHAR(50),
                is_active BOOLEAN DEFAULT TRUE,
                priority INT DEFAULT 0,
                rules JSONB,
                applies_to_departments TEXT[],
                applies_to_teams TEXT[],
                applies_to_roles TEXT[],
                enforcement_level VARCHAR(20),
                exceptions TEXT[],
                created_by VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_schedule_policies_company ON schedule_policies(company_id);
            CREATE INDEX IF NOT EXISTS idx_schedule_policies_type ON schedule_policies(policy_type);
            CREATE INDEX IF NOT EXISTS idx_schedule_policies_active ON schedule_policies(is_active);
        """)
        
        print("All scheduling tables created successfully!")
        
        # Verify tables were created
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename IN (
                'availability_templates', 'booking_rules', 'recurring_availability',
                'schedule_overrides', 'buffer_rules', 'team_schedules',
                'resources', 'resource_bookings', 'schedule_policies'
            )
            ORDER BY tablename;
        """)
        
        print("\nCreated tables:")
        for table in tables:
            print(f"  - {table['tablename']}")

if __name__ == "__main__":
    asyncio.run(create_scheduling_tables())