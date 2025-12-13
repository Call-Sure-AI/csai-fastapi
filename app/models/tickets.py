# app\models\tickets.py
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import declarative_base, relationship
import enum
from datetime import datetime
import uuid
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

Base = declarative_base()

class TicketStatus(str, enum.Enum):
    NEW = "new"
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TicketSource(str, enum.Enum):
    EMAIL = "email"
    PHONE = "phone"
    CHAT = "chat"
    WEB_FORM = "web_form"
    AUTO_GENERATED = "auto_generated"

class Ticket(Base):
    __tablename__ = 'Ticket'
    id = Column(String, primary_key=True, default=lambda: f"TKT-{str(uuid.uuid4())[:8].upper()}")
    company_id = Column(String, ForeignKey('Company.id'), nullable=False)
    conversation_id = Column(String, ForeignKey('Conversation.id'), nullable=True)
    customer_id = Column(String, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(SQLEnum(TicketStatus), default=TicketStatus.NEW, nullable=False)
    priority = Column(SQLEnum(TicketPriority), default=TicketPriority.MEDIUM, nullable=False)
    source = Column(SQLEnum(TicketSource), default=TicketSource.AUTO_GENERATED, nullable=False)
    assigned_to = Column(String, nullable=True)
    customer_name = Column(String(255), nullable=True)
    customer_email = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    tags = Column(ARRAY(String), default=[])
    meta_data = Column(JSONB, default={})
    auto_resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    notes = relationship("TicketNote", back_populates="ticket", cascade="all, delete-orphan")

class TicketNote(Base):
    __tablename__ = 'TicketNote'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id = Column(String, ForeignKey('Ticket.id'), nullable=False)
    content = Column(Text, nullable=False)
    author = Column(String(255), nullable=False)
    is_internal = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    ticket = relationship("Ticket", back_populates="notes")

class ConversationAnalysisResult(BaseModel):
    should_create_ticket: bool
    confidence_score: float
    detected_issues: List[str]
    priority: TicketPriority
    suggested_title: str
    suggested_description: str
    reason: Optional[str] = None
