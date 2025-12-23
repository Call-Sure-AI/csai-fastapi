# scripts/create_regulatory_tables.py
"""
Database migration script for regulatory compliance tables.
STANDALONE - No dependencies on app codebase.

Usage:
    python scripts/create_regulatory_tables.py
"""

import os
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_connection():
    """Get a direct database connection from DATABASE_URL"""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")
    
    # Parse the connection string
    result = urlparse(database_url)
    
    return psycopg2.connect(
        host=result.hostname,
        port=result.port or 5432,
        database=result.path[1:],  # Remove leading '/'
        user=result.username,
        password=result.password,
        sslmode='require'  # Required for Neon
    )


def create_regulatory_tables():
    """Create tables for regulatory compliance (address verification)"""
    
    conn = None
    try:
        print("🔌 Connecting to database...")
        conn = get_connection()
        cursor = conn.cursor()
        print("✅ Connected!")
        
        print("\n📦 Creating regulatory_addresses table...")
        
        # Create regulatory_addresses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS regulatory_addresses (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                company_id UUID NOT NULL,
                country_code VARCHAR(2) NOT NULL,
                
                -- Business Information
                business_name VARCHAR(255) NOT NULL,
                
                -- Address Details
                address_line2 VARCHAR(255),
                street_address VARCHAR(255) NOT NULL,
                city VARCHAR(100) NOT NULL,
                region VARCHAR(100) NOT NULL,
                postal_code VARCHAR(20) NOT NULL,
                
                -- Contact Person
                contact_name VARCHAR(100) NOT NULL,
                contact_email VARCHAR(255) NOT NULL,
                contact_phone VARCHAR(20) NOT NULL,
                
                -- Verification Status
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                rejection_reason TEXT,
                
                -- Twilio Integration
                twilio_address_sid VARCHAR(100),
                twilio_bundle_sid VARCHAR(100),
                twilio_end_user_sid VARCHAR(100),
                twilio_regulation_sid VARCHAR(100),
                
                -- Timestamps
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                
                -- Constraints
                CONSTRAINT chk_status CHECK (status IN ('pending', 'in_review', 'verified', 'rejected', 'failed')),
                CONSTRAINT chk_country_code CHECK (LENGTH(country_code) = 2)
            );
        """)
        print("  ✅ Table created")
        
        # Create indexes
        print("\n📇 Creating indexes...")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_regulatory_addresses_company_id 
            ON regulatory_addresses(company_id);
        """)
        print("  ✅ idx_regulatory_addresses_company_id")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_regulatory_addresses_country_code 
            ON regulatory_addresses(country_code);
        """)
        print("  ✅ idx_regulatory_addresses_country_code")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_regulatory_addresses_status 
            ON regulatory_addresses(status);
        """)
        print("  ✅ idx_regulatory_addresses_status")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_regulatory_addresses_twilio_bundle 
            ON regulatory_addresses(twilio_bundle_sid);
        """)
        print("  ✅ idx_regulatory_addresses_twilio_bundle")
        
        # Unique constraint for active addresses
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_regulatory_addresses_unique_active 
            ON regulatory_addresses(company_id, country_code) 
            WHERE status NOT IN ('rejected', 'failed');
        """)
        print("  ✅ idx_regulatory_addresses_unique_active")
        
        # Create trigger function
        print("\n⚡ Creating trigger...")
        
        cursor.execute("""
            CREATE OR REPLACE FUNCTION update_regulatory_addresses_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        
        cursor.execute("""
            DROP TRIGGER IF EXISTS trigger_regulatory_addresses_updated_at ON regulatory_addresses;
        """)
        
        cursor.execute("""
            CREATE TRIGGER trigger_regulatory_addresses_updated_at
                BEFORE UPDATE ON regulatory_addresses
                FOR EACH ROW
                EXECUTE FUNCTION update_regulatory_addresses_updated_at();
        """)
        print("  ✅ updated_at trigger created")
        
        conn.commit()
        
        # Show table structure
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'regulatory_addresses'
            ORDER BY ordinal_position;
        """)
        
        print("\n" + "=" * 60)
        print("✅ SUCCESS! Table created.")
        print("=" * 60)
        print("\n📋 Table Structure:")
        print("-" * 60)
        print(f"  {'Column':<25} {'Type':<20} {'Nullable':<10}")
        print("-" * 60)
        for row in cursor.fetchall():
            nullable = 'YES' if row[2] == 'YES' else 'NO'
            print(f"  {row[0]:<25} {row[1]:<20} {nullable:<10}")
        
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if conn:
            conn.close()
            print("\n🔌 Connection closed.")


def drop_regulatory_tables():
    """Drop regulatory tables"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS regulatory_addresses CASCADE;")
        cursor.execute("DROP FUNCTION IF EXISTS update_regulatory_addresses_updated_at CASCADE;")
        
        conn.commit()
        print("✅ Dropped regulatory_addresses table")
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage regulatory compliance tables")
    parser.add_argument("--drop", action="store_true", help="Drop tables instead of creating")
    args = parser.parse_args()
    
    if args.drop:
        confirm = input("⚠️  Are you sure you want to DROP the table? (yes/no): ")
        if confirm.lower() == "yes":
            drop_regulatory_tables()
        else:
            print("Cancelled.")
    else:
        create_regulatory_tables()