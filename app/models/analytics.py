from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, date
import json

class ConversationOutcome(BaseModel):
    call_id: str
    user_phone: str
    conversation_duration: int
    outcome: str
    lead_score: int
    extracted_details: Dict[str, Any]
    agent_id: str

class DailyAnalytics(BaseModel):
    date: date
    total_calls: int
    interested_leads: int
    callback_requests: int
    not_interested: int
    incomplete_calls: int
    avg_duration: Optional[float] = 0.0
    avg_lead_score: Optional[float] = 0.0
    
    @validator('avg_duration', 'avg_lead_score', pre=True)
    def handle_null_values(cls, v):
        return v if v is not None else 0.0

class AgentPerformance(BaseModel):
    agent_id: str
    total_calls: int
    successful_leads: int
    conversion_rate: float
    avg_duration: Optional[float] = 0.0
    avg_lead_score: Optional[float] = 0.0
    
    @validator('avg_duration', 'avg_lead_score', 'conversion_rate', pre=True)
    def handle_null_values(cls, v):
        return v if v is not None else 0.0

class LeadDetail(BaseModel):
    call_id: str
    user_phone: Optional[str] = None
    extracted_details: Dict[str, Any] = Field(default_factory=dict)
    lead_score: int
    conversation_duration: int
    created_at: datetime
    agent_id: str
    
    @validator('extracted_details', pre=True)
    def parse_extracted_details(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        elif v is None:
            return {}
        return v

class AnalyticsDashboard(BaseModel):
    daily_stats: List[DailyAnalytics]
    agent_performance: List[AgentPerformance]
    recent_leads: List[LeadDetail]
    total_metrics: Dict[str, Any]
