from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from app.models.schemas import AgentCreate, AgentUpdate, Agent
from handlers.agent_handler import AgentHandler
from middleware.auth_middleware import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])
agent_handler = AgentHandler()

@router.get("/", response_model=List[Agent])
async def get_all_agents(
    current_user: dict = Depends(get_current_user),
    id: Optional[str] = Query(None, description="Specific agent ID to fetch")
):
    try:
        user_id = current_user["id"]
        agents = await agent_handler.get_all_agents(user_id, id)
        return agents
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in get_all_agents: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{agent_id}", response_model=Agent)
async def get_agent_by_id(
    agent_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        agent = await agent_handler.get_agent_by_id(agent_id)
        return agent
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in get_agent_by_id: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/user/{user_id}", response_model=List[Agent])
async def get_agents_by_user_id(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        agents = await agent_handler.get_agents_by_user_id(user_id)
        return agents
    except Exception as e:
        logger.error(f"Error in get_agents_by_user_id: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/", response_model=Agent, status_code=201)
async def create_agent(
    agent_data: AgentCreate,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user["id"]
        agent = await agent_handler.create_agent(agent_data, user_id)
        return agent
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in create_agent: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{agent_id}", response_model=Agent)
async def update_agent(
    agent_id: str,
    agent_data: AgentUpdate,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user["id"]
        agent = await agent_handler.update_agent(agent_id, agent_data, user_id)
        return agent
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in update_agent: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user["id"]
        await agent_handler.delete_agent(agent_id, user_id)
        return None
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in delete_agent: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")