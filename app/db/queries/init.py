"""
Database Queries Module

This module contains all SQL queries organized by table/feature.
Each query class provides static methods and parameterized queries
for better code organization and reusability.
"""

from .user_queries import UserQueries
from .account_queries import AccountQueries
from .otp_queries import OTPQueries
from .company_queries import CompanyQueries
from .auth_queries import AuthQueries
from .agent_queries import AgentQueries
from .conversation_queries import ConversationQueries
from .document_queries import DocumentQueries
from .session_queries import SessionQueries
from .invitation_queries import InvitationQueries

__all__ = [
    'UserQueries',
    'AccountQueries', 
    'OTPQueries',
    'CompanyQueries',
    'AuthQueries',
    'AgentQueries',
    'ConversationQueries',
    'DocumentQueries',
    'SessionQueries',
    'InvitationQueries'
]