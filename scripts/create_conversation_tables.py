import asyncio
import asyncpg
from config import DATABASE_URL

async def create_conversation_tables():
    conn = await asyncpg.connect(DATABASE_URL)
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS Conversation (
            id SERIAL PRIMARY KEY,
            call_id VARCHAR(255) UNIQUE NOT NULL,
            user_phone VARCHAR(20),
            agent_id VARCHAR(255),
            outcome VARCHAR(50),
            transcript TEXT,
            duration INTEGER DEFAULT 0,
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_conversation_call_id ON Conversation(call_id);
        CREATE INDEX IF NOT EXISTS idx_conversation_agent_id ON Conversation(agent_id);
        CREATE INDEX IF NOT EXISTS idx_conversation_created_at ON Conversation(created_at);
    """)
    
    await conn.close()
    print("Conversation tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_conversation_tables())
