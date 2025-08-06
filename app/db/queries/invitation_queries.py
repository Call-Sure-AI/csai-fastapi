from typing import List, Dict, Any, Optional
import asyncpg
import json
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)
# REMOVE THIS LINE - it's importing itself!
# from app.db.queries.invitation_queries import InvitationQueries

class InvitationQueries:
    
    async def create_invitation(
        self, 
        conn: asyncpg.Connection, 
        invitation_data: Dict[str, Any], 
        token: str, 
        expires_at: datetime
    ) -> Dict[str, Any]:
        """Create a new invitation"""
        invitation_id = str(uuid.uuid4())
        query = """
            INSERT INTO invitations (
                id, email, company_id, role, token, status, expires_at, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            RETURNING *
        """
        
        row = await conn.fetchrow(
            query,
            invitation_id,
            invitation_data['email'],
            invitation_data['company_id'],
            invitation_data.get('role', 'member'),
            token,
            'pending',
            expires_at
        )
        return dict(row) if row else None
    
    async def get_invitation_by_token(
        self, 
        conn: asyncpg.Connection, 
        token: str
    ) -> Optional[Dict[str, Any]]:
        """Get invitation by token"""
        query = """
            SELECT i.*, 
                   json_build_object(
                       'id', c.id,
                       'name', c.name,
                       'business_name', c.business_name
                   ) as company
            FROM invitations i
            LEFT JOIN "Company" c ON i.company_id = c.id
            WHERE i.token = $1
        """
        row = await conn.fetchrow(query, token)
        return dict(row) if row else None
    
    async def get_invitation_by_token_with_company(
        self, 
        conn: asyncpg.Connection, 
        token: str
    ) -> Optional[Dict[str, Any]]:
        """Get invitation with full company details"""
        query = """
            SELECT i.*,
                   json_build_object(
                       'id', c.id,
                       'name', c.name,
                       'business_name', c.business_name,
                       'user_id', c.user_id
                   ) as company
            FROM invitations i
            JOIN "Company" c ON i.company_id = c.id
            WHERE i.token = $1
        """
        row = await conn.fetchrow(query, token)
        return dict(row) if row else None
    
    async def get_invitation_by_email_and_company(
        self,
        conn: asyncpg.Connection,
        email: str,
        company_id: str
    ) -> Optional[Dict[str, Any]]:
        """Check if invitation already exists"""
        query = """
            SELECT * FROM invitations
            WHERE email = $1 AND company_id = $2 AND status = 'pending'
        """
        row = await conn.fetchrow(query, email, company_id)
        return dict(row) if row else None
    
    async def update_invitation(
        self,
        conn: asyncpg.Connection,
        invitation_id: str,
        token: str,
        role: str,
        expires_at: datetime
    ) -> Dict[str, Any]:
        """Update existing invitation"""
        query = """
            UPDATE invitations
            SET token = $1, role = $2, expires_at = $3, updated_at = NOW()
            WHERE id = $4
            RETURNING *
        """
        row = await conn.fetchrow(query, token, role, expires_at, invitation_id)
        return dict(row) if row else None
    
    async def accept_invitation(
        self,
        conn: asyncpg.Connection,
        invitation_id: str
    ) -> Dict[str, Any]:
        """Mark invitation as accepted"""
        query = """
            UPDATE invitations
            SET status = 'accepted', accepted_at = NOW(), updated_at = NOW()
            WHERE id = $1
            RETURNING *
        """
        row = await conn.fetchrow(query, invitation_id)
        return dict(row) if row else None
    
    async def get_pending_invitations(
        self,
        conn: asyncpg.Connection,
        company_id: str
    ) -> List[Dict[str, Any]]:
        """Get all pending invitations for a company"""
        query = """
            SELECT * FROM invitations
            WHERE company_id = $1 AND status = 'pending'
            ORDER BY created_at DESC
        """
        rows = await conn.fetch(query, company_id)
        return [dict(row) for row in rows]
    
    async def get_accepted_invitations(
        self,
        conn: asyncpg.Connection,
        company_id: str
    ) -> List[Dict[str, Any]]:
        """Get all accepted invitations for a company"""
        query = """
            SELECT * FROM invitations
            WHERE company_id = $1 AND status = 'accepted'
            ORDER BY accepted_at DESC
        """
        rows = await conn.fetch(query, company_id)
        return [dict(row) for row in rows]
    
    async def get_expired_invitations(
        self,
        conn: asyncpg.Connection,
        company_id: str
    ) -> List[Dict[str, Any]]:
        """Get all expired invitations for a company"""
        query = """
            SELECT * FROM invitations
            WHERE company_id = $1 
            AND (status = 'expired' OR (status = 'pending' AND expires_at < NOW()))
            ORDER BY expires_at DESC
        """
        rows = await conn.fetch(query, company_id)
        return [dict(row) for row in rows]
    
    async def delete_invitation(
        self,
        conn: asyncpg.Connection,
        invitation_id: str
    ) -> bool:
        """Delete an invitation"""
        query = """
            DELETE FROM invitations
            WHERE id = $1
            RETURNING id
        """
        row = await conn.fetchrow(query, invitation_id)
        return row is not None
    
    async def get_invitation_with_company(
        self,
        conn: asyncpg.Connection,
        invitation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get invitation with company details"""
        query = """
            SELECT i.*,
                   json_build_object(
                       'id', c.id,
                       'name', c.name,
                       'business_name', c.business_name,
                       'user_id', c.user_id
                   ) as company
            FROM invitations i
            JOIN "Company" c ON i.company_id = c.id
            WHERE i.id = $1
        """
        row = await conn.fetchrow(query, invitation_id)
        return dict(row) if row else None
    
    # Helper queries for other tables
    async def get_company_by_id(
        self,
        conn: asyncpg.Connection,
        company_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get company by ID"""
        query = """
            SELECT * FROM "Company"
            WHERE id = $1
        """
        row = await conn.fetchrow(query, company_id)
        return dict(row) if row else None
    
    async def get_user_by_email(
        self,
        conn: asyncpg.Connection,
        email: str
    ) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        query = """
            SELECT * FROM "User"
            WHERE email = $1
        """
        row = await conn.fetchrow(query, email)
        return dict(row) if row else None
    
    async def create_user_with_account(
        self,
        conn: asyncpg.Connection,
        email: str,
        name: str,
        hashed_password: str
    ) -> Dict[str, Any]:
        """Create new user with account"""
        import string
        import random
        from datetime import datetime
        
        # Generate user ID in your format: cma[random]0000qp01[random]
        def generate_user_id():
            chars = string.ascii_lowercase + string.digits
            part1 = ''.join(random.choices(chars, k=6))
            part2 = ''.join(random.choices(chars, k=6))
            return f"cma{part1}0000qp01{part2}"
        
        user_id = generate_user_id()
        now = datetime.now()
        
        # Create user with camelCase columns
        user_query = """
            INSERT INTO "User" (id, email, name, "createdAt", "updatedAt")
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """
        user = await conn.fetchrow(user_query, user_id, email, name, now, now)
        
        # Create account - note: Account table doesn't have an 'id' column
        account_query = """
            INSERT INTO "Account" (
                "userId", 
                type, 
                provider, 
                "providerAccountId",
                access_token,
                "createdAt",
                "updatedAt"
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        await conn.execute(
            account_query, 
            user_id,  # userId
            'credentials',  # type
            'credentials',  # provider
            email,  # providerAccountId
            hashed_password,  # access_token (storing hashed password here)
            now,  # createdAt
            now   # updatedAt
        )
        
        return dict(user) if user else None
    
    async def create_company_membership(
        self,
        conn: asyncpg.Connection,
        user_id: str,
        company_id: str,
        role: str
    ) -> Dict[str, Any]:
        """Create company membership"""
        # Check if membership already exists
        check_query = """
            SELECT id FROM "CompanyMember"
            WHERE user_id = $1 AND company_id = $2
        """
        existing = await conn.fetchrow(check_query, user_id, company_id)
        
        if existing:
            # Update role if membership exists
            update_query = """
                UPDATE "CompanyMember"
                SET role = $1, updated_at = NOW()
                WHERE user_id = $2 AND company_id = $3
                RETURNING *
            """
            row = await conn.fetchrow(update_query, role, user_id, company_id)
        else:
            # Create new membership
            membership_id = str(uuid.uuid4())
            insert_query = """
                INSERT INTO "CompanyMember" (id, user_id, company_id, role, created_at, updated_at)
                VALUES ($1, $2, $3, $4, NOW(), NOW())
                RETURNING *
            """
            row = await conn.fetchrow(insert_query, membership_id, user_id, company_id, role)
        
        return dict(row) if row else None