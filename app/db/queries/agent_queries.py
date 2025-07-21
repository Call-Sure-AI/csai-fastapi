from typing import List, Dict, Any, Optional
from app.models.schemas import AgentCreate, AgentUpdate
import asyncpg
import json

class AgentQueries:
    
    async def get_agents_by_user_id(self, conn: asyncpg.Connection, user_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                a.*,
                c.name as company_name,
                COUNT(conv.id) as conversation_count
            FROM agents a
            LEFT JOIN companies c ON a.company_id = c.id
            LEFT JOIN conversations conv ON a.id = conv.agent_id
            WHERE a.user_id = $1
            GROUP BY a.id, c.name
            ORDER BY a.created_at DESC
        """
        rows = await conn.fetch(query, user_id)
        return [dict(row) for row in rows]
    
    async def get_agent_by_id(self, conn: asyncpg.Connection, agent_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT 
                a.*,
                c.name as company_name,
                COUNT(conv.id) as conversation_count
            FROM agents a
            LEFT JOIN companies c ON a.company_id = c.id
            LEFT JOIN conversations conv ON a.id = conv.agent_id
            WHERE a.id = $1
            GROUP BY a.id, c.name
        """
        row = await conn.fetchrow(query, agent_id)
        return dict(row) if row else None
    
    async def get_agent_by_name_and_company(self, conn: asyncpg.Connection, name: str, company_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT * FROM agents 
            WHERE name = $1 AND company_id = $2
        """
        row = await conn.fetchrow(query, name, company_id)
        return dict(row) if row else None
    
    async def create_agent(self, conn: asyncpg.Connection, agent_data: AgentCreate) -> Dict[str, Any]:
        query = """
            INSERT INTO agents (
                user_id, name, type, is_active, company_id, prompt,
                additional_context, advanced_settings, confidence_threshold,
                files, template_id, knowledge_base_ids, database_integration_ids,
                search_config, max_response_tokens, temperature,
                image_processing_enabled, image_processing_config
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
            RETURNING *
        """
        agent_dict = agent_data.dict()
        files_json = json.dumps(agent_dict.get('files', []))
        knowledge_base_ids_json = json.dumps(agent_dict.get('knowledge_base_ids', []))
        database_integration_ids_json = json.dumps(agent_dict.get('database_integration_ids', []))
        additional_context_json = json.dumps(agent_dict.get('additional_context')) if agent_dict.get('additional_context') else None
        advanced_settings_json = json.dumps(agent_dict.get('advanced_settings')) if agent_dict.get('advanced_settings') else None
        search_config_json = json.dumps(agent_dict.get('search_config')) if agent_dict.get('search_config') else None
        image_processing_config_json = json.dumps(agent_dict.get('image_processing_config')) if agent_dict.get('image_processing_config') else None
        
        row = await conn.fetchrow(
            query,
            agent_data.user_id,
            agent_data.name,
            agent_data.type,
            agent_data.is_active,
            agent_data.company_id,
            agent_data.prompt,
            additional_context_json,
            advanced_settings_json,
            agent_data.confidence_threshold,
            files_json,
            agent_data.template_id,
            knowledge_base_ids_json,
            database_integration_ids_json,
            search_config_json,
            agent_data.max_response_tokens,
            agent_data.temperature,
            agent_data.image_processing_enabled,
            image_processing_config_json
        )
        return dict(row)
    
    async def update_agent(self, conn: asyncpg.Connection, agent_id: str, agent_data: AgentUpdate) -> Dict[str, Any]:
        update_fields = []
        values = []
        param_count = 1
        
        agent_dict = agent_data.dict(exclude_unset=True)
        
        for field, value in agent_dict.items():
            if field in ['files', 'knowledge_base_ids', 'database_integration_ids']:
                values.append(json.dumps(value))
            elif field in ['additional_context', 'advanced_settings', 'search_config', 'image_processing_config']:
                values.append(json.dumps(value) if value else None)
            else:
                values.append(value)
            
            update_fields.append(f"{field} = ${param_count}")
            param_count += 1
        
        if not update_fields:
            return await self.get_agent_by_id(conn, agent_id)

        update_fields.append(f"updated_at = NOW()")
        values.append(agent_id)
        
        query = f"""
            UPDATE agents 
            SET {', '.join(update_fields)}
            WHERE id = ${param_count}
            RETURNING *
        """
        
        row = await conn.fetchrow(query, *values)
        return dict(row)
    
    async def delete_agent(self, conn: asyncpg.Connection, agent_id: str) -> Dict[str, Any]:
        query = """
            DELETE FROM agents 
            WHERE id = $1 
            RETURNING *
        """
        row = await conn.fetchrow(query, agent_id)
        if not row:
            raise ValueError("Agent not found")
        return dict(row)
