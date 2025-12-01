# app\models\campaigns.py
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from typing import Literal

class SlotMode(str, Enum):
    PREDEFINED = "predefined"  # Fixed slots from DB
    DYNAMIC = "dynamic"        # Any time within business hours
    HYBRID = "hybrid"          # Prefer predefined, allow custom

class BusinessHours(BaseModel):
    start: str = Field(..., pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")  # HH:MM format
    end: str = Field(..., pattern="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")

class DaySchedule(BaseModel):
    mon: Optional[BusinessHours] = None
    tue: Optional[BusinessHours] = None
    wed: Optional[BusinessHours] = None
    thu: Optional[BusinessHours] = None
    fri: Optional[BusinessHours] = None
    sat: Optional[BusinessHours] = None
    sun: Optional[BusinessHours] = None

class PredefinedSlot(BaseModel):
    day: str = Field(..., pattern="^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$")
    times: List[str]  # ["09:00", "11:00", "14:00"]

class CloserShift(BaseModel):
    closer_id: str
    name: str
    shifts: List[Dict[str, str]]  # [{"day": "monday", "start": "09:00", "end": "18:00"}]

class SlotConfiguration(BaseModel):
    slot_mode: SlotMode = SlotMode.DYNAMIC
    business_hours: DaySchedule = Field(default_factory=lambda: DaySchedule(
        mon=BusinessHours(start="09:00", end="18:00"),
        tue=BusinessHours(start="09:00", end="18:00"),
        wed=BusinessHours(start="09:00", end="18:00"),
        thu=BusinessHours(start="09:00", end="18:00"),
        fri=BusinessHours(start="09:00", end="18:00")
    ))
    timezone: str = "UTC"
    slot_duration_minutes: int = Field(30, ge=5, le=480)
    buffer_minutes: int = Field(0, ge=0, le=120)
    max_bookings_per_slot: int = Field(1, ge=1, le=10)
    allow_overbooking: bool = False
    allow_custom_times: bool = False
    predefined_slots: List[PredefinedSlot] = Field(default_factory=list)
    closer_shifts: List[CloserShift] = Field(default_factory=list)
    allow_multiple_bookings_per_customer: bool = False

class SlotConfigurationResponse(SlotConfiguration):
    id: str
    campaign_id: str
    company_id: str
    created_at: datetime
    updated_at: datetime

class SlotConfigurationUpdate(BaseModel):
    slot_mode: Optional[SlotMode] = None
    business_hours: Optional[DaySchedule] = None
    timezone: Optional[str] = None
    slot_duration_minutes: Optional[int] = Field(None, ge=5, le=480)
    buffer_minutes: Optional[int] = Field(None, ge=0, le=120)
    max_bookings_per_slot: Optional[int] = Field(None, ge=1, le=10)
    allow_overbooking: Optional[bool] = None
    allow_custom_times: Optional[bool] = None
    predefined_slots: Optional[List[PredefinedSlot]] = None
    closer_shifts: Optional[List[CloserShift]] = None
    allow_multiple_bookings_per_customer: Optional[bool] = None

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