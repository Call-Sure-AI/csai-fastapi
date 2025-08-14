import asyncio
import asyncpg
from config import DATABASE_URL

async def create_analytics_tables():
    conn = await asyncpg.connect(DATABASE_URL)
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS Conversation_Outcome (
            id SERIAL PRIMARY KEY,
            call_id VARCHAR(255) UNIQUE NOT NULL,
            user_phone VARCHAR(20),
            conversation_duration INTEGER,
            outcome VARCHAR(50) NOT NULL,
            lead_score INTEGER,
            extracted_details JSONB,
            agent_id VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_conversation_outcome_created_at 
        ON Conversation_Outcome(created_at);
        
        CREATE INDEX IF NOT EXISTS idx_conversation_outcome_outcome 
        ON Conversation_Outcome(outcome);
        
        CREATE INDEX IF NOT EXISTS idx_conversation_outcome_agent_id 
        ON Conversation_Outcome(agent_id);
    """)
    
    await conn.close()
    print("Analytics tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_analytics_tables())
