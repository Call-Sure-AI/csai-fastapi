import uuid
from pydantic import BaseModel, Field, EmailStr, HttpUrl, field_validator, validator
from typing import Optional, Dict, List, Any, Literal
from datetime import datetime, time, date
import re
from enum import Enum

class IntegrationType(str, Enum):
    WHATSAPP = "whatsapp"
    GOOGLE = "google" 
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TELEGRAM = "telegram"
    SLACK = "slack"
    DISCORD = "discord"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    API = "api"
    CUSTOM = "custom"


class IntegrationStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ERROR = "error"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class IntegrationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: IntegrationType = Field(..., description="Type of integration - used to segregate integrations")
    description: Optional[str] = Field(None, max_length=500)
    is_active: bool = Field(default=True)
    status: IntegrationStatus = Field(default=IntegrationStatus.ACTIVE)

    config: Dict[str, Any] = Field(default_factory=dict, description="All integration-specific configuration")

    webhook_url: Optional[HttpUrl] = None
    expires_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)

    last_error: Optional[str] = None
    error_count: int = Field(default=0, ge=0)


class IntegrationCreate(IntegrationBase):
    company_id: str = Field(..., description="Company this integration belongs to")


class IntegrationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    status: Optional[IntegrationStatus] = None
    config: Optional[Dict[str, Any]] = None
    webhook_url: Optional[HttpUrl] = None
    expires_at: Optional[datetime] = None
    tags: Optional[List[str]] = None


class Integration(IntegrationBase):
    id: str
    company_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class IntegrationResponse(BaseModel):
    id: str
    name: str
    type: IntegrationType
    description: Optional[str] = None
    is_active: bool
    status: IntegrationStatus
    webhook_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    tags: List[str]
    created_at: datetime
    updated_at: datetime


class IntegrationListResponse(BaseModel):
    integrations: List[IntegrationResponse]
    total: int
    page: int = 1
    per_page: int = 20

class GoogleAuthRequest(BaseModel):
    idToken: str

class EmailCheckRequest(BaseModel):
    email: EmailStr

class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str

class SignInRequest(BaseModel):
    email: EmailStr
    password: str

class GenerateOTPRequest(BaseModel):
    email: EmailStr

class SignInRequest(BaseModel):
    email: str
    password: Optional[str] = None
    code: Optional[str] = None
    
    @validator('password')
    def validate_auth_method(cls, password, values):
        code = values.get('code')
        if not password and not code:
            raise ValueError('Either password or OTP code must be provided')
        if password and code:
            raise ValueError('Provide either password or OTP code, not both')
        return password

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    image: Optional[str] = None
    role: str

class AuthResponse(BaseModel):
    token: str
    user: UserResponse
    newUser: bool = False
    companies: List[dict] = []

class EmailCheckResponse(BaseModel):
    exists: bool

class MessageResponse(BaseModel):
    message: str

class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None

# Internal Models
class User(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    image: Optional[str] = None
    email_verified: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class Account(BaseModel):
    id: uuid.UUID
    userId: uuid.UUID
    type: str
    provider: str
    provider_account_id: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[int] = None
    token_type: Optional[str] = None
    scope: Optional[str] = None
    id_token: Optional[str] = None
    created_at: datetime

class OTP(BaseModel):
    id: uuid.UUID
    email: str
    code: str
    expires_at: datetime
    created_at: datetime
    used: bool = False

class AgentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True
    company_id: str
    prompt: str
    additional_context: Optional[Dict[str, Any]] = None
    advanced_settings: Optional[Dict[str, Any]] = None
    confidence_threshold: float = Field(default=0.7, ge=0, le=1)
    files: List[str] = Field(default_factory=list)
    template_id: Optional[str] = Field(None, max_length=255)
    knowledge_base_ids: List[str] = Field(default_factory=list)
    database_integration_ids: List[str] = Field(default_factory=list)
    search_config: Optional[Dict[str, Any]] = None
    max_response_tokens: Optional[int] = None
    temperature: Optional[float] = None
    image_processing_enabled: Optional[bool] = None
    image_processing_config: Optional[Dict[str, Any]] = None

class AgentCreate(AgentBase):
    name: str
    type: str
    is_active: bool = True
    company_id: str
    prompt: str

class AgentUpdate(AgentBase):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    company_id: Optional[str] = None
    prompt: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None
    advanced_settings: Optional[Dict[str, Any]] = None
    confidence_threshold: Optional[float] = Field(None, ge=0, le=1)
    files: Optional[List[str]] = None
    template_id: Optional[str] = Field(None, max_length=255)
    knowledge_base_ids: Optional[List[str]] = None
    database_integration_ids: Optional[List[str]] = None
    search_config: Optional[Dict[str, Any]] = None
    max_response_tokens: Optional[int] = None
    temperature: Optional[float] = None
    image_processing_enabled: Optional[bool] = None
    image_processing_config: Optional[Dict[str, Any]] = None

class Agent(AgentBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
    
class NotificationPreferences(BaseModel):
    email: Optional[bool] = None
    sms: Optional[bool] = None

class WorkingHours(BaseModel):
    start: str
    end: str
    timezone: str

class CompanySettings(BaseModel):
    notification_preferences: Optional[NotificationPreferences] = None
    working_hours: Optional[WorkingHours] = None

class CompanyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    business_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    address: str = Field(..., min_length=1, max_length=255)
    website: Optional[HttpUrl] = Field(None, max_length=255)
    logo: Optional[str] = Field(None, max_length=255)
    prompt_templates: Optional[Dict[str, Any]] = None
    phone_number: Optional[str] = None
    settings: Optional[CompanySettings] = None

    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v):
        if v is not None:
            pattern = r'^\+?[1-9]\d{1,19}$'
            if not re.match(pattern, v):
                raise ValueError('Invalid phone number format')
        return v
    
    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Override model_dump to convert HttpUrl to string"""
        data = super().model_dump(**kwargs)
        
        # Convert HttpUrl fields to strings
        if 'website' in data and data['website']:
            data['website'] = str(data['website'])
        if 'logo' in data and data['logo']:
            data['logo'] = str(data['logo'])
            
        return data
    
    def to_db_dict(self) -> Dict[str, Any]:
        """This method is now redundant but kept for backward compatibility"""
        return self.model_dump()

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(CompanyBase):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    business_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(None, min_length=1, max_length=255)

class Company(CompanyBase):
    id: str
    user_id: str
    api_key: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class Activity(BaseModel):
    id: str
    user_id: str
    action: str
    entity_type: str
    entity_id: str
    metadata: Optional[Dict[str, Any]] = {}
    created_at: datetime
    user: Optional[Dict[str, str]] = None  # For user name and email
    
    class Config:
        from_attributes = True

class EmailRequest(BaseModel):
    to: EmailStr
    subject: str
    html: str
    text: Optional[str] = None

class EmailResponse(BaseModel):
    success: bool
    message: str

class BulkEmailRequest(BaseModel):
    recipients: List[EmailStr]
    subject: str
    html: str

class TemplateEmailRequest(BaseModel):
    to: EmailStr
    template_name: str
    template_data: Dict[str, Any]
    subject: Optional[str] = None

class VerifyOTPRequest(BaseModel):
    email: str
    code: str
    
class OTPEmailRequest(BaseModel):
    email: EmailStr
    code: str

class WelcomeEmailRequest(BaseModel):
    to: EmailStr
    name: str

class PasswordResetEmailRequest(BaseModel):
    to: EmailStr
    reset_link: str

class VerificationEmailRequest(BaseModel):
    to: EmailStr
    verification_link: str

class InvitationRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"  # Changed from VIEWER
    MEMBER = "member"

class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"  # Optional, if you use it

class InvitationCreate(BaseModel):
    email: EmailStr
    company_id: str = Field(..., description="Company ID", validation_alias="companyId")
    role: Optional[InvitationRole] = Field(InvitationRole.MEMBER, description="User role")
    
    class Config:
        populate_by_name = True  # Accept both company_id and companyId

class InvitationAccept(BaseModel):
    name: Optional[str] = Field(None, description="User name (required for new users)")
    password: Optional[str] = Field(None, description="Password (required for new users)")

class Invitation(BaseModel):
    id: str
    email: EmailStr
    company_id: str
    role: InvitationRole
    token: str
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    accepted_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class InvitationResponse(BaseModel):
    message: str
    invitation_url: str
    invitation: dict

class InvitationValidation(BaseModel):
    invitation: dict

class SendInvitationEmailRequest(BaseModel):
    invitation_id: str = Field(..., validation_alias="invitationId")
    
    class Config:
        populate_by_name = True

class DeleteInvitationRequest(BaseModel):
    invitation_id: str = Field(..., validation_alias="invitationId")
    
    class Config:
        populate_by_name = True

class S3FileUploadResponse(BaseModel):
    success: bool
    key: Optional[str] = None
    url: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class S3FileDetails(BaseModel):
    success: bool
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class S3FileDownload(BaseModel):
    success: bool
    data: Optional[bytes] = None
    content_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    size: Optional[int] = None
    error: Optional[str] = None

class S3FileDelete(BaseModel):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

class S3FileList(BaseModel):
    success: bool
    files: Optional[List[Dict[str, Any]]] = None
    count: Optional[int] = None
    is_truncated: Optional[bool] = None
    next_continuation_token: Optional[str] = None
    error: Optional[str] = None

class S3FileCopy(BaseModel):
    success: bool
    source: Optional[str] = None
    destination: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class S3FileExists(BaseModel):
    success: bool
    exists: Optional[bool] = None
    error: Optional[str] = None

class S3PresignedURL(BaseModel):
    success: bool
    url: Optional[str] = None
    expires_in: Optional[int] = None
    error: Optional[str] = None

class S3BulkOperationResult(BaseModel):
    total_files: int
    successful_operations: int
    failed_operations: int
    results: List[Dict[str, Any]]

# ========================
# WhatsApp Schemas - Updated with proper Pydantic v2 validators
# ========================

class WhatsAppOnboardRequest(BaseModel):
    business_id: str
    status: Literal["FINISH", "CANCEL"]
    waba_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    code: Optional[str] = None
    current_step: Optional[str] = None

    @field_validator('business_id')
    @classmethod
    def validate_business_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Business ID cannot be empty')
        return v.strip()

class WhatsAppMessageRequest(BaseModel):
    """Base message request schema"""
    to: str             # Recipient phone number
    message: str        # Text message content
    type: str = "text"  # Message type (text, template, media, etc.)
    business_id: Optional[str] = None  # Business ID for routing

    @field_validator('to')
    @classmethod  # <- ADD @classmethod decorator
    def validate_phone_number(cls, v: str) -> str:  # <- Use 'cls' not 'self'
        # Remove any whitespace
        v = v.strip()
        
        # Basic phone number validation
        # Should start with + and contain 10-15 digits
        if not re.match(r'^\+\d{10,15}$', v):
            # Try to fix common formats
            if v.startswith('00'):
                v = '+' + v[2:]
            elif not v.startswith('+') and v.isdigit():
                # Assume it needs a + prefix
                v = '+' + v
            else:
                raise ValueError('Phone number must be in format +1234567890 (10-15 digits)')
        
        return v

    @field_validator('message')
    @classmethod  # <- ADD @classmethod decorator
    def validate_message(cls, v: str) -> str:  # <- Use 'cls' not 'self'
        if not v or not v.strip():
            raise ValueError('Message content cannot be empty')
        
        # WhatsApp message length limit
        if len(v) > 4096:
            raise ValueError('Message too long (max 4096 characters)')
        
        return v.strip()

class SendMessageRequest(WhatsAppMessageRequest):
    """Extended message request for API endpoints"""
    business_id: str  # Make business_id required for API calls
    
    # Additional optional fields for advanced messaging
    preview_url: Optional[bool] = True  # Enable URL previews
    context: Optional[Dict[str, str]] = None  # For replying to messages

class SendMessageResponse(BaseModel):
    """Response after sending a WhatsApp message"""
    message_id: str      # Unique message ID returned by WhatsApp API
    status: str          # e.g., "sent", "failed", "queued", "rate_limited", "unauthorized"
    to: str              # Recipient phone number
    error_message: Optional[str] = None  # Error details if status is failed

    class Config:
        from_attributes = True  # Updated for Pydantic v2

class WhatsAppTemplateMessage(BaseModel):
    """Schema for WhatsApp template messages"""
    to: str
    business_id: str
    template_name: str
    language_code: str = "en"  # Default to English
    components: Optional[List[Dict[str, Any]]] = None  # Template parameters

    @field_validator('to')
    @classmethod  # <- ADD @classmethod decorator
    def validate_phone_number(cls, v: str) -> str:  # <- Use 'cls' not 'self'
        v = v.strip()
        if not re.match(r'^\+\d{10,15}$', v):
            if v.startswith('00'):
                v = '+' + v[2:]
            elif not v.startswith('+') and v.isdigit():
                v = '+' + v
            else:
                raise ValueError('Phone number must be in format +1234567890')
        return v

class WhatsAppMediaMessage(BaseModel):
    """Schema for WhatsApp media messages (images, documents, etc.)"""
    to: str
    business_id: str
    media_type: Literal["image", "document", "audio", "video"]
    media_url: Optional[str] = None  # URL to media file
    media_id: Optional[str] = None   # WhatsApp media ID (if uploaded to WhatsApp)
    caption: Optional[str] = None    # Caption for media
    filename: Optional[str] = None   # For documents

    @field_validator('to')
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r'^\+\d{10,15}$', v):
            if v.startswith('00'):
                v = '+' + v[2:]
            elif not v.startswith('+') and v.isdigit():
                v = '+' + v
            else:
                raise ValueError('Phone number must be in format +1234567890')
        return v

    def model_post_init(self, __context: Any) -> None:
        """Custom validation that requires access to multiple fields"""
        # Fixed: Added the required __context parameter
        if not self.media_url and not self.media_id:
            raise ValueError('Either media_url or media_id must be provided')

class BulkMessageRequest(BaseModel):
    """Schema for sending bulk WhatsApp messages"""
    business_id: str
    recipients: List[str]  # List of phone numbers
    message: str
    type: str = "text"
    
    @field_validator('recipients')
    @classmethod  # <- ADD @classmethod decorator
    def validate_recipients(cls, v: List[str]) -> List[str]:  # <- Use 'cls' not 'self'
        if len(v) > 100:  # Limit bulk messages
            raise ValueError('Maximum 100 recipients allowed per bulk message')
        
        validated_numbers = []
        for phone in v:
            phone = phone.strip()
            if not re.match(r'^\+\d{10,15}$', phone):
                if phone.startswith('00'):
                    phone = '+' + phone[2:]
                elif not phone.startswith('+') and phone.isdigit():
                    phone = '+' + phone
                else:
                    raise ValueError(f'Invalid phone number format: {phone}')
            validated_numbers.append(phone)
        
        return validated_numbers

class BulkMessageResponse(BaseModel):
    """Response for bulk message sending"""
    total_messages: int
    successful: int
    failed: int
    results: List[SendMessageResponse]

class WhatsAppWebhookMessage(BaseModel):
    """Schema for incoming WhatsApp webhook messages"""
    id: str
    from_: str = Field(alias="from")  # 'from' is a Python keyword
    timestamp: str
    type: str
    text: Optional[Dict[str, str]] = None
    image: Optional[Dict[str, Any]] = None
    document: Optional[Dict[str, Any]] = None
    audio: Optional[Dict[str, Any]] = None
    video: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, str]] = None  # For message replies

class WhatsAppWebhookStatus(BaseModel):
    """Schema for WhatsApp message status updates"""
    id: str  # Message ID
    status: str  # sent, delivered, read, failed
    timestamp: str
    recipient_id: str
    conversation: Optional[Dict[str, Any]] = None
    pricing: Optional[Dict[str, Any]] = None

class WhatsAppWebhookEntry(BaseModel):
    """Schema for WhatsApp webhook entry"""
    id: str  # WhatsApp Business Account ID
    changes: List[Dict[str, Any]]

class WhatsAppWebhookPayload(BaseModel):
    """Schema for complete WhatsApp webhook payload"""
    object: str  # Should be "whatsapp_business_account"
    entry: List[WhatsAppWebhookEntry]

class WhatsAppStatusResponse(BaseModel):
    """Schema for WhatsApp business status response"""
    business_id: str
    status: str  # FINISH, CANCEL, PENDING, etc.
    current_step: Optional[str] = None
    waba_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    has_token: bool = False
    created_at: datetime
    updated_at: datetime

class WhatsAppBusinessInfo(BaseModel):
    """Schema for WhatsApp Business Account information"""
    id: str
    name: str
    currency: Optional[str] = None
    timezone_id: Optional[str] = None
    message_template_namespace: Optional[str] = None

class WhatsAppPhoneNumberInfo(BaseModel):
    """Schema for WhatsApp Phone Number information"""
    id: str
    display_phone_number: str
    verified_name: str
    code_verification_status: str
    quality_rating: Optional[str] = None

# Webhook verification
class WhatsAppWebhookVerification(BaseModel):
    """Schema for webhook verification"""
    hub_mode: str = Field(alias="hub.mode")
    hub_verify_token: str = Field(alias="hub.verify_token") 
    hub_challenge: str = Field(alias="hub.challenge")

    class Config:
        populate_by_name = True

class LeadCreate(BaseModel):
    first_name: str = Field(..., max_length=255)
    last_name: Optional[str] = Field(None, max_length=255)
    email: str = Field(..., max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    company: Optional[str] = Field(None, max_length=255)
    custom_fields: Optional[Dict[str, Any]] = {}

class LeadUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=255)
    last_name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    company: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=50)
    custom_fields: Optional[Dict[str, Any]] = None

class Lead(BaseModel):
    id: str
    campaign_id: str
    first_name: str
    last_name: Optional[str]
    email: str
    phone: Optional[str]
    company: Optional[str]
    custom_fields: Dict[str, Any] = {}
    call_attempts: int = 0
    last_call_at: Optional[datetime]
    status: str = "pending"
    created_at: datetime
    updated_at: datetime

class LeadsBulkUpdate(BaseModel):
    lead_ids: List[str]
    updates: LeadUpdate

class CSVParseResponse(BaseModel):
    headers: List[str]
    preview_rows: List[List[str]]
    total_rows: int
    detected_delimiter: str

class CSVValidateRequest(BaseModel):
    csv_content: str
    expected_headers: Optional[List[str]] = None
    required_fields: Optional[List[str]] = None

class CSVValidationError(BaseModel):
    row: int
    column: str
    error: str
    value: str

class CSVValidateResponse(BaseModel):
    is_valid: bool
    errors: List[CSVValidationError]
    summary: Dict[str, Any]

class FieldMapping(BaseModel):
    csv_column: str
    system_field: str
    required: bool = False
    transform: Optional[str] = None

class CSVMapFieldsRequest(BaseModel):
    csv_headers: List[str]
    mappings: List[FieldMapping]
    
class CSVMapFieldsResponse(BaseModel):
    mapped_fields: Dict[str, str]
    unmapped_columns: List[str]
    missing_required: List[str]
    preview_mapping: Dict[str, Any]

class BookingSettings(BaseModel):
    calendar_type: str = Field(..., description="google, outlook, calendly")
    meeting_duration_minutes: int = Field(30, ge=15, le=180)
    buffer_time_minutes: int = Field(15, ge=0, le=60)
    send_invite_to_lead: bool = True
    send_invite_to_team: bool = True
    team_email_addresses: List[str] = []
    booking_window_days: int = Field(30, ge=1, le=90)
    min_notice_hours: int = Field(2, ge=1, le=48)
    max_bookings_per_day: Optional[int] = Field(None, ge=1, le=50)

class EmailSettings(BaseModel):
    template: str = Field(..., min_length=10)
    subject_line: str = Field(..., min_length=5, max_length=100)
    from_name: str = Field(..., min_length=2, max_length=50)
    from_email: str = Field(..., patttern=r'^[^@]+@[^@]+\.[^@]+$')
    enable_followup: bool = True
    followup_delay_hours: int = Field(24, ge=1, le=168)
    max_followup_attempts: int = Field(3, ge=1, le=10)
    unsubscribe_link: bool = True
    track_opens: bool = True
    track_clicks: bool = True

class CallSettings(BaseModel):
    script: str = Field(..., min_length=20)
    max_call_attempts: int = Field(3, ge=1, le=10)
    call_interval_hours: int = Field(24, ge=1, le=168)
    preferred_calling_hours: Dict[str, Any] = Field(default={
        "start": "09:00",
        "end": "17:00",
        "timezone": "UTC"
    })
    voicemail_script: Optional[str] = None
    call_recording_enabled: bool = True
    auto_dial_enabled: bool = False
    caller_id: Optional[str] = None

class ScheduleSettings(BaseModel):
    working_days: List[str] = Field(default=["monday", "tuesday", "wednesday", "thursday", "friday"])
    working_hours_start: time = Field(default=time(9, 0))
    working_hours_end: time = Field(default=time(17, 0))
    timezone: str = Field(default="UTC")
    lunch_break_start: Optional[time] = Field(default=time(12, 0))
    lunch_break_end: Optional[time] = Field(default=time(13, 0))
    max_concurrent_calls: int = Field(5, ge=1, le=20)
    campaign_active_days: List[str] = Field(default=["monday", "tuesday", "wednesday", "thursday", "friday"])
    pause_on_holidays: bool = True

class CampaignSettings(BaseModel):
    booking: BookingSettings
    email: EmailSettings
    call: CallSettings
    schedule: ScheduleSettings
    
class BookingSettingsUpdate(BaseModel):
    calendar_type: Optional[str] = None
    meeting_duration_minutes: Optional[int] = Field(None, ge=15, le=180)
    buffer_time_minutes: Optional[int] = Field(None, ge=0, le=60)
    send_invite_to_lead: Optional[bool] = None
    send_invite_to_team: Optional[bool] = None
    team_email_addresses: Optional[List[str]] = None
    booking_window_days: Optional[int] = Field(None, ge=1, le=90)
    min_notice_hours: Optional[int] = Field(None, ge=1, le=48)
    max_bookings_per_day: Optional[int] = Field(None, ge=1, le=50)

class EmailSettingsUpdate(BaseModel):
    template: Optional[str] = Field(None, min_length=10)
    subject_line: Optional[str] = Field(None, min_length=5, max_length=100)
    from_name: Optional[str] = Field(None, min_length=2, max_length=50)
    from_email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    enable_followup: Optional[bool] = None
    followup_delay_hours: Optional[int] = Field(None, ge=1, le=168)
    max_followup_attempts: Optional[int] = Field(None, ge=1, le=10)
    unsubscribe_link: Optional[bool] = None
    track_opens: Optional[bool] = None
    track_clicks: Optional[bool] = None

class CallSettingsUpdate(BaseModel):
    script: Optional[str] = Field(None, min_length=20)
    max_call_attempts: Optional[int] = Field(None, ge=1, le=10)
    call_interval_hours: Optional[int] = Field(None, ge=1, le=168)
    preferred_calling_hours: Optional[Dict[str, Any]] = None
    voicemail_script: Optional[str] = None
    call_recording_enabled: Optional[bool] = None
    auto_dial_enabled: Optional[bool] = None
    caller_id: Optional[str] = None

class ScheduleSettingsUpdate(BaseModel):
    working_days: Optional[List[str]] = None
    working_hours_start: Optional[time] = None
    working_hours_end: Optional[time] = None
    timezone: Optional[str] = None
    lunch_break_start: Optional[time] = None
    lunch_break_end: Optional[time] = None
    max_concurrent_calls: Optional[int] = Field(None, ge=1, le=20)
    campaign_active_days: Optional[List[str]] = None
    pause_on_holidays: Optional[bool] = None

class CalendarConnectRequest(BaseModel):
    calendar_type: str = Field(..., description="google, outlook, calendly")
    credentials: Dict[str, Any] = Field(..., description="OAuth tokens or API keys")
    calendar_name: Optional[str] = Field(None, max_length=255)
    is_primary: bool = Field(default=True)

class CalendarConnectResponse(BaseModel):
    calendar_id: str
    calendar_type: str
    calendar_name: str
    is_connected: bool
    message: str

class TimeSlot(BaseModel):
    start: str = Field(..., description="ISO 8601 datetime string")
    end: str = Field(..., description="ISO 8601 datetime string")
    available: bool = True

class CalendarAvailabilityResponse(BaseModel):
    calendar_id: str
    date_range: Dict[str, str]
    total_slots: int
    available_slots: List[TimeSlot]

class CalendarTestRequest(BaseModel):
    calendar_id: str

class CalendarTestResponse(BaseModel):
    calendar_id: str
    success: bool
    message: str
    last_tested: str
    connection_details: Optional[Dict[str, Any]] = None

class CalendarIntegration(BaseModel):
    id: str
    company_id: str
    user_id: str
    calendar_type: str
    calendar_id: str
    calendar_name: str
    credentials: Dict[str, Any]
    is_active: bool
    is_primary: bool
    last_sync: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class CampaignLiveStatus(BaseModel):
    campaign_id: str
    status: str = Field(..., description="active, paused, completed,```ror")
    current_phase: str = Field(default="idle", description="calling```mailing, analyzing")
    active_agents: int = Field(default=0, ge=0)
    queue_size: int = Field(default=0, ge=0)
    last_activity: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class CampaignMetrics(BaseModel):
    campaign_id: str
    calls_made: int = Field(default=0, ge=0)
    calls_answered: int = Field(default=0, ge=0)
    calls_successful: int = Field(default=0, ge=0)
    emails_sent: int = Field(default=0, ge=0)
    emails_opened: int = Field(default=0, ge=0)
    bookings_scheduled: int = Field(default=0, ge=0)
    leads_contacted: int = Field(default=0, ge=0)
    conversion_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class WebSocketMessage(BaseModel):
    type: str = Field(..., description="status, metrics, error```eartbeat")
    data: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class BookingBase(BaseModel):
    campaign_id: str = Field(..., description="Campaign ID this booking belongs to")
    customer: str = Field(..., min_length=1, max_length=255)
    slot_start: datetime = Field(..., description="Booking start time")
    slot_end: datetime = Field(..., description="Booking end time")
    status: str = Field(default="pending", description="pending, confirmed, cancelled, rescheduled, completed")
    customer_email: Optional[str] = Field(None, max_length=255)
    customer_phone: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=1000)

class BookingCreate(BookingBase):
    pass

class BookingUpdate(BaseModel):
    campaign_id: Optional[str] = None
    customer: Optional[str] = Field(None, min_length=1, max_length=255)
    slot_start: Optional[datetime] = None
    slot_end: Optional[datetime] = None
    status: Optional[str] = None
    customer_email: Optional[str] = Field(None, max_length=255)
    customer_phone: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=1000)

class BookingResponse(BookingBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class BookingStatusUpdate(BaseModel):
    status: str = Field(..., description="New status for the booking")

class BookingBulkUpdate(BaseModel):
    booking_ids: List[str] = Field(..., min_items=1)
    updates: BookingUpdate

class BookingFilter(BaseModel):
    campaign_id: Optional[str] = None
    customer: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class BookingAnalytics(BaseModel):
    total_bookings: int = Field(ge=0)
    completed: int = Field(ge=0)
    cancelled: int = Field(ge=0) 
    pending: int = Field(ge=0)
    rescheduled: int = Field(ge=0)
    completion_rate: float = Field(ge=0.0, le=1.0)
    cancellation_rate: float = Field(ge=0.0, le=1.0)
    average_booking_duration: int = Field(description="Average duration in minutes")
    revenue_generated: float = Field(ge=0.0)
    period_start: date
    period_end: date

class AIPerformanceMetrics(BaseModel):
    call_success_rate: float = Field(ge=0.0, le=1.0, description="Percentage of successful calls")
    average_handle_time: int = Field(ge=0, description="Average call duration in seconds")
    auto_dialer_efficiency: float = Field(ge=0.0, le=1.0)
    voice_quality_score: float = Field(ge=0.0, le=10.0)
    response_accuracy: float = Field(ge=0.0, le=1.0)
    total_calls_handled: int = Field(ge=0)
    ai_uptime: float = Field(ge=0.0, le=1.0, description="AI system uptime percentage")
    cost_per_call: float = Field(ge=0.0)

class CallInsights(BaseModel):
    peak_hours: List[str] = Field(description="Best performing hours")
    avg_calls_per_hour: float = Field(ge=0.0)
    best_days: List[str] = Field(description="Most successful days of week")
    call_patterns: Dict[str, int] = Field(description="Call volume by time periods")
    answer_rates: Dict[str, float] = Field(description="Answer rates by time/```")
    conversion_by_hour: Dict[str, float]
    total_call_volume: int = Field(ge=0)
    
class ConversionFunnel(BaseModel):
    leads_imported: int = Field(ge=0)
    leads_contacted: int = Field(ge=0) 
    leads_answered: int = Field(ge=0)
    bookings_scheduled: int = Field(ge=0)
    bookings_completed: int = Field(ge=0)
    final_conversions: int = Field(ge=0)
    contact_rate: float = Field(ge=0.0, le=1.0)
    answer_rate: float = Field(ge=0.0, le=1.0)
    booking_rate: float = Field(ge=0.0, le=1.0)
    completion_rate: float = Field(ge=0.0, le=1.0)
    overall_conversion_rate: float = Field(ge=0.0, le=1.0)

class OptimalTimes(BaseModel):
    best_call_times: List[Dict[str, Any]] = Field(description="Optimal time periods for calls")
    worst_call_times: List[Dict[str, Any]] = Field(description="Poor performing time periods")
    day_performance: Dict[str, float] = Field(description="Success rate by day of week")
    hour_performance: Dict[str, float] = Field(description="Success rate by hour")
    recommendations: List[str] = Field(description="AI-generated recommendations")
    timezone: str = Field(default="UTC")