import uuid
from fastapi import HTTPException, status
from app.db.postgres_client import postgres_client
from app.db.queries.agent_queries import AgentQueries
from app.models.agents import AgentCreate, AgentUpdate, AgentResponse

class AgentHandler:
    @staticmethod
    async def get_all(user_id: str):
        print(f'Getting agents for user {user_id}')
        query, params = AgentQueries.get_agents_by_user_id_params(user_id)
        print(f'Query: {query}')
        agents = postgres_client.client.execute_query(query, params)
        print(f'Agents: {agents}')
        return [AgentResponse(**agent) for agent in agents]

    @staticmethod
    async def get_by_id(agent_id: str):
        query, params = AgentQueries.get_agent_by_id_params(agent_id)
        agent = postgres_client.client.execute_query(query, params)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return AgentResponse(**agent[0])

    @staticmethod
    async def create(agent_data: AgentCreate):
        # Check for duplicate
        query, params = AgentQueries.get_agent_by_name_and_company_params(agent_data.name, agent_data.company_id)
        existing = postgres_client.client.execute_query(query, params)
        if existing:
            return AgentResponse(**existing[0])
        # Create agent
        agent_id = uuid.uuid4()
        agent = agent_data.dict()
        agent['id'] = agent_id
        query, params = AgentQueries.create_agent_params(agent)
        created = postgres_client.client.execute_query(query, params)
        return AgentResponse(**created[0])

    @staticmethod
    async def update(agent_id: str, update_data: AgentUpdate):
        # Check existence
        query, params = AgentQueries.get_agent_by_id_params(agent_id)
        agent = postgres_client.client.execute_query(query, params)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        # Update
        data = {k: v for k, v in update_data.dict().items() if v is not None}
        if not data:
            raise HTTPException(status_code=400, detail="No fields to update")
        query, params = AgentQueries.update_agent_params(agent_id, data)
        updated = postgres_client.client.execute_query(query, params)
        return AgentResponse(**updated[0])

    @staticmethod
    async def delete(agent_id: str):
        query, params = AgentQueries.delete_agent_params(agent_id)
        deleted = postgres_client.client.execute_query(query, params)
        if not deleted:
            raise HTTPException(status_code=404, detail="Agent not found")
        return AgentResponse(**deleted[0])
