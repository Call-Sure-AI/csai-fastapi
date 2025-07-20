from typing import Dict, List, Optional, Tuple

class AccountQueries:
    """All SQL queries related to Account table"""
    
    GET_ACCOUNTS_BY_USER_ID = """
        SELECT * FROM "Account" WHERE "userId" = %s
    """
    
    GET_ACCOUNT_BY_PROVIDER = """
        SELECT * FROM "Account" 
        WHERE "userId" = %s AND provider = %s
    """
    
    GET_GOOGLE_ACCOUNT = """
        SELECT * FROM "Account" 
        WHERE "userId" = %s AND provider = 'google'
    """
    
    GET_CREDENTIALS_ACCOUNT = """
        SELECT * FROM "Account" 
        WHERE "userId" = %s AND provider = 'credentials'
    """
    
    GET_ACCOUNT_BY_PROVIDER_ID = """
        SELECT * FROM "Account" 
        WHERE provider = %s AND "providerAccountId" = %s
    """
    
    CREATE_OAUTH_ACCOUNT = """
        INSERT INTO "Account" ("userId", type, provider, "providerAccountId", "access_token") 
        VALUES (%s, %s, %s, %s, %s) 
        RETURNING *
    """
    
    CREATE_CREDENTIALS_ACCOUNT = """
        INSERT INTO "Account" ("userId", type, provider, "providerAccountId", "access_token")
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
    """
    
    CREATE_ACCOUNT_FULL = """
        INSERT INTO "Account" (
            "userId", type, provider, "providerAccountId", 
            "access_token", "refresh_token", "expires_at", "token_type", scope, "id_token"
        ) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
        RETURNING *
    """
    
    UPDATE_ACCESS_TOKEN = """
        UPDATE "Account" 
        SET "access_token" = %s, "updatedAt" = CURRENT_TIMESTAMP 
        WHERE "userId" = %s AND provider = %s
        RETURNING *
    """
    
    UPDATE_REFRESH_TOKEN = """
        UPDATE "Account" 
        SET "refresh_token" = %s, "expires_at" = %s, "updatedAt" = CURRENT_TIMESTAMP 
        WHERE "userId" = %s AND provider = %s
        RETURNING *
    """
    
    UPDATE_OAUTH_TOKENS = """
        UPDATE "Account" 
        SET "access_token" = %s, "refresh_token" = %s, "expires_at" = %s, 
            "token_type" = %s, scope = %s, "id_token" = %s, "updatedAt" = CURRENT_TIMESTAMP
        WHERE "userId" = %s AND provider = %s
        RETURNING *
    """
    
    DELETE_ACCOUNT_BY_PROVIDER = """
        DELETE FROM "Account" WHERE provider = %s AND "providerAccountId" = %s
    """
    
    DELETE_ACCOUNTS_BY_USER = """
        DELETE FROM "Account" WHERE "userId" = %s
    """
    
    DELETE_ACCOUNT_BY_USER_PROVIDER = """
        DELETE FROM "Account" WHERE "userId" = %s AND provider = %s
    """

    @staticmethod
    def create_google_account_params(userId: str, google_id: str, access_token: str) -> Tuple[str, tuple]:
        """Create Google OAuth account"""
        return AccountQueries.CREATE_OAUTH_ACCOUNT, (userId, 'oauth', 'google', google_id, access_token)
    
    @staticmethod
    def create_credentials_account_params(userId: str, email: str, hashed_password: str) -> Tuple[str, tuple]:
        """Create credentials account"""
        return AccountQueries.CREATE_CREDENTIALS_ACCOUNT, (userId, 'credentials', 'credentials', email, hashed_password)
    
    @staticmethod
    def get_google_account_params(userId: str) -> Tuple[str, tuple]:
        """Get Google account by user ID"""
        return AccountQueries.GET_GOOGLE_ACCOUNT, (userId,)
    
    @staticmethod
    def get_credentials_account_params(userId: str) -> Tuple[str, tuple]:
        """Get credentials account by user ID"""
        return AccountQueries.GET_CREDENTIALS_ACCOUNT, (userId,)