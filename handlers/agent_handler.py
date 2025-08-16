from typing import List, Optional, Dict, Any
from app.db.postgres_client import postgres_client
from app.models.schemas import AgentCreate, AgentUpdate, Agent
from pydantic import ValidationError
import logging
import json
import uuid
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class AgentHandler:
    def __init__(self):
        self._db = None
        
    @property
    def db(self):
        """Lazy database access"""
        if self._db is None:
            self._db = postgres_client.client
        return self._db
    
    def _parse_json_fields(self, agent: Dict[str, Any]) -> Dict[str, Any]:
        """Parse JSON string fields to dictionaries"""
        json_fields = [
            'additional_context', 
            'advanced_settings', 
            'files', 
            'knowledge_base_ids', 
            'database_integration_ids',
            'search_config',
            'image_processing_config'
        ]
        
        for field in json_fields:
            if field in agent and agent[field] is not None:
                if isinstance(agent[field], str):
                    try:
                        agent[field] = json.loads(agent[field])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON field {field}: {agent[field]}")
                        agent[field] = None
        
        return agent
        
    async def get_all_agents(self, user_id: str, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all agents for a user or a specific agent"""
        try:
            logger.info(f"get_all_agents called with user_id: {user_id}, agent_id: {agent_id}")
            
            if agent_id:
                logger.info(f"Fetching specific agent with id: {agent_id}")
                agent = await self.get_agent_by_id(agent_id)
                return [agent] if agent else []
            
            query = """
                SELECT 
                    a.*,
                    c.name as company_name
                FROM "Agent" a
                LEFT JOIN "Company" c ON a.company_id = c.id
                WHERE a.user_id = $1
                ORDER BY a.created_at DESC
            """
            
            logger.info(f"Executing query with user_id: {user_id}")
            agents = await self.db.execute_query(query, (user_id,))
            
            logger.info(f"Query result type: {type(agents)}, value: {agents}")
            
            if agents is None:
                logger.warning(f"Query returned None for user_id: {user_id}")
                return []
            
            logger.info(f"Found {len(agents)} agents for user_id: {user_id}")
            
            # Parse JSON fields for each agent
            parsed_agents = [self._parse_json_fields(agent) for agent in agents]
            logger.info(f"Returning {len(parsed_agents)} parsed agents")
            
            return parsed_agents
            
        except Exception as error:
            logger.error(f"Error fetching agents: {error}", exc_info=True)
            raise Exception("Internal server error")


    async def get_agent_by_id(self, agent_id: str) -> Dict[str, Any]:
        """Get a specific agent by ID"""
        try:
            query = """
                SELECT 
                    a.*,
                    c.name as company_name
                FROM "Agent" a
                LEFT JOIN "Company" c ON a.company_id = c.id
                WHERE a.id = $1
            """
            
            agent = await self.db.execute_query_one(query, (agent_id,))
            
            if not agent:
                raise ValueError("Agent not found")
            
            # Parse JSON fields
            return self._parse_json_fields(agent)
            
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error fetching agent: {error}")
            raise Exception("Internal server error")

    async def get_agents_by_user_id(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all agents for a specific user"""
        try:
            query = """
                SELECT 
                    a.*,
                    c.name as company_name
                FROM "Agent" a
                LEFT JOIN "Company" c ON a.company_id = c.id
                WHERE a.user_id = $1
                ORDER BY a.created_at DESC
            """
            
            agents = await self.db.execute_query(query, (user_id,))
            # Parse JSON fields for each agent
            return [self._parse_json_fields(agent) for agent in agents]
            
        except Exception as error:
            logger.error(f"Error fetching agents: {error}")
            raise Exception("Internal server error")

    async def create_agent(self, agent_data: AgentCreate, user_id: str) -> Dict[str, Any]:
        """Create a new agent"""
        try:
            logger.info(f"Agent creation request received: {agent_data.dict()}")
    
            if not agent_data.company_id:
                logger.error("Missing company_id in agent creation request")
                raise ValueError("company_id is required")
            
            # Check if agent already exists
            check_query = """
                SELECT * FROM "Agent" 
                WHERE name = $1 AND company_id = $2
            """
            existing_agents = await self.db.execute_query(
                check_query, (agent_data.name, agent_data.company_id)
            )
            
            if existing_agents:
                logger.info(f'Agent already exists with name "{agent_data.name}" for company ID "{agent_data.company_id}"')
                return self._parse_json_fields(existing_agents[0])

            # Create new agent
            agent_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            # Prepare JSON fields
            agent_dict = agent_data.dict()
            
            insert_query = """
                INSERT INTO "Agent" (
                    id, user_id, name, type, is_active, company_id, prompt,
                    additional_context, advanced_settings, confidence_threshold,
                    files, template_id, knowledge_base_ids, database_integration_ids,
                    search_config, max_response_tokens, temperature,
                    image_processing_enabled, image_processing_config,
                    created_at, updated_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10,
                    $11, $12, $13, $14, $15::jsonb, 
                    $16, $17, $18, $19::jsonb, $20, $21
                )
                RETURNING *
            """
            
            params = (
                agent_id,
                user_id,
                agent_data.name,
                agent_data.type,
                agent_data.is_active,
                agent_data.company_id,
                agent_data.prompt,
                json.dumps(agent_dict.get('additional_context')) if agent_dict.get('additional_context') else None,
                json.dumps(agent_dict.get('advanced_settings')) if agent_dict.get('advanced_settings') else None,
                agent_data.confidence_threshold,
                agent_data.files or [],
                agent_data.template_id,
                agent_data.knowledge_base_ids or [],
                agent_data.database_integration_ids or [],
                json.dumps(agent_dict.get('search_config')) if agent_dict.get('search_config') else None,
                agent_data.max_response_tokens,
                agent_data.temperature,
                agent_data.image_processing_enabled,
                json.dumps(agent_dict.get('image_processing_config')) if agent_dict.get('image_processing_config') else None,
                now,
                now
            )
            
            result = await self.db.execute_query_one(insert_query, params)
            
            if not result:
                raise Exception("Failed to create agent")
                
            logger.info(f'Successfully created agent with ID "{result["id"]}" for company ID "{result["company_id"]}"')
            
            # Log activity asynchronously (fire and forget) - if activities table exists
            try:
                activity_query = """
                    INSERT INTO activities (user_id, action, entity_type, entity_id, metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5::jsonb, NOW())
                """
                activity_metadata = {
                    'name': result['name'],
                    'type': result['type'],
                    'company_id': result['company_id']
                }
                # Don't await this - let it run in background
                try:
                    await self.db.execute_insert(
                        activity_query,
                        (user_id, 'CREATE', 'AGENT', result['id'], json.dumps(activity_metadata))
                    )
                    logger.info(f"Activity logged for agent creation: {result['id']}")
                except Exception as log_error:
                    logger.warning(f'Failed to log agent creation activity: {log_error}')
            except Exception as log_error:
                # Don't fail if activities table doesn't exist
                logger.warning(f'Failed to log agent creation activity: {log_error}')
            
            return self._parse_json_fields(result)
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error creating agent: {error}")
            raise Exception("Internal server error")

    async def update_agent(self, agent_id: str, agent_data: AgentUpdate, user_id: str) -> Dict[str, Any]:
        """Update an existing agent"""
        try:
            # Check if agent exists
            existing_agent = await self.get_agent_by_id(agent_id)
            
            if not existing_agent:
                raise ValueError("Agent not found")
            
            # Build update query dynamically
            update_fields = []
            values = []
            param_count = 1
            
            agent_dict = agent_data.dict(exclude_unset=True)
            
            for field, value in agent_dict.items():
                if field in ['files', 'knowledge_base_ids', 'database_integration_ids']:
                    values.append(json.dumps(value))
                    update_fields.append(f"{field} = ${param_count}::jsonb")
                elif field in ['additional_context', 'advanced_settings', 'search_config', 'image_processing_config']:
                    values.append(json.dumps(value) if value else None)
                    update_fields.append(f"{field} = ${param_count}::jsonb")
                else:
                    values.append(value)
                    update_fields.append(f"{field} = ${param_count}")
                param_count += 1
            
            if not update_fields:
                return existing_agent

            update_fields.append(f"updated_at = ${param_count}")
            values.append(datetime.utcnow())
            param_count += 1
            
            values.append(agent_id)
            
            query = f"""
                UPDATE "Agent" 
                SET {', '.join(update_fields)}
                WHERE id = ${param_count}
                RETURNING *
            """
            
            result = await self.db.execute_query_one(query, tuple(values))
            
            if not result:
                raise Exception("Failed to update agent")
            
            # Log activity asynchronously - if activities table exists
            try:
                activity_query = """
                    INSERT INTO activities (user_id, action, entity_type, entity_id, metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5::jsonb, NOW())
                """
                activity_metadata = {'updated_fields': list(agent_dict.keys())}
                asyncio.create_task(
                    self.db.execute_insert(
                        activity_query,
                        (user_id, 'UPDATE', 'AGENT', agent_id, json.dumps(activity_metadata))
                    )
                )
            except Exception as log_error:
                logger.warning(f'Failed to log agent update activity: {log_error}')
                
            return self._parse_json_fields(result)
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error updating agent: {error}")
            raise Exception("Internal server error")

    async def delete_agent(self, agent_id: str, user_id: str) -> Dict[str, Any]:
        """Delete an agent"""
        try:
            # Check if agent exists
            agent = await self.get_agent_by_id(agent_id)
            
            if not agent:
                raise ValueError("Agent not found")

            query = """
                DELETE FROM "Agent" 
                WHERE id = $1 
                RETURNING *
            """
            
            result = await self.db.execute_query_one(query, (agent_id,))
            
            if not result:
                raise ValueError("Agent not found")
            
            # Log activity asynchronously - if activities table exists
            try:
                activity_query = """
                    INSERT INTO activities (user_id, action, entity_type, entity_id, metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5::jsonb, NOW())
                """
                activity_metadata = {'agent_name': agent['name']}
                asyncio.create_task(
                    self.db.execute_insert(
                        activity_query,
                        (user_id, 'DELETE', 'AGENT', agent_id, json.dumps(activity_metadata))
                    )
                )
            except Exception as log_error:
                logger.warning(f'Failed to log agent deletion activity: {log_error}')
                
            return self._parse_json_fields(result)
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error deleting agent: {error}")
            raise Exception("Internal server error")