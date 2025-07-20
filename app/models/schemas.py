from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
import uuid

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