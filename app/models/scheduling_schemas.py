# app\models\scheduling_schemas.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, date, time
from enum import Enum

class DayOfWeek(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

class ScheduleType(str, Enum):
    FIXED = "fixed"
    FLEXIBLE = "flexible"
    SHIFT = "shift"
    ON_DEMAND = "on_demand"

class BookingRuleType(str, Enum):
    MIN_NOTICE = "min_notice"
    MAX_PER_DAY = "max_per_day"
    MAX_PER_WEEK = "max_per_week"
    BLACKOUT_DATES = "blackout_dates"
    ALLOWED_DURATION = "allowed_duration"
    BOOKING_WINDOW = "booking_window"
    CANCELLATION_POLICY = "cancellation_policy"

class OverrideType(str, Enum):
    TIME_OFF = "time_off"
    HOLIDAY = "holiday"
    SPECIAL_HOURS = "special_hours"
    BLOCKED = "blocked"

class AssignmentMethod(str, Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_BUSY = "least_busy"
    MOST_AVAILABLE = "most_available"
    RANDOM = "random"
    MANUAL = "manual"
    SKILL_BASED = "skill_based"

class PolicyType(str, Enum):
    GLOBAL = "global"
    DEPARTMENT = "department"
    TEAM = "team"
    ROLE = "role"

class TimeBlock(BaseModel):
    start_time: time
    end_time: time
    is_available: bool = True
    
    @field_validator('end_time')
    @classmethod
    def validate_end_after_start(cls, v, info):
        if 'start_time' in info.data and v <= info.data['start_time']:
            raise ValueError('End time must be after start time')
        return v

class AvailabilityTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    schedule_type: ScheduleType = Field(default=ScheduleType.FIXED)
    timezone: str = Field(default="UTC")
    is_default: bool = Field(default=False)

    monday: List[TimeBlock] = Field(default_factory=list)
    tuesday: List[TimeBlock] = Field(default_factory=list)
    wednesday: List[TimeBlock] = Field(default_factory=list)
    thursday: List[TimeBlock] = Field(default_factory=list)
    friday: List[TimeBlock] = Field(default_factory=list)
    saturday: List[TimeBlock] = Field(default_factory=list)
    sunday: List[TimeBlock] = Field(default_factory=list)
    slot_duration_minutes: int = Field(default=30, ge=5, le=480)
    advance_booking_days: int = Field(default=60, ge=1, le=365)
    minimum_notice_hours: int = Field(default=2, ge=0, le=168)

class AvailabilityTemplateCreate(AvailabilityTemplateBase):
    user_id: Optional[str] = None
    team_id: Optional[str] = None

class AvailabilityTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    schedule_type: Optional[ScheduleType] = None
    timezone: Optional[str] = None
    is_default: Optional[bool] = None
    monday: Optional[List[TimeBlock]] = None
    tuesday: Optional[List[TimeBlock]] = None
    wednesday: Optional[List[TimeBlock]] = None
    thursday: Optional[List[TimeBlock]] = None
    friday: Optional[List[TimeBlock]] = None
    saturday: Optional[List[TimeBlock]] = None
    sunday: Optional[List[TimeBlock]] = None
    slot_duration_minutes: Optional[int] = Field(None, ge=5, le=480)
    advance_booking_days: Optional[int] = Field(None, ge=1, le=365)
    minimum_notice_hours: Optional[int] = Field(None, ge=0, le=168)

class AvailabilityTemplateResponse(AvailabilityTemplateBase):
    id: str
    company_id: str
    user_id: Optional[str]
    team_id: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class BookingRuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    rule_type: BookingRuleType
    is_active: bool = Field(default=True)
    priority: int = Field(default=0, ge=0, le=100)

    parameters: Dict[str, Any] = Field(default_factory=dict)

    applies_to_all: bool = Field(default=False)
    user_ids: List[str] = Field(default_factory=list)
    team_ids: List[str] = Field(default_factory=list)
    meeting_type_ids: List[str] = Field(default_factory=list)

class BookingRuleCreate(BookingRuleBase):
    pass

class BookingRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=0, le=100)
    parameters: Optional[Dict[str, Any]] = None
    applies_to_all: Optional[bool] = None
    user_ids: Optional[List[str]] = None
    team_ids: Optional[List[str]] = None
    meeting_type_ids: Optional[List[str]] = None

class BookingRuleResponse(BookingRuleBase):
    id: str
    company_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class RecurringAvailabilityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    user_id: str
    day_of_week: DayOfWeek
    time_blocks: List[TimeBlock]
    effective_from: date
    effective_until: Optional[date] = None
    is_active: bool = Field(default=True)
    repeat_pattern: str = Field(default="weekly", description="weekly, biweekly, monthly")
    exceptions: List[date] = Field(default_factory=list)

class RecurringAvailabilityCreate(RecurringAvailabilityBase):
    pass

class RecurringAvailabilityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    time_blocks: Optional[List[TimeBlock]] = None
    effective_until: Optional[date] = None
    is_active: Optional[bool] = None
    repeat_pattern: Optional[str] = None
    exceptions: Optional[List[date]] = None

class RecurringAvailabilityResponse(RecurringAvailabilityBase):
    id: str
    company_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ScheduleOverrideBase(BaseModel):
    user_id: str
    override_type: OverrideType
    start_date: date
    end_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    reason: Optional[str] = Field(None, max_length=500)
    is_all_day: bool = Field(default=True)
    replacement_user_id: Optional[str] = None

class ScheduleOverrideCreate(ScheduleOverrideBase):
    pass

class ScheduleOverrideUpdate(BaseModel):
    override_type: Optional[OverrideType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    reason: Optional[str] = Field(None, max_length=500)
    is_all_day: Optional[bool] = None
    replacement_user_id: Optional[str] = None

class ScheduleOverrideResponse(ScheduleOverrideBase):
    id: str
    company_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class BufferRuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    meeting_type: Optional[str] = None
    buffer_before_minutes: int = Field(default=0, ge=0, le=120)
    buffer_after_minutes: int = Field(default=15, ge=0, le=120)
    applies_to_all_meetings: bool = Field(default=True)
    is_active: bool = Field(default=True)

class BufferRuleCreate(BufferRuleBase):
    pass

class BufferRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    buffer_before_minutes: Optional[int] = Field(None, ge=0, le=120)
    buffer_after_minutes: Optional[int] = Field(None, ge=0, le=120)
    applies_to_all_meetings: Optional[bool] = None
    is_active: Optional[bool] = None

class BufferRuleResponse(BufferRuleBase):
    id: str
    company_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class TeamScheduleBase(BaseModel):
    team_id: str
    name: str = Field(..., min_length=1, max_length=255)
    assignment_method: AssignmentMethod
    allow_member_preference: bool = Field(default=True)
    collective_availability: bool = Field(default=False)
    min_team_members_available: int = Field(default=1, ge=1)
    rotation_settings: Optional[Dict[str, Any]] = None
    skill_requirements: Optional[List[str]] = None

class TeamScheduleCreate(TeamScheduleBase):
    member_ids: List[str]

class TeamScheduleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    assignment_method: Optional[AssignmentMethod] = None
    allow_member_preference: Optional[bool] = None
    collective_availability: Optional[bool] = None
    min_team_members_available: Optional[int] = Field(None, ge=1)
    rotation_settings: Optional[Dict[str, Any]] = None
    skill_requirements: Optional[List[str]] = None
    member_ids: Optional[List[str]] = None

class TeamScheduleResponse(TeamScheduleBase):
    id: str
    company_id: str
    member_ids: List[str]
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AvailabilityCheckRequest(BaseModel):
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    start_date: date
    end_date: date
    duration_minutes: int = Field(30, ge=5, le=480)
    timezone: str = Field(default="UTC")
    include_buffer: bool = Field(default=True)
    meeting_type: Optional[str] = None

class TimeSlot(BaseModel):
    start: datetime
    end: datetime
    available: bool
    capacity: int = Field(default=1, ge=0)
    user_ids: Optional[List[str]] = None

class AvailabilityCheckResponse(BaseModel):
    available_slots: List[TimeSlot]
    total_slots: int
    timezone: str
    next_available: Optional[datetime] = None


class BulkAvailabilityRequest(BaseModel):
    user_ids: Optional[List[str]] = None
    team_ids: Optional[List[str]] = None
    start_date: date
    end_date: date
    duration_minutes: int = Field(30, ge=5, le=480)
    find_common_slots: bool = Field(default=False)
    min_attendees: int = Field(default=1, ge=1)

class BulkAvailabilityResponse(BaseModel):
    results: Dict[str, List[TimeSlot]]
    common_slots: Optional[List[TimeSlot]] = None
    total_available_slots: int

class OptimalTimesRequest(BaseModel):
    participants: List[str]
    duration_minutes: int = Field(30, ge=5, le=480)
    date_range_start: date
    date_range_end: date
    preferred_times: Optional[List[str]] = None
    avoid_times: Optional[List[str]] = None
    timezone_preferences: Optional[Dict[str, str]] = None
    meeting_type: Optional[str] = None
    urgency: Literal["low", "medium", "high"] = "medium"

class SuggestedTime(BaseModel):
    start: datetime
    end: datetime
    score: float = Field(ge=0, le=1)
    attendee_availability: Dict[str, bool]
    reasons: List[str]

class OptimalTimesResponse(BaseModel):
    suggested_times: List[SuggestedTime]
    best_time: Optional[SuggestedTime] = None
    analysis: Dict[str, Any]

class ScheduleConflictRequest(BaseModel):
    user_ids: List[str]
    start_time: datetime
    end_time: datetime
    ignore_booking_ids: Optional[List[str]] = None
    check_buffers: bool = Field(default=True)
    check_policies: bool = Field(default=True)

class ConflictDetail(BaseModel):
    user_id: str
    conflict_type: str
    conflicting_booking_id: Optional[str] = None
    description: str
    severity: Literal["low", "medium", "high"]

class ScheduleConflictResponse(BaseModel):
    has_conflicts: bool
    conflicts: List[ConflictDetail]
    resolution_suggestions: List[str]

class ResourceAllocationRequest(BaseModel):
    booking_id: str
    resource_types: List[str]
    start_time: datetime
    end_time: datetime
    preferences: Optional[Dict[str, Any]] = None
    required_capacity: Optional[Dict[str, int]] = None

class AllocatedResource(BaseModel):
    resource_id: str
    resource_type: str
    resource_name: str
    capacity: int
    location: Optional[str] = None
    cost: Optional[float] = None

class ResourceAllocationResponse(BaseModel):
    booking_id: str
    allocated_resources: List[AllocatedResource]
    total_cost: Optional[float] = None
    alternatives: Optional[List[AllocatedResource]] = None

class SchedulePolicyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    policy_type: PolicyType
    is_active: bool = Field(default=True)
    priority: int = Field(default=0, ge=0, le=100)

    rules: Dict[str, Any] = Field(default_factory=dict)

    applies_to_departments: Optional[List[str]] = None
    applies_to_teams: Optional[List[str]] = None
    applies_to_roles: Optional[List[str]] = None

    enforcement_level: Literal["strict", "flexible", "advisory"] = "flexible"
    exceptions: Optional[List[str]] = None

class SchedulePolicyCreate(SchedulePolicyBase):
    pass

class SchedulePolicyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=0, le=100)
    rules: Optional[Dict[str, Any]] = None
    enforcement_level: Optional[Literal["strict", "flexible", "advisory"]] = None

class SchedulePolicyResponse(SchedulePolicyBase):
    id: str
    company_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ScheduleAnalyticsResponse(BaseModel):
    period_start: date
    period_end: date

    total_available_hours: float
    total_booked_hours: float
    utilization_rate: float

    total_bookings: int
    cancelled_bookings: int
    rescheduled_bookings: int
    no_show_bookings: int

    average_booking_duration: float
    average_lead_time: float
    peak_hours: List[Dict[str, Any]]
    slow_hours: List[Dict[str, Any]]

    busiest_users: List[Dict[str, Any]]
    least_utilized_users: List[Dict[str, Any]]
    team_distribution: Dict[str, int]

    day_of_week_distribution: Dict[str, int]
    time_of_day_distribution: Dict[str, int]
    meeting_type_distribution: Dict[str, int]
    optimization_suggestions: List[str]