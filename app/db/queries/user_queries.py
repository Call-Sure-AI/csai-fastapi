from typing import Dict, List, Optional, Tuple

class UserQueries:
    """All SQL queries related to User table"""
    
    GET_USER_BY_EMAIL = """
        SELECT * FROM "User" WHERE email = %s
    """
    
    GET_USER_BY_ID = """
        SELECT * FROM "User" WHERE id = %s
    """
    
    GET_USER_PROFILE = """
        SELECT id, name, email, image, "createdAt", "updatedAt" FROM "User" WHERE id = %s
    """
    
    GET_USER_WITH_CREDENTIALS = """
        SELECT u.*, a."access_token" 
        FROM "User" u
        JOIN "Account" a ON u.id = a."userId"
        WHERE u.email = %s AND a.provider = 'credentials'
    """
    
    CHECK_USER_EXISTS_BY_EMAIL = """
        SELECT id FROM "User" WHERE email = %s
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
        WHERE u.id = %s
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
        WHERE u.id = %s
        GROUP BY u.id
    """
    
    # INSERT queries
    CREATE_USER = """
        INSERT INTO "User" (id, email, name, image, "emailVerified") 
        VALUES (%s, %s, %s, %s, %s) 
        RETURNING *
    """
    
    CREATE_USER_BASIC = """
        INSERT INTO "User" (id, email, name) 
        VALUES (%s, %s, %s) 
        RETURNING *
    """
    
    # UPDATE queries
    UPDATE_USER_EMAIL_VERIFIED = """
        UPDATE "User" 
        SET "emailVerified" = %s, "updatedAt" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    UPDATE_USER_PROFILE = """
        UPDATE "User" 
        SET name = %s, image = %s, "updatedAt" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    UPDATE_USER_NAME = """
        UPDATE "User" 
        SET name = %s, "updatedAt" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    DELETE_USER_BY_ID = """
        DELETE FROM "User" WHERE id = %s
    """
    
    DELETE_USER_BY_EMAIL = """
        DELETE FROM "User" WHERE email = %s
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
        """Create user with parameters"""
        return UserQueries.CREATE_USER, (userId, email, name, image, email_verified)
    
    @staticmethod
    def create_user_basic_params(userId: str, email: str, name: str) -> Tuple[str, tuple]:
        """Create basic user with parameters"""
        return UserQueries.CREATE_USER_BASIC, (userId, email, name)