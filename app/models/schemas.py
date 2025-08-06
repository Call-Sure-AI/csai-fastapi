import uuid
from pydantic import BaseModel, Field, EmailStr, HttpUrl, field_validator, validator
from typing import Optional, Dict, List, Any, Literal
from datetime import datetime
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
        allow_population_by_field_name = True
