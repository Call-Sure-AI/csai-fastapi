import sys
import os
import asyncio

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.postgres_client import get_db_connection

async def add_provider_column():
    """Add provider column to AgentNumber table"""
    try:
        async with await get_db_connection() as conn:
            # Add provider column
            await conn.execute("""
                ALTER TABLE "AgentNumber" 
                ADD COLUMN IF NOT EXISTS provider VARCHAR(20) DEFAULT 'twilio';
            """)
            
            # Update existing records to 'twilio' if not set
            await conn.execute("""
                UPDATE "AgentNumber" 
                SET provider = 'twilio' 
                WHERE provider IS NULL;
            """)
            
            print("✅ Added 'provider' column to AgentNumber table")
            print("✅ Updated existing records to use 'twilio' provider")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(add_provider_column())