from typing import List, Dict, Any, Optional
from datetime import datetime, date
import asyncpg

class AnalyticsQueries:
    @staticmethod
    async def create_conversation_outcome(
        pool: asyncpg.Pool,
        call_id: str,
        user_phone: str,
        conversation_duration: int,
        outcome: str,
        lead_score: int,
        extracted_details: Dict[str, Any],
        agent_id: str
    ):
        query = """
        INSERT INTO Conversation_Outcome 
        (call_id, user_phone, conversation_duration, outcome, lead_score, 
         extracted_details, agent_id, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """
        async with pool.acquire() as conn:
            return await conn.fetchval(
                query, call_id, user_phone, conversation_duration, 
                outcome, lead_score, extracted_details, agent_id, datetime.utcnow()
            )

    @staticmethod
    async def get_daily_analytics(pool: asyncpg.Pool, start_date: date, end_date: date):
        query = """
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as total_calls,
            COUNT(CASE WHEN outcome = 'interested' THEN 1 END) as interested_leads,
            COUNT(CASE WHEN outcome = 'callback_requested' THEN 1 END) as callback_requests,
            COUNT(CASE WHEN outcome = 'not_interested' THEN 1 END) as not_interested,
            COUNT(CASE WHEN outcome = 'incomplete' THEN 1 END) as incomplete_calls,
            AVG(conversation_duration) as avg_duration,
            AVG(lead_score) as avg_lead_score
        FROM Conversation_Outcome 
        WHERE DATE(created_at) BETWEEN $1 AND $2
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, start_date, end_date)
            return [dict(row) for row in rows]

    @staticmethod
    async def get_agent_performance(pool: asyncpg.Pool, agent_id: Optional[str] = None):
        where_clause = "WHERE agent_id = $1" if agent_id else ""
        params = [agent_id] if agent_id else []
        
        query = f"""
        SELECT 
            agent_id,
            COUNT(*) as total_calls,
            COUNT(CASE WHEN outcome IN ('interested', 'callback_requested') THEN 1 END) as successful_leads,
            ROUND(COUNT(CASE WHEN outcome IN ('interested', 'callback_requested') THEN 1 END) * 100.0 / COUNT(*), 2) as conversion_rate,
            AVG(conversation_duration) as avg_duration,
            AVG(lead_score) as avg_lead_score
        FROM Conversation_Outcome 
        {where_clause}
        GROUP BY agent_id
        ORDER BY conversion_rate DESC
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    @staticmethod
    async def get_lead_details(pool: asyncpg.Pool, outcome: str = 'interested'):
        query = """
        SELECT 
            call_id,
            user_phone,
            extracted_details,
            lead_score,
            conversation_duration,
            created_at,
            agent_id
        FROM Conversation_Outcome 
        WHERE outcome = $1
        ORDER BY created_at DESC
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, outcome)
            return [dict(row) for row in rows]
