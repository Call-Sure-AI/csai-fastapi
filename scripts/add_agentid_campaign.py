import sys
import os

# Get the path of the project root and add it to the system path.
# This ensures that modules like 'app' can be imported correctly.
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

import asyncio
from app.db.postgres_client import get_db_connection


async def add_agent_id_to_campaign():
    """
    Updates the Campaign table schema to include the agent_id column.
    This script is designed to be idempotent, meaning it can be run multiple times
    without causing errors, as it checks if the column exists before adding it.
    """
    try:
        async with await get_db_connection() as conn:
            # Add the agent_id column to the Campaign table
            await conn.execute("""
                ALTER TABLE Campaign
                ADD COLUMN IF NOT EXISTS agent_id TEXT;
            """)
            print("Successfully added 'agent_id' column to the 'Campaign' table.")
            
            # Optionally add a foreign key constraint to the Agent table
            # Uncomment the following lines if you want to enforce referential integrity
            """
            await conn.execute('''
                ALTER TABLE Campaign
                ADD CONSTRAINT fk_campaign_agent
                FOREIGN KEY (agent_id) REFERENCES "Agent"(id)
                ON DELETE SET NULL;
            ''')
            print("Successfully added foreign key constraint for 'agent_id'.")
            """
            
    except Exception as e:
        print(f"Error updating Campaign table schema: {e}")


if __name__ == "__main__":
    # Ensure this is run from the project root with `python scripts/add_agent_id_to_campaign.py`
    asyncio.run(add_agent_id_to_campaign())
