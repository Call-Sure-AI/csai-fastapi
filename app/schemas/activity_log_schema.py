from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ActivityUser(BaseModel):
    email: str
    initial: str


class ActivityEvent(BaseModel):
    event: str
    user: ActivityUser
    details: str
    ip: Optional[str]
    time: str
    date: str
    raw_time: datetime


class ActivitySummary(BaseModel):
    total_events: int
    today: int
    creates: int
    updates: int


class ActivityLogResponse(BaseModel):
    summary: ActivitySummary
    events: List[ActivityEvent]
    pagination: dict
