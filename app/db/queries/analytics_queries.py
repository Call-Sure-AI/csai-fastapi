from typing import List, Dict, Any, Optional
from datetime import datetime, date
from app.db.postgres_client import get_db_connection
import json

class AnalyticsQueries:
    @staticmethod
    async def create_conversation_outcome(
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
        
        async with await get_db_connection() as conn:
            result = await conn.fetchval(
                query, 
                call_id, user_phone, conversation_duration, outcome, 
                lead_score, json.dumps(extracted_details), agent_id, datetime.utcnow()
            )
            return result

    @staticmethod
    async def get_daily_analytics(start_date: date, end_date: date):
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
        
        async with await get_db_connection() as conn:
            rows = await conn.fetch(query, start_date, end_date)
            return [dict(row) for row in rows]

    @staticmethod
    async def get_agent_performance(agent_id: Optional[str] = None):
        if agent_id:
            where_clause = "WHERE agent_id = $1"
            params = [agent_id]
        else:
            where_clause = ""
            params = []
        
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
        
        async with await get_db_connection() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    @staticmethod
    async def get_lead_details(outcome: str = 'interested'):
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
        LIMIT 100
        """
        
        async with await get_db_connection() as conn:
            rows = await conn.fetch(query, outcome)
            results = []
            for row in rows:
                row_dict = dict(row)
                if isinstance(row_dict['extracted_details'], str):
                    try:
                        row_dict['extracted_details'] = json.loads(row_dict['extracted_details'])
                    except (json.JSONDecodeError, TypeError):
                        row_dict['extracted_details'] = {}
                elif row_dict['extracted_details'] is None:
                    row_dict['extracted_details'] = {}
                results.append(row_dict)
            return results
