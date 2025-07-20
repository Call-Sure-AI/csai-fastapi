from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from pydantic import BaseModel
from typing import Optional


Base = declarative_base()

class User(Base):
    __tablename__ = 'user'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    image = Column(Text)
    email_verified = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    owned_companies = relationship("Company", back_populates="owner")
    company_memberships = relationship("CompanyMembership", back_populates="user")

class Account(Base):
    __tablename__ = 'accounts'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userId = Column(UUID(as_uuid=True), ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    type = Column(String(50), nullable=False)  # 'oauth' or 'credentials'
    provider = Column(String(50), nullable=False)  # 'google', 'credentials'
    provider_account_id = Column(String(255), nullable=False)
    access_token = Column(Text)
    refresh_token = Column(Text)
    expires_at = Column(Integer)
    token_type = Column(String(50))
    scope = Column(Text)
    id_token = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    user = relationship("User", back_populates="accounts")
    
    __table_args__ = (
        {'schema': None}  
    )

class OTP(Base):
    __tablename__ = 'otps'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    used = Column(Boolean, default=False)
    
    __table_args__ = (
        {'schema': None}
    )

class Company(Base):
    __tablename__ = 'companies'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    owner_id = Column(UUID(as_uuid=True), ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    owner = relationship("User", back_populates="owned_companies")
    memberships = relationship("CompanyMembership", back_populates="company")

class CompanyMembership(Base):
    __tablename__ = 'company_memberships'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userId = Column(UUID(as_uuid=True), ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    role = Column(String(50), default='member')  # 'admin', 'member', 'viewer'
    joined_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    user = relationship("User", back_populates="company_memberships")
    company = relationship("Company", back_populates="memberships")

class UserResponse(BaseModel):
    id: str
    name: Optional[str]
    email: str
    image: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class SessionData(BaseModel):
    user_id: str
    session_token: str
    expires: datetime