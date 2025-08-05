from typing import Dict, List, Optional, Tuple


class AccountQueries:
    """All SQL queries related to Account table"""
    
    GET_ACCOUNTS_BY_USER_ID = """
        SELECT * FROM "Account" WHERE "userId" = $1
    """
    
    GET_ACCOUNT_BY_PROVIDER = """
        SELECT * FROM "Account" 
        WHERE "userId" = $1 AND provider = $2
    """
    
    GET_GOOGLE_ACCOUNT = """
        SELECT * FROM "Account" 
        WHERE "userId" = $1 AND provider = 'google'
    """
    
    GET_CREDENTIALS_ACCOUNT = """
        SELECT * FROM "Account" 
        WHERE "userId" = $1 AND provider = 'credentials'
    """
    
    GET_ACCOUNT_BY_PROVIDER_ID = """
        SELECT * FROM "Account" 
        WHERE provider = $1 AND "providerAccountId" = $2
    """
    
    CREATE_OAUTH_ACCOUNT = """
<<<<<<< HEAD
        INSERT INTO "Account" ("userId", type, provider, "providerAccountId", "access_token", "createdAt", "updatedAt") 
        VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) 
=======
        INSERT INTO "Account" ("userId", type, provider, "providerAccountId", "access_token") 
        VALUES ($1, $2, $3, $4, $5) 
>>>>>>> 96bee3d452de7d0f058473e83eb6eaeac9703abe
        RETURNING *
    """
    
    CREATE_CREDENTIALS_ACCOUNT = """
<<<<<<< HEAD
        INSERT INTO "Account" ("userId", type, provider, "providerAccountId", "access_token", "createdAt", "updatedAt")
        VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
=======
        INSERT INTO "Account" ("userId", type, provider, "providerAccountId", "access_token")
        VALUES ($1, $2, $3, $4, $5)
>>>>>>> 96bee3d452de7d0f058473e83eb6eaeac9703abe
        RETURNING *
    """
    
    CREATE_ACCOUNT_FULL = """
        INSERT INTO "Account" (
            "userId", type, provider, "providerAccountId", 
            "access_token", "refresh_token", "expires_at", "token_type", scope, "id_token",
            "createdAt", "updatedAt"
        ) 
<<<<<<< HEAD
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) 
=======
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) 
>>>>>>> 96bee3d452de7d0f058473e83eb6eaeac9703abe
        RETURNING *
    """
    
    UPDATE_ACCESS_TOKEN = """
        UPDATE "Account" 
        SET "access_token" = $1, "updatedAt" = CURRENT_TIMESTAMP 
        WHERE "userId" = $2 AND provider = $3
        RETURNING *
    """
    
    UPDATE_REFRESH_TOKEN = """
        UPDATE "Account" 
        SET "refresh_token" = $1, "expires_at" = $2, "updatedAt" = CURRENT_TIMESTAMP 
        WHERE "userId" = $3 AND provider = $4
        RETURNING *
    """
    
    UPDATE_OAUTH_TOKENS = """
        UPDATE "Account" 
        SET "access_token" = $1, "refresh_token" = $2, "expires_at" = $3, 
            "token_type" = $4, scope = $5, "id_token" = $6, "updatedAt" = CURRENT_TIMESTAMP
        WHERE "userId" = $7 AND provider = $8
        RETURNING *
    """
    
    DELETE_ACCOUNT_BY_PROVIDER = """
        DELETE FROM "Account" WHERE provider = $1 AND "providerAccountId" = $2
    """
    
    DELETE_ACCOUNTS_BY_USER = """
        DELETE FROM "Account" WHERE "userId" = $1
    """
    
    DELETE_ACCOUNT_BY_USER_PROVIDER = """
        DELETE FROM "Account" WHERE "userId" = $1 AND provider = $2
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
