from typing import Dict, List, Optional, Tuple
from datetime import datetime

class SessionQueries:
    """All SQL queries related to Session table"""
    
    GET_SESSION_BY_TOKEN = """
        SELECT * FROM "Session" WHERE "sessionToken" = $1
    """
    
    GET_SESSIONS_BY_USER = """
        SELECT * FROM "Session" 
        WHERE "userId" = $1 
        ORDER BY "createdAt" DESC
    """
    
    GET_VALID_SESSIONS = """
        SELECT * FROM "Session" 
        WHERE "userId" = $1 AND expires > $2
        ORDER BY "createdAt" DESC
    """
    
    CREATE_SESSION = """
        INSERT INTO "Session" ("sessionToken", "userId", expires) 
        VALUES ($1, $2, $3) 
        RETURNING *
    """
    
    UPDATE_SESSION_EXPIRY = """
        UPDATE "Session" 
        SET expires = $1, "updatedAt" = CURRENT_TIMESTAMP 
        WHERE "sessionToken" = $2
        RETURNING *
    """
    
    DELETE_SESSION = """
        DELETE FROM "Session" WHERE "sessionToken" = $1
    """
    
    DELETE_SESSIONS_BY_USER = """
        DELETE FROM "Session" WHERE "userId" = $1
    """
    
    DELETE_EXPIRED_SESSIONS = """
        DELETE FROM "Session" WHERE expires < $1
    """
    
    CLEANUP_EXPIRED_SESSIONS = """
        DELETE FROM "Session" WHERE expires < CURRENT_TIMESTAMP
    """

    @staticmethod
    def get_session_by_token_params(session_token: str) -> Tuple[str, tuple]:
        """Get session by token parameters"""
        return SessionQueries.GET_SESSION_BY_TOKEN, (session_token,)
    
    @staticmethod
    def create_session_params(session_token: str, user_id: str, expires: datetime) -> Tuple[str, tuple]:
        """Create session parameters"""
        return SessionQueries.CREATE_SESSION, (session_token, user_id, expires)
    
    @staticmethod
    def delete_session_params(session_token: str) -> Tuple[str, tuple]:
        """Delete session parameters"""
        return SessionQueries.DELETE_SESSION, (session_token,)