import sys
import os

# Get the path of the project root and add it to the system path.
# This ensures that modules like 'app' can be imported correctly.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

import asyncio
from app.db.postgres_client import get_db_connection

async def update_campaign_schema():
    """
    Updates the Campaign table schema to include the new leads_file_url column.
    This script is designed to be idempotent, meaning it can be run multiple times
    without causing errors, as it checks if the column exists before adding it.
    """
    try:
        async with await get_db_connection() as conn:
            # Add the new leads_file_url column to the Campaign table
            await conn.execute("""
                ALTER TABLE Campaign
                ADD COLUMN IF NOT EXISTS leads_file_url TEXT;
            """)
            print("Successfully added 'leads_file_url' column to the 'Campaign' table.")
    except Exception as e:
        print(f"Error updating Campaign table schema: {e}")

if __name__ == "__main__":
    # Ensure this is run from the project root with `python scripts/modify_campaign_tables.py`
    asyncio.run(update_campaign_schema())