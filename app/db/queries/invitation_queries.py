from typing import Dict, List, Optional, Tuple
from datetime import datetime

class InvitationQueries:
    """All SQL queries related to Invitation table"""
    
    GET_INVITATION_BY_TOKEN = """
        SELECT * FROM "Invitation" WHERE token = %s
    """
    
    GET_INVITATION_BY_EMAIL = """
        SELECT * FROM "Invitation" 
        WHERE email = %s AND "company_id" = %s
    """
    
    GET_INVITATIONS_BY_COMPANY = """
        SELECT * FROM "Invitation" 
        WHERE "company_id" = %s 
        ORDER BY "created_at" DESC
    """
    
    GET_PENDING_INVITATIONS = """
        SELECT * FROM "Invitation" 
        WHERE status = 'pending' AND "expires_at" > %s
    """
    
    GET_EXPIRED_INVITATIONS = """
        SELECT * FROM "Invitation" 
        WHERE "expires_at" < %s
    """
    
    CREATE_INVITATION = """
        INSERT INTO "Invitation" (id, email, "company_id", role, token, "expires_at") 
        VALUES (%s, %s, %s, %s, %s, %s) 
        RETURNING *
    """
    
    UPDATE_INVITATION_STATUS = """
        UPDATE "Invitation" 
        SET status = %s, "accepted_at" = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    ACCEPT_INVITATION = """
        UPDATE "Invitation" 
        SET status = 'accepted', "accepted_at" = CURRENT_TIMESTAMP, "updated_at" = CURRENT_TIMESTAMP 
        WHERE token = %s AND "expires_at" > %s
        RETURNING *
    """
    
    DELETE_INVITATION = """
        DELETE FROM "Invitation" WHERE id = %s
    """
    
    DELETE_INVITATIONS_BY_COMPANY = """
        DELETE FROM "Invitation" WHERE "company_id" = %s
    """
    
    DELETE_EXPIRED_INVITATIONS = """
        DELETE FROM "Invitation" WHERE "expires_at" < %s
    """
    
    CLEANUP_OLD_INVITATIONS = """
        DELETE FROM "Invitation" 
        WHERE status IN ('accepted', 'expired') OR "expires_at" < %s
    """

    @staticmethod
    def get_invitation_by_token_params(token: str) -> Tuple[str, tuple]:
        """Get invitation by token parameters"""
        return InvitationQueries.GET_INVITATION_BY_TOKEN, (token,)
    
    @staticmethod
    def create_invitation_params(invitation_id: str, email: str, company_id: str, role: str, token: str, expires_at: datetime) -> Tuple[str, tuple]:
        """Create invitation parameters"""
        return InvitationQueries.CREATE_INVITATION, (invitation_id, email, company_id, role, token, expires_at)
    
    @staticmethod
    def accept_invitation_params(token: str, current_time: datetime = None) -> Tuple[str, tuple]:
        """Accept invitation parameters"""
        if current_time is None:
            current_time = datetime.utcnow()
        return InvitationQueries.ACCEPT_INVITATION, (token, current_time)