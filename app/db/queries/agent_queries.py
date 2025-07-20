from typing import Dict, List, Optional, Tuple
from datetime import datetime

class AgentQueries:
    """All SQL queries related to Agent table"""
    
    GET_AGENT_BY_ID = """
        SELECT * FROM "Agent" WHERE id = %s
    """
    
    GET_AGENTS_BY_USER = """
        SELECT * FROM "Agent" WHERE "user_id" = %s AND "is_active" = true
    """
    
    GET_AGENTS_BY_COMPANY = """
        SELECT * FROM "Agent" WHERE "company_id" = %s AND "is_active" = true
    """
    
    GET_AGENT_WITH_STATS = """
        SELECT a.*, 
               COUNT(ai.id) as total_interactions,
               AVG(ai."confidence_score") as avg_confidence,
               AVG(ai."response_time") as avg_response_time
        FROM "Agent" a
        LEFT JOIN "AgentInteraction" ai ON a.id = ai."agent_id"
        WHERE a.id = %s
        GROUP BY a.id
    """
    
    CREATE_AGENT = """
        INSERT INTO "Agent" (
            id, "user_id", name, type, "company_id", prompt, 
            "additional_context", "confidence_threshold", files
        ) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) 
        RETURNING *
    """
    
    CREATE_AGENT_BASIC = """
        INSERT INTO "Agent" (id, "user_id", name, type, prompt) 
        VALUES (%s, %s, %s, %s, %s) 
        RETURNING *
    """
    
    UPDATE_AGENT_PROMPT = """
        UPDATE "Agent" 
        SET prompt = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    UPDATE_AGENT_SETTINGS = """
        UPDATE "Agent" 
        SET "advanced_settings" = %s, "confidence_threshold" = %s, 
            temperature = %s, "max_response_tokens" = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    UPDATE_AGENT_STATS = """
        UPDATE "Agent" 
        SET "average_confidence" = %s, "average_response_time" = %s, 
            "success_rate" = %s, "total_interactions" = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    DEACTIVATE_AGENT = """
        UPDATE "Agent" 
        SET "is_active" = false, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    DELETE_AGENT = """
        DELETE FROM "Agent" WHERE id = %s
    """
    
    DELETE_AGENTS_BY_USER = """
        DELETE FROM "Agent" WHERE "user_id" = %s
    """
    
    DELETE_AGENTS_BY_COMPANY = """
        DELETE FROM "Agent" WHERE "company_id" = %s
    """

    @staticmethod
    def get_agent_by_id_params(agent_id):
        return (
            'SELECT * FROM "Agent" WHERE id = %s',
            (str(agent_id),)
        )

    @staticmethod
    def get_agents_by_user_id_params(user_id):
        return (
            'SELECT * FROM "Agent" WHERE user_id = %s',
            (str(user_id),)
        )

    @staticmethod
    def get_agent_by_name_and_company_params(name, company_id):
        return (
            'SELECT * FROM "Agent" WHERE name = %s AND company_id = %s',
            (name, str(company_id))
        )

    @staticmethod
    def create_agent_params(agent):
        return (
            '''
            INSERT INTO "Agent" (id, name, type, company_id, user_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            ''',
            (str(agent.id), agent.name, agent.type, str(agent.company_id), str(agent.user_id))
        )

    @staticmethod
    def update_agent_params(agent_id, data):
        set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
        return (
            f'UPDATE "Agent" SET {set_clause} WHERE id = %s RETURNING *',
            tuple(data.values()) + (str(agent_id),)
        )

    @staticmethod
    def delete_agent_params(agent_id):
        return (
            'DELETE FROM "Agent" WHERE id = %s RETURNING *',
            (str(agent_id),)
        )