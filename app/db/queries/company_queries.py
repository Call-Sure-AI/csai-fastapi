from typing import Dict, List, Optional, Tuple

class CompanyQueries:
    """All SQL queries related to Company and CompanyMember tables"""
    
    GET_COMPANIES_BY_OWNER = """
        SELECT * FROM "Company" WHERE "user_id" = %s
    """
    
    GET_COMPANY_BY_ID = """
        SELECT * FROM "Company" WHERE id = %s
    """
    
    COUNT_COMPANIES_BY_OWNER = """
        SELECT COUNT(*) as count FROM "Company" WHERE "user_id" = %s
    """
    
    GET_COMPANIES_WITH_OWNER = """
        SELECT c.*, u.name as owner_name, u.email as owner_email
        FROM "Company" c
        JOIN "User" u ON c."user_id" = u.id
        WHERE c.id = %s
    """
    
    GET_USER_MEMBERSHIPS = """
        SELECT cm.*, c.name as company_name, c."business_name" as company_business_name
        FROM "CompanyMember" cm
        JOIN "Company" c ON cm."company_id" = c.id
        WHERE cm."user_id" = %s
    """
    
    GET_COMPANY_MEMBERS = """
        SELECT cm.*, u.name as user_name, u.email as user_email, u.image as user_image
        FROM "CompanyMember" cm
        JOIN "User" u ON cm."user_id" = u.id
        WHERE cm."company_id" = %s
    """
    
    GET_USER_ROLE_IN_COMPANY = """
        SELECT role FROM "CompanyMember" 
        WHERE "user_id" = %s AND "company_id" = %s
    """
    
    GET_USER_FIRST_MEMBERSHIP = """
        SELECT role FROM "CompanyMember" 
        WHERE "user_id" = %s 
        ORDER BY "created_at" ASC 
        LIMIT 1
    """
    
    CHECK_MEMBERSHIP_EXISTS = """
        SELECT id FROM "CompanyMember" 
        WHERE "user_id" = %s AND "company_id" = %s
    """
    
    GET_COMPANY_WITH_SETTINGS = """
        SELECT c.*, c.settings, c."image_config", c."prompt_templates"
        FROM "Company" c
        WHERE c.id = %s
    """
    
    CREATE_COMPANY = """
        INSERT INTO "Company" (id, "user_id", name, "business_name", email, address) 
        VALUES (%s, %s, %s, %s, %s, %s) 
        RETURNING *
    """
    
    CREATE_COMPANY_BASIC = """
        INSERT INTO "Company" (id, "user_id", name, "business_name", email, address) 
        VALUES (%s, %s, %s, %s, %s, %s) 
        RETURNING *
    """
    
    CREATE_MEMBERSHIP = """
        INSERT INTO "CompanyMember" (id, "user_id", "company_id", role) 
        VALUES (%s, %s, %s, %s) 
        RETURNING *
    """
    
    CREATE_MEMBERSHIP_DEFAULT_ROLE = """
        INSERT INTO "CompanyMember" (id, "user_id", "company_id") 
        VALUES (%s, %s, %s) 
        RETURNING *
    """
    
    UPDATE_COMPANY_INFO = """
        UPDATE "Company" 
        SET name = %s, "business_name" = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    UPDATE_COMPANY_SETTINGS = """
        UPDATE "Company" 
        SET settings = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    UPDATE_COMPANY_API_KEY = """
        UPDATE "Company" 
        SET "api_key" = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE id = %s
        RETURNING *
    """
    
    UPDATE_MEMBER_ROLE = """
        UPDATE "CompanyMember" 
        SET role = %s, "updated_at" = CURRENT_TIMESTAMP 
        WHERE "user_id" = %s AND "company_id" = %s
        RETURNING *
    """
    
    DELETE_COMPANY = """
        DELETE FROM "Company" WHERE id = %s
    """
    
    DELETE_COMPANIES_BY_OWNER = """
        DELETE FROM "Company" WHERE "user_id" = %s
    """
    
    DELETE_MEMBERSHIP = """
        DELETE FROM "CompanyMember" 
        WHERE "user_id" = %s AND "company_id" = %s
    """
    
    DELETE_MEMBERSHIPS_BY_USER = """
        DELETE FROM "CompanyMember" WHERE "user_id" = %s
    """
    
    DELETE_MEMBERSHIPS_BY_COMPANY = """
        DELETE FROM "CompanyMember" WHERE "company_id" = %s
    """

    @staticmethod
    def count_companies_by_owner_params(owner_id: str) -> Tuple[str, tuple]:
        """Count companies owned by user"""
        return CompanyQueries.COUNT_COMPANIES_BY_OWNER, (owner_id,)
    
    @staticmethod
    def get_user_first_membership_params(userId: str) -> Tuple[str, tuple]:
        """Get user's first company membership"""
        return CompanyQueries.GET_USER_FIRST_MEMBERSHIP, (userId,)
    
    @staticmethod
    def create_company_params(company_id: str, name: str, description: str, owner_id: str) -> Tuple[str, tuple]:
        """Create company parameters"""
        return CompanyQueries.CREATE_COMPANY, (company_id, name, description, owner_id)
    
    @staticmethod
    def create_membership_params(membership_id: str, userId: str, company_id: str, role: str = 'member') -> Tuple[str, tuple]:
        """Create company membership parameters"""
        return CompanyQueries.CREATE_MEMBERSHIP, (membership_id, userId, company_id, role)