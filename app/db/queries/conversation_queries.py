from typing import Dict, List, Optional, Tuple
from datetime import datetime

class ConversationQueries:
    """All SQL queries related to Conversation table"""
    
    GET_CONVERSATION_BY_ID = """
        SELECT * FROM "Conversation" WHERE id = %s
    """
    
    GET_CONVERSATIONS_BY_CUSTOMER = """
        SELECT * FROM "Conversation" 
        WHERE "customer_id" = %s 
        ORDER BY "created_at" DESC
    """
    
    GET_CONVERSATIONS_BY_COMPANY = """
        SELECT * FROM "Conversation" 
        WHERE "company_id" = %s 
        ORDER BY "created_at" DESC
        LIMIT %s OFFSET %s
    """
    
    GET_ACTIVE_CONVERSATIONS = """
        SELECT * FROM "Conversation" 
        WHERE status = 'active' AND "company_id" = %s
        ORDER BY "updated_at" DESC
    """
    
    GET_CONVERSATION_WITH_INTERACTIONS = """
        SELECT c.*, 
               COALESCE(
                   JSON_AGG(
                       JSON_BUILD_OBJECT(
                           'id', ai.id,
                           'agent_id', ai."agent_id",
                           'query', ai.query,
                           'response', ai.response,
                           'confidence_score', ai."confidence_score",
                           'created_at', ai."created_at"
                       ) ORDER BY ai."created_at"
                   ) FILTER (WHERE ai.id IS NOT NULL),
                   '[]'
               ) as interactions
        FROM "Conversation" c
        LEFT JOIN "AgentInteraction" ai ON c.id = ai."conversation_id"
        WHERE c.id = %s
        GROUP BY c.id
    """
    
    CREATE_CONVERSATION = """
        INSERT INTO "Conversation" (id, "customer_id", "company_id", "current_agent_id", history) 
        VALUES (%s, %s, %s, %s, %s) 
        RETURNING *
    """
    
    CREATE_CONVERSATION_BASIC = """
        INSERT INTO "Conversation" (id, "customer_id", "company_id") 
        VALUES (%s, %s, %s) 
        RETURNING *
    """
    
    UPDATE_CONVERSATION_AGENT = """
        UPDATE "Conversation" 
        SET "current_agent_id" = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    UPDATE_CONVERSATION_HISTORY = """
        UPDATE "Conversation" 
        SET history = %s, "messages_count" = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    UPDATE_CONVERSATION_STATUS = """
        UPDATE "Conversation" 
        SET status = %s, "ended_at" = %s, "ended_by" = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    UPDATE_CONVERSATION_SENTIMENT = """
        UPDATE "Conversation" 
        SET "sentiment_score" = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    END_CONVERSATION = """
        UPDATE "Conversation" 
        SET status = 'ended', "ended_at" = CURRENT_TIMESTAMP, "ended_by" = %s,
            duration = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - "created_at")), "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    DELETE_CONVERSATION = """
        DELETE FROM "Conversation" WHERE id = %s
    """
    
    DELETE_CONVERSATIONS_BY_COMPANY = """
        DELETE FROM "Conversation" WHERE "company_id" = %s
    """

    @staticmethod
    def get_conversation_by_id_params(conversation_id: str) -> Tuple[str, tuple]:
        """Get conversation by ID parameters"""
        return ConversationQueries.GET_CONVERSATION_BY_ID, (conversation_id,)
    
    @staticmethod
    def create_conversation_params(conversation_id: str, customer_id: str, company_id: str) -> Tuple[str, tuple]:
        """Create conversation parameters"""
        return ConversationQueries.CREATE_CONVERSATION_BASIC, (conversation_id, customer_id, company_id)
    
    @staticmethod
    def get_conversations_by_company_params(company_id: str, limit: int = 50, offset: int = 0) -> Tuple[str, tuple]:
        """Get conversations by company parameters"""
        return ConversationQueries.GET_CONVERSATIONS_BY_COMPANY, (company_id, limit, offset)