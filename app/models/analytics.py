from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime, date

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
    avg_duration: float
    avg_lead_score: float

class AgentPerformance(BaseModel):
    agent_id: str
    total_calls: int
    successful_leads: int
    conversion_rate: float
    avg_duration: float
    avg_lead_score: float

class LeadDetail(BaseModel):
    call_id: str
    user_phone: str
    extracted_details: Dict[str, Any]
    lead_score: int
    conversation_duration: int
    created_at: datetime
    agent_id: str

class AnalyticsDashboard(BaseModel):
    daily_stats: List[DailyAnalytics]
    agent_performance: List[AgentPerformance]
    recent_leads: List[LeadDetail]
    total_metrics: Dict[str, Any]
