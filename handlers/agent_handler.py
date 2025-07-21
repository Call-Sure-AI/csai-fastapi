from typing import List, Optional, Dict, Any
from app.db.postgres_client import get_db_connection
from app.db.queries.agent_queries import AgentQueries
from app.utils.activity_logger import ActivityLogger
from app.models.schemas import AgentCreate, AgentUpdate, Agent
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)

class AgentHandler:
    def __init__(self):
        self.agent_queries = AgentQueries()
        self.activity_logger = ActivityLogger()

    async def get_all_agents(self, user_id: str, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            if agent_id:
                return await self.get_agent_by_id(agent_id)
            
            async with get_db_connection() as conn:
                agents = await self.agent_queries.get_agents_by_user_id(conn, user_id)
                return agents
        except Exception as error:
            logger.error(f"Error fetching agents: {error}")
            raise Exception("Internal server error")

    async def get_agent_by_id(self, agent_id: str) -> Dict[str, Any]:
        try:
            async with get_db_connection() as conn:
                agent = await self.agent_queries.get_agent_by_id(conn, agent_id)
                
                if not agent:
                    raise ValueError("Agent not found")
                    
                return agent
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error fetching agent: {error}")
            raise Exception("Internal server error")

    async def get_agents_by_user_id(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            async with get_db_connection() as conn:
                agents = await self.agent_queries.get_agents_by_user_id(conn, user_id)
                return agents
        except Exception as error:
            logger.error(f"Error fetching agents: {error}")
            raise Exception("Internal server error")

    async def create_agent(self, agent_data: AgentCreate, user_id: str) -> Dict[str, Any]:
        try:
            logger.info(f"Agent creation request received: {agent_data.dict()}")
    
            if not agent_data.company_id:
                logger.error("Missing company_id in agent creation request")
                raise ValueError("company_id is required")
            
            async with get_db_connection() as conn:
                existing_agent = await self.agent_queries.get_agent_by_name_and_company(
                    conn, agent_data.name, agent_data.company_id
                )

                if existing_agent:
                    logger.info(f'Agent already exists with name "{agent_data.name}" for company ID "{agent_data.company_id}"')
                    
                    try:
                        await self.activity_logger.log({
                            'user_id': user_id,
                            'action': 'DUPLICATE_ATTEMPT',
                            'entity_type': 'AGENT',
                            'entity_id': existing_agent['id'],
                            'metadata': {
                                'name': existing_agent['name'],
                                'type': existing_agent['type'],
                                'company_id': existing_agent['company_id']
                            }
                        })
                    except Exception as log_error:
                        logger.error(f'Failed to log duplicate agent attempt: {log_error}')
                    
                    return existing_agent

                agent = await self.agent_queries.create_agent(conn, agent_data)
                
                logger.info(f'Successfully created agent with ID "{agent["id"]}" for company ID "{agent["company_id"]}"')

                try:
                    await self.activity_logger.log({
                        'user_id': user_id,
                        'action': 'CREATE',
                        'entity_type': 'AGENT',
                        'entity_id': agent['id'],
                        'metadata': {
                            'name': agent['name'],
                            'type': agent['type'],
                            'company_id': agent['company_id']
                        }
                    })
                except Exception as log_error:
                    logger.error(f'Failed to log agent creation activity: {log_error}')
                
                return agent
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error creating agent: {error}")
            raise Exception("Internal server error")

    async def update_agent(self, agent_id: str, agent_data: AgentUpdate, user_id: str) -> Dict[str, Any]:
        try:
            async with get_db_connection() as conn:
                existing_agent = await self.agent_queries.get_agent_by_id(conn, agent_id)
                
                if not existing_agent:
                    raise ValueError("Agent not found")
            
                agent = await self.agent_queries.update_agent(conn, agent_id, agent_data)
                
                try:
                    await self.activity_logger.log({
                        'user_id': user_id,
                        'action': 'UPDATE',
                        'entity_type': 'AGENT',
                        'entity_id': agent['id'],
                        'metadata': {
                            'updated_fields': agent_data.dict(exclude_unset=True)
                        }
                    })
                except Exception as log_error:
                    logger.error(f'Failed to log agent update activity: {log_error}')
                
                return agent
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error updating agent: {error}")
            raise Exception("Internal server error")

    async def delete_agent(self, agent_id: str, user_id: str) -> Dict[str, Any]:
        try:
            async with get_db_connection() as conn:
                agent = await self.agent_queries.get_agent_by_id(conn, agent_id)
                
                if not agent:
                    raise ValueError("Agent not found")

                deleted_agent = await self.agent_queries.delete_agent(conn, agent_id)
                
                try:
                    await self.activity_logger.log({
                        'user_id': user_id,
                        'action': 'DELETE',
                        'entity_type': 'AGENT',
                        'entity_id': agent_id,
                        'metadata': {
                            'agent_name': agent['name']
                        }
                    })
                except Exception as log_error:
                    logger.error(f'Failed to log agent deletion activity: {log_error}')
                
                return deleted_agent
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error deleting agent: {error}")
            raise Exception("Internal server error")
