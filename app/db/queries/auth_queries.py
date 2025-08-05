from typing import Dict, List, Optional, Tuple
from datetime import datetime
from .user_queries import UserQueries
from .account_queries import AccountQueries
from .otp_queries import OTPQueries
from .company_queries import CompanyQueries

class AuthQueries:
    """Combined authentication-related queries and transactions"""
    
    @staticmethod
    def create_user_with_google_account_transaction(
        userId: str, 
        email: str, 
        name: str, 
        image: str, 
        email_verified: datetime,
        google_id: str,
        access_token: str
    ) -> List[Tuple[str, tuple]]:
        """Transaction to create user with Google account"""
        return [
            UserQueries.create_user_params(userId, email, name, image, email_verified),
            AccountQueries.create_google_account_params(userId, google_id, access_token)
        ]
    
    @staticmethod
    def create_user_with_credentials_transaction(
        userId: str,
        email: str,
        name: str,
        hashed_password: str
    ) -> List[Tuple[str, tuple]]:
        """Transaction to create user with credentials account"""
        return [
            UserQueries.create_user_basic_params(userId, email, name),
            AccountQueries.create_credentials_account_params(userId, email, hashed_password)
        ]
    
    @staticmethod
    def create_user_with_otp_verification_transaction(
        userId: str,
        email: str,
        name: str,
        jwt_token: str
    ) -> List[Tuple[str, tuple]]:
        """Transaction to create user through OTP verification"""
        return [
            UserQueries.create_user_basic_params(userId, email, name),
            AccountQueries.create_credentials_account_params(userId, email, jwt_token)
        ]
    
    @staticmethod
    def generate_otp_transaction(email: str, code: str, expires_at: datetime) -> List[Tuple[str, tuple]]:
        """Transaction to generate new OTP (delete old ones and create new)"""
        return [
            OTPQueries.delete_otps_by_email_params(email),
            OTPQueries.create_otp_params(email, code, expires_at)
        ]
    
    @staticmethod
    def get_user_role_queries(userId: str) -> Dict[str, Tuple[str, tuple]]:
        return {
            'companies': CompanyQueries.count_companies_by_owner_params(userId),
            'membership': CompanyQueries.get_user_first_membership_params(userId)
        }

    GET_USER_WITH_ACCOUNTS = """
        SELECT 
            u.*,
            COALESCE(
                JSON_AGG(
                    JSON_BUILD_OBJECT(
                        'userId', a."userId",
                        'type', a.type,
                        'provider', a.provider,
                        'providerAccountId', a."providerAccountId",
                        'createdAt', a."createdAt"
                    )
                ) FILTER (WHERE a."userId" IS NOT NULL), 
                '[]'
            ) as accounts
        FROM "User" u
        LEFT JOIN "Account" a ON u.id = a."userId"
        WHERE u.id = $1
        GROUP BY u.id
    """

    GET_USER_COMPLETE_PROFILE = """
        SELECT 
            u.*,
            COALESCE(
                JSON_AGG(
                    JSON_BUILD_OBJECT(
                        'id', c.id,
                        'name', c.name,
                        'business_name', c."business_name",
                        'email', c.email,
                        'created_at', c."created_at"
                    )
                ) FILTER (WHERE c.id IS NOT NULL), 
                '[]'
            ) as owned_companies,
            COALESCE(
                JSON_AGG(
                    DISTINCT JSON_BUILD_OBJECT(
                        'company_id', cm."company_id",
                        'role', cm.role,
                        'company_name', comp.name,
                        'created_at', cm."created_at"
                    )
                ) FILTER (WHERE cm.id IS NOT NULL), 
                '[]'
            ) as memberships
        FROM "User" u
        LEFT JOIN "Company" c ON u.id = c."user_id"
        LEFT JOIN "CompanyMember" cm ON u.id = cm."user_id"
        LEFT JOIN "Company" comp ON cm."company_id" = comp.id
        WHERE u.id = $1
        GROUP BY u.id
    """


    @staticmethod
    def get_user_with_accounts_params(userId: str) -> Tuple[str, tuple]:
        """Get user with all accounts"""
        return AuthQueries.GET_USER_WITH_ACCOUNTS, (userId,)
    
    @staticmethod
    def get_user_complete_profile_params(userId: str) -> Tuple[str, tuple]:
        """Get user complete profile with companies and memberships"""
        return AuthQueries.GET_USER_COMPLETE_PROFILE, (userId,)