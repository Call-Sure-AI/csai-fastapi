from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class CalendarType(str, Enum):
    GOOGLE = "google"
    OUTLOOK = "outlook"
    CALENDLY = "calendly"
    OTHER = "other"

class DataMapping(BaseModel):
    csv_column: str
    mapped_to: str
    required: bool = False

class CalendarBooking(BaseModel):
    calendar_type: CalendarType
    meeting_duration_minutes: int = Field(..., gt=0, le=480)
    buffer_time_minutes: int = Field(0, ge=0, le=120)
    send_invite_to_lead: bool = True
    send_invite_to_team: bool = True
    team_email_addresses: List[EmailStr]
    calendar_credentials: Optional[Dict[str, Any]] = None

class AutomationSettings(BaseModel):
    email_template: Optional[str] = None
    call_script: Optional[str] = None
    max_call_attempts: int = Field(3, ge=1, le=10)
    call_interval_hours: int = Field(24, ge=1, le=168)  # Max 1 week
    enable_followup_emails: bool = True
    followup_email_template: Optional[str] = None

class CreateCampaignRequest(BaseModel):
    campaign_name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    agent_id: Optional[str] = None
    data_mapping: List[DataMapping]
    booking: CalendarBooking
    automation: AutomationSettings

class CampaignResponse(BaseModel):
    id: str
    agent_id: str | None = None
    campaign_name: str
    description: Optional[str]
    company_id: str
    created_by: str
    status: str
    leads_count: int
    csv_file_path: Optional[str] # This field seems to be unused, you should remove it or rename it.
    leads_file_url: Optional[str] # Add the new field for the S3 URL
    data_mapping: List[DataMapping]
    booking: CalendarBooking
    automation: AutomationSettings
    created_at: datetime
    updated_at: datetime

class CampaignLead(BaseModel):
    id: str
    campaign_id: str
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    company: Optional[str]
    custom_fields: Dict[str, Any]
    call_attempts: int = 0
    last_call_at: Optional[datetime] = None
    status: str = "pending"
    created_at: datetime

class UpdateCampaignRequest(BaseModel):
    campaign_name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=1000)
    agent_id: str | None = None
    data_mapping: List[DataMapping] | None = None
    status: Optional[str] = None
    booking: CalendarBooking | None = None
    automation: AutomationSettings | None = None
    status: str | None = None


class AgentAssignRequest(BaseModel):
    agent_ids: List[str] = Field(..., min_items=1)

class AgentSettingsPayload(BaseModel):
    is_active: bool | None = None
    max_response_tokens: int | None = Field(None, ge=1)
    temperature: float | None = Field(None, ge=0, le=2)