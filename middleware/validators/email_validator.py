from pydantic import BaseModel, EmailStr, validator
from typing import List, Dict, Any, Optional
import re

class EmailValidationMixin:
    @validator('html')
    def validate_html_content(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('HTML content cannot be empty')
        if len(v) > 1000000:
            raise ValueError('HTML content too large (max 1MB)')
        return v
    
    @validator('subject')
    def validate_subject(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Subject cannot be empty')
        if len(v) > 255:
            raise ValueError('Subject too long (max 255 characters)')
        return v.strip()

class ValidatedEmailRequest(BaseModel, EmailValidationMixin):
    to: EmailStr
    subject: str
    html: str
    text: Optional[str] = None

class ValidatedBulkEmailRequest(BaseModel, EmailValidationMixin):
    recipients: List[EmailStr]
    subject: str
    html: str
    
    @validator('recipients')
    def validate_recipients(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Recipients list cannot be empty')
        if len(v) > 100:
            raise ValueError('Too many recipients (max 100)')
        return v

class ValidatedTemplateEmailRequest(BaseModel):
    to: EmailStr
    template_name: str
    template_data: Dict[str, Any]
    subject: Optional[str] = None
    
    @validator('template_name')
    def validate_template_name(cls, v):
        allowed_templates = ['otp', 'welcome', 'password_reset', 'verification']
        if v not in allowed_templates:
            raise ValueError(f'Invalid template name. Allowed: {allowed_templates}')
        return v
    
    @validator('subject')
    def validate_subject(cls, v):
        if v is not None and len(v) > 255:
            raise ValueError('Subject too long (max 255 characters)')
        return v
