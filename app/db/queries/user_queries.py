from typing import Dict, List, Optional, Tuple


class UserQueries:
    """All SQL queries related to User table"""
    
    GET_USER_BY_EMAIL = """
        SELECT * FROM "User" WHERE email = $1
    """
    
    GET_USER_BY_ID = """
        SELECT * FROM "User" WHERE id = $1
    """
    
    GET_USER_PROFILE = """
        SELECT id, name, email, image, "createdAt", "updatedAt" FROM "User" WHERE id = $1
    """
    
    GET_USER_WITH_CREDENTIALS = """
        SELECT u.*, a."access_token" 
        FROM "User" u
        JOIN "Account" a ON u.id = a."userId"
        WHERE u.email = $1 AND a.provider = 'credentials'
    """
    
    CHECK_USER_EXISTS_BY_EMAIL = """
        SELECT id FROM "User" WHERE email = $1
    """
    
    GET_USER_WITH_COMPANIES = """
        SELECT u.*, 
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
               ) as owned_companies
        FROM "User" u
        LEFT JOIN "Company" c ON u.id = c."user_id"
        WHERE u.id = $1
        GROUP BY u.id
    """
    
    GET_USER_WITH_MEMBERSHIPS = """
        SELECT u.*,
               COALESCE(
                   JSON_AGG(
                       JSON_BUILD_OBJECT(
                           'company_id', cm."company_id",
                           'role', cm.role,
                           'company_name', comp.name,
                           'created_at', cm."created_at"
                       )
                   ) FILTER (WHERE cm.id IS NOT NULL),
                   '[]'
               ) as memberships
        FROM "User" u
        LEFT JOIN "CompanyMember" cm ON u.id = cm."user_id"
        LEFT JOIN "Company" comp ON cm."company_id" = comp.id
        WHERE u.id = $1
        GROUP BY u.id
    """
    
    CREATE_USER = """
        INSERT INTO "User" (id, email, name, image, "emailVerified", "createdAt", "updatedAt") 
        VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) 
        RETURNING *
    """
    
    # Alternative: If you want to pass timestamps as parameters
    CREATE_USER_WITH_TIMESTAMPS = """
        INSERT INTO "User" (id, email, name, image, "emailVerified", "createdAt", "updatedAt") 
        VALUES ($1, $2, $3, $4, $5, $6, $7) 
        RETURNING *
    """
    
    # Keep other queries the same...
    CREATE_USER_BASIC = """
        INSERT INTO "User" (id, email, name, "createdAt", "updatedAt") 
        VALUES ($1, $2, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) 
        RETURNING *
    """

    
    # UPDATE queries
    UPDATE_USER_EMAIL_VERIFIED = """
        UPDATE "User" 
        SET "emailVerified" = $1, "updatedAt" = CURRENT_TIMESTAMP 
        WHERE id = $2
        RETURNING *
    """
    
    UPDATE_USER_PROFILE = """
        UPDATE "User" 
        SET name = $1, image = $2, "updatedAt" = CURRENT_TIMESTAMP 
        WHERE id = $3
        RETURNING *
    """
    
    UPDATE_USER_NAME = """
        UPDATE "User" 
        SET name = $1, "updatedAt" = CURRENT_TIMESTAMP 
        WHERE id = $2
        RETURNING *
    """
    
    DELETE_USER_BY_ID = """
        DELETE FROM "User" WHERE id = $1
    """
    
    DELETE_USER_BY_EMAIL = """
        DELETE FROM "User" WHERE email = $1
    """

    @staticmethod
    def get_user_by_email_params(email: str) -> Tuple[str, tuple]:
        """Get user by email with parameters"""
        return UserQueries.GET_USER_BY_EMAIL, (email,)
    
    @staticmethod
    def get_user_by_id_params(userId: str) -> Tuple[str, tuple]:
        """Get user by ID with parameters"""
        return UserQueries.GET_USER_BY_ID, (userId,)
    
    @staticmethod
    def create_user_params(userId: str, email: str, name: str, image: str = None, email_verified = None) -> Tuple[str, tuple]:
        return UserQueries.CREATE_USER, (userId, email, name, image, email_verified)

    @staticmethod
    def create_user_with_timestamps_params(userId: str, email: str, name: str, image: str = None, email_verified = None) -> Tuple[str, tuple]:
        now = datetime.utcnow()
        return UserQueries.CREATE_USER_WITH_TIMESTAMPS, (userId, email, name, image, email_verified, now, now)
    
    @staticmethod
    def create_user_basic_params(userId: str, email: str, name: str) -> Tuple[str, tuple]:
        """Create basic user with parameters"""
        return UserQueries.CREATE_USER_BASIC, (userId, email, name)
