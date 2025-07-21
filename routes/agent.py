from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from app.models.schemas import AgentCreate, AgentUpdate, Agent, UserResponse
from handlers.agent_handler import AgentHandler
from middleware.auth_middleware import get_current_user
import logging

logger = logging.getLogger(__name__)

# Create router with correct prefix
router = APIRouter(prefix="/agents", tags=["agents"])

# Create a dependency to get agent handler
def get_agent_handler():
    """Dependency to get agent handler instance"""
    return AgentHandler()

@router.get("/", response_model=List[Agent])
async def get_all_agents(
    current_user: UserResponse = Depends(get_current_user),
    id: Optional[str] = Query(None, description="Specific agent ID to fetch"),
    agent_handler: AgentHandler = Depends(get_agent_handler)
):
    """Get all agents for the current user"""
    try:
        user_id = current_user.id
        agents = await agent_handler.get_all_agents(user_id, id)
        return agents
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in get_all_agents: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/test")
async def test_agent_router():
    """Test endpoint to verify agent router is working - NO AUTH REQUIRED"""
    return {"message": "Agent router is working!", "status": "success"}

@router.get("/test-db")
async def test_database_connection(
    agent_handler: AgentHandler = Depends(get_agent_handler)
):
    """Test database connection - NO AUTH REQUIRED"""
    try:
        # Test database query
        query = "SELECT 1 as test, NOW() as current_time"
        result = await agent_handler.db.execute_query_one(query)
        return {
            "status": "success",
            "message": "Database connection working",
            "database_time": result['current_time'] if result else None
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database connection failed: {str(e)}"
        }

@router.get("/{agent_id}", response_model=Agent)
async def get_agent_by_id(
    agent_id: str,
    current_user: UserResponse = Depends(get_current_user),
    agent_handler: AgentHandler = Depends(get_agent_handler)
):
    """Get a specific agent by ID"""
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
    current_user: UserResponse = Depends(get_current_user),
    agent_handler: AgentHandler = Depends(get_agent_handler)
):
    """Get all agents for a specific user"""
    try:
        agents = await agent_handler.get_agents_by_user_id(user_id)
        return agents
    except Exception as e:
        logger.error(f"Error in get_agents_by_user_id: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/", response_model=Agent, status_code=201)
async def create_agent(
    agent_data: AgentCreate,
    current_user: UserResponse = Depends(get_current_user),
    agent_handler: AgentHandler = Depends(get_agent_handler)
):
    """Create a new agent"""
    try:
        user_id = current_user.id
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
    current_user: UserResponse = Depends(get_current_user),
    agent_handler: AgentHandler = Depends(get_agent_handler)
):
    """Update an existing agent"""
    try:
        user_id = current_user.id
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
    current_user: UserResponse = Depends(get_current_user),
    agent_handler: AgentHandler = Depends(get_agent_handler)
):
    """Delete an agent"""
    try:
        user_id = current_user.id
        await agent_handler.delete_agent(agent_id, user_id)
        return None
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in delete_agent: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")