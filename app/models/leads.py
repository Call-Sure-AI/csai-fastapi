from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum

class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    CONVERTED = "converted"
    LOST = "lost"
    NURTURING = "nurturing"

class LeadSource(str, Enum):
    WEBSITE = "website"
    EMAIL = "email"
    SOCIAL_MEDIA = "social_media"
    REFERRAL = "referral"
    PAID_AD = "paid_ad"
    EVENT = "event"
    CSV_IMPORT = "csv_import"
    API = "api"
    CRM_SYNC = "crm_sync"

class LeadPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Lead(BaseModel):
    id: Optional[str] = None
    company_id: Optional[str] = None  # Reference to Company table
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    lead_company: Optional[str] = None  # The lead's company name (renamed from 'company')
    job_title: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    source: LeadSource = LeadSource.API
    status: LeadStatus = LeadStatus.NEW
    priority: LeadPriority = LeadPriority.MEDIUM
    score: int = Field(default=0, ge=0, le=100)
    tags: List[str] = []
    custom_fields: Dict[str, Any] = {}
    assigned_to: Optional[str] = None
    created_by: Optional[str] = None  # Added this field
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_contacted_at: Optional[datetime] = None
    converted_at: Optional[datetime] = None
    
class LeadImportRequest(BaseModel):
    source: Literal["csv", "excel", "crm", "api"]
    file_path: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    mapping: Optional[Dict[str, str]] = None
    options: Dict[str, Any] = Field(default_factory=dict)
    
class LeadImportResponse(BaseModel):
    imported: int
    failed: int
    duplicates: int
    errors: List[Dict[str, Any]] = []
    lead_ids: List[str] = []

class LeadEnrichmentRequest(BaseModel):
    lead_ids: List[str]
    fields: List[str] = ["company_info", "social_profiles", "tech_stack"]
    provider: Optional[str] = "clearbit"

class LeadScoreRequest(BaseModel):
    lead_id: Optional[str] = None
    lead_ids: Optional[List[str]] = None
    scoring_model: Optional[str] = "default"
    factors: Optional[Dict[str, float]] = None

class LeadScoreResponse(BaseModel):
    lead_id: str
    previous_score: int
    new_score: int
    factors: Dict[str, float]
    updated_at: datetime

class LeadSegment(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    criteria: Dict[str, Any]
    lead_count: Optional[int] = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class LeadDistributionRequest(BaseModel):
    lead_ids: List[str]
    distribution_method: Literal["round_robin", "load_balanced", "skill_based", "territory"]
    agent_ids: Optional[List[str]] = None
    rules: Optional[Dict[str, Any]] = None

class LeadDistributionResponse(BaseModel):
    distributed: int
    assignments: Dict[str, List[str]]  # agent_id -> lead_ids

class NurturingCampaign(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    trigger: Literal["immediate", "scheduled", "event_based"]
    schedule: Optional[Dict[str, Any]] = None
    steps: List[Dict[str, Any]]
    active: bool = True
    created_at: Optional[datetime] = None

class LeadNurturingRequest(BaseModel):
    lead_ids: List[str]
    campaign_id: str
    start_immediately: bool = True
    custom_params: Optional[Dict[str, Any]] = None

class LeadJourney(BaseModel):
    lead_id: str
    events: List[Dict[str, Any]]
    current_stage: str
    score_history: List[Dict[str, Any]]
    engagement_metrics: Dict[str, Any]
    touchpoints: List[Dict[str, Any]]

class LeadFilter(BaseModel):
    status: Optional[List[LeadStatus]] = None
    source: Optional[List[LeadSource]] = None
    priority: Optional[List[LeadPriority]] = None
    score_min: Optional[int] = None
    score_max: Optional[int] = None
    assigned_to: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    search_query: Optional[str] = None
    segment_id: Optional[str] = None
    page: int = 1
    page_size: int = 50
    sort_by: str = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"

class BulkLeadUpdate(BaseModel):
    lead_ids: List[str]
    updates: Dict[str, Any]
    
class LeadMergeRequest(BaseModel):
    primary_lead_id: str
    duplicate_lead_ids: List[str]
    merge_strategy: Literal["keep_primary", "most_recent", "custom"] = "keep_primary"
    field_preferences: Optional[Dict[str, str]] = None