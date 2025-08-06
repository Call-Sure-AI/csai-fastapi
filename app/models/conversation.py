from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Conversation(Base):
    __tablename__ = 'Conversation'
    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey('Company.id'), nullable=False)
    customer_id = Column(String, nullable=False)
    # Add other fields as relevant
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    history = Column(JSON, default=list)
    meta_data = Column(JSON, default=dict)