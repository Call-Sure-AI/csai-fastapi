from typing import Dict, List, Optional, Tuple
from datetime import datetime

class OTPQueries:
    """All SQL queries related to OTP table"""
    
    GET_VALID_OTP = """
        SELECT * FROM "OTP" 
        WHERE email = %s AND code = %s AND "expiresAt" > %s
    """
    
    GET_OTP_BY_EMAIL = """
        SELECT * FROM "OTP" 
        WHERE email = %s
        ORDER BY "createdAt" DESC
    """
    
    GET_OTP_BY_ID = """
        SELECT * FROM "OTP" WHERE id = %s
    """
    
    GET_EXPIRED_OTPS = """
        SELECT * FROM "OTP" WHERE "expiresAt" < %s
    """
    
    CREATE_OTP = """
        INSERT INTO "OTP" (email, code, "expiresAt") 
        VALUES (%s, %s, %s)
        RETURNING *
    """
    
    CREATE_OTP_WITH_ID = """
        INSERT INTO "OTP" (id, email, code, "expiresAt") 
        VALUES (%s, %s, %s, %s)
        RETURNING *
    """
    
    DELETE_OTP_BY_ID = """
        DELETE FROM "OTP" WHERE id = %s
    """
    
    DELETE_OTPS_BY_EMAIL = """
        DELETE FROM "OTP" WHERE email = %s
    """
    
    DELETE_EXPIRED_OTPS = """
        DELETE FROM "OTP" WHERE "expiresAt" < %s
    """
    
    CLEANUP_OLD_OTPS = """
        DELETE FROM "OTP" 
        WHERE "createdAt" < %s
    """

    @staticmethod
    def get_valid_otp_params(email: str, code: str, current_time: datetime = None) -> Tuple[str, tuple]:
        """Get valid OTP parameters"""
        if current_time is None:
            current_time = datetime.utcnow()
        return OTPQueries.GET_VALID_OTP, (email, code, current_time)
    
    @staticmethod
    def create_otp_params(email: str, code: str, expires_at: datetime) -> Tuple[str, tuple]:
        """Create OTP parameters"""
        return OTPQueries.CREATE_OTP, (email, code, expires_at)
    
    @staticmethod
    def delete_otps_by_email_params(email: str) -> Tuple[str, tuple]:
        """Delete OTPs by email parameters"""
        return OTPQueries.DELETE_OTPS_BY_EMAIL, (email,)
    
    @staticmethod
    def get_otp_by_email_params(email: str) -> Tuple[str, tuple]:
        """Get OTP by email parameters"""
        return OTPQueries.GET_OTP_BY_EMAIL, (email,)
    
    @staticmethod
    def delete_otp_by_id_params(otp_id: str) -> Tuple[str, tuple]:
        """Delete OTP by ID parameters"""
        return OTPQueries.DELETE_OTP_BY_ID, (otp_id,)