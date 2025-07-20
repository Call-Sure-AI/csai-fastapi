from fastapi import APIRouter, Depends, status
from app.models.schemas import AgentCreate, AgentUpdate, AgentResponse
from handlers.agent_handler import AgentHandler
from middleware.auth_middleware import get_current_user
from app.models.schemas import UserResponse

router = APIRouter(prefix="/api/agent", tags=["agents"])

@router.get("/", response_model=list[AgentResponse])
async def get_agents(current_user: UserResponse = Depends(get_current_user)):
    return await AgentHandler.get_all(current_user.id)

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, current_user: UserResponse = Depends(get_current_user)):
    return await AgentHandler.get_by_id(agent_id)

@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(agent: AgentCreate, current_user: UserResponse = Depends(get_current_user)):
    agent_data = agent.copy(update={"user_id": current_user.id})
    return await AgentHandler.create(agent_data)

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, update: AgentUpdate, current_user: UserResponse = Depends(get_current_user)):
    return await AgentHandler.update(agent_id, update)

@router.delete("/{agent_id}", response_model=AgentResponse)
async def delete_agent(agent_id: str, current_user: UserResponse = Depends(get_current_user)):
    return await AgentHandler.delete(agent_id) 