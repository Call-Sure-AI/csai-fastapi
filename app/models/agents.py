from pydantic import BaseModel, Field, validator
from typing import Optional, List
from uuid import UUID

class AgentBase(BaseModel):
    name: str = Field(..., min_length=1)
    type: Optional[str]
    company_id: UUID
    user_id: UUID

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    name: Optional[str]
    type: Optional[str]

class AgentResponse(AgentBase):
    id: UUID

    class Config:
        orm_mode = True

class CompanyResponse(BaseModel):
    id: UUID
    name: str

class ConversationResponse(BaseModel):
    id: UUID
    topic: str

class AgentDetailResponse(AgentResponse):
    companies: Optional[List[CompanyResponse]] = []
    conversations: Optional[List[ConversationResponse]] = []