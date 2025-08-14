from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncpg
import json

class ConversationQueries:
    @staticmethod
    async def create_conversation(
        pool: asyncpg.Pool,
        call_id: str,
        user_phone: str,
        agent_id: str
    ):
        query = """
        INSERT INTO Conversation (call_id, user_phone, agent_id, status, created_at)
        VALUES ($1, $2, $3, 'active', $4)
        RETURNING id
        """
        async with pool.acquire() as conn:
            return await conn.fetchval(
                query, call_id, user_phone, agent_id, datetime.utcnow()
            )

    @staticmethod
    async def update_conversation_outcome(
        pool: asyncpg.Pool,
        call_id: str,
        outcome: str,
        transcript: str,
        duration: int
    ):
        query = """
        UPDATE Conversation 
        SET outcome = $2, transcript = $3, duration = $4, 
            status = 'completed', updated_at = $5
        WHERE call_id = $1
        """
        async with pool.acquire() as conn:
            await conn.execute(
                query, call_id, outcome, transcript, 
                duration, datetime.utcnow()
            )

    @staticmethod
    async def get_conversation_history(
        pool: asyncpg.Pool,
        agent_id: Optional[str] = None,
        limit: int = 50
    ):
        where_clause = "WHERE agent_id = $1" if agent_id else ""
        limit_clause = f"LIMIT ${2 if agent_id else 1}"
        params = [agent_id, limit] if agent_id else [limit]
        
        query = f"""
        SELECT call_id, user_phone, agent_id, outcome, duration, 
               status, created_at, updated_at
        FROM Conversation 
        {where_clause}
        ORDER BY created_at DESC
        {limit_clause}
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
