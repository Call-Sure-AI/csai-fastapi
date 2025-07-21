from pydantic import BaseModel, Field, validator
from typing import Optional, List, Any
from uuid import UUID

class AgentBase(BaseModel):
    name: str = Field(..., min_length=1)
    type: Optional[str]
    company_id: Optional[str]
    user_id: str
    prompt: Optional[str]
    additional_context: Optional[Any]
    confidence_threshold: Optional[float]
    files: Optional[List[str]]
    template_id: Optional[str]
    advanced_settings: Optional[Any]
    is_active: Optional[bool]
    average_confidence: Optional[float]
    average_response_time: Optional[float]
    database_integration_ids: Optional[List[str]]

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