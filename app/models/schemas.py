import uuid
from pydantic import BaseModel, Field, EmailStr, HttpUrl, validator
from typing import Optional, Dict, List, Any, Literal
from datetime import datetime
import re
from enum import Enum

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

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    code: str

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
    user_id: str

class AgentUpdate(AgentBase):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    company_id: Optional[str] = None
    prompt: Optional[str] = None

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
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        if v is not None:
            pattern = r'^\+?[1-9]\d{1,19}$'
            if not re.match(pattern, v):
                raise ValueError('Invalid phone number format')
        return v

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
    MEMBER = "member"
    VIEWER = "viewer"

class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"

class InvitationCreate(BaseModel):
    email: EmailStr
    company_id: str = Field(..., description="Company ID")
    role: Optional[InvitationRole] = Field(InvitationRole.MEMBER, description="User role")

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

class WhatsAppOnboardRequest(BaseModel):
    business_id: str
    status: Literal["FINISH", "CANCEL"]
    waba_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    code: Optional[str] = None
    current_step: Optional[str] = None

class WhatsAppMessageRequest(BaseModel):
    to: str             # Recipient phone number
    message: str        # Text message
    type: str = "text"  # Optional, default to text; could extend to templates, media

class SendMessageRequest(BaseModel):
    to: str         # recipient phone number
    message: str    # message text
    type: str = "text"

class SendMessageResponse(BaseModel):
    message_id: str
    status: str
    to: str

class SendMessageResponse(BaseModel):
    message_id: str      # Unique message ID returned by WhatsApp API
    status: str          # e.g., "sent", "failed", "queued"
    to: str              # Recipient phone number

    class Config:
        orm_mode = True  # Allows ORM objects (SQLAlchemy) to be serialized
