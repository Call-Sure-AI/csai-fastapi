from typing import List, Dict, Any, Optional
from datetime import datetime
from app.models.schemas import InvitationCreate
import asyncpg

class InvitationQueries:
    
    async def get_company_by_id(self, conn: asyncpg.Connection, company_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM companies WHERE id = $1"
        row = await conn.fetchrow(query, company_id)
        return dict(row) if row else None
    
    async def get_invitation_by_email_and_company(
        self, conn: asyncpg.Connection, email: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        query = """
            SELECT * FROM invitations 
            WHERE email = $1 AND company_id = $2
        """
        row = await conn.fetchrow(query, email, company_id)
        return dict(row) if row else None
    
    async def create_invitation(
        self, conn: asyncpg.Connection, invitation_data: InvitationCreate, token: str, expires_at: datetime
    ) -> Dict[str, Any]:
        query = """
            INSERT INTO invitations (email, company_id, role, token, expires_at, status, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, 'pending', NOW(), NOW())
            RETURNING *
        """
        row = await conn.fetchrow(
            query,
            invitation_data.email,
            invitation_data.company_id,
            invitation_data.role or 'member',
            token,
            expires_at
        )
        return dict(row)
    
    async def update_invitation(
        self, conn: asyncpg.Connection, invitation_id: str, token: str, role: str, expires_at: datetime
    ) -> Dict[str, Any]:
        query = """
            UPDATE invitations 
            SET token = $1, role = $2, expires_at = $3, updated_at = NOW(), status = 'pending'
            WHERE id = $4
            RETURNING *
        """
        row = await conn.fetchrow(query, token, role, expires_at, invitation_id)
        return dict(row)
    
    async def get_invitation_by_token(self, conn: asyncpg.Connection, token: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT 
                i.*,
                json_build_object(
                    'id', c.id,
                    'name', c.name,
                    'business_name', c.business_name
                ) as company
            FROM invitations i
            JOIN companies c ON i.company_id = c.id
            WHERE i.token = $1
        """
        row = await conn.fetchrow(query, token)
        return dict(row) if row else None
    
    async def get_invitation_by_token_with_company(
        self, conn: asyncpg.Connection, token: str
    ) -> Optional[Dict[str, Any]]:
        query = """
            SELECT 
                i.*,
                c.id as company_id,
                c.name as company_name,
                c.business_name as company_business_name
            FROM invitations i
            JOIN companies c ON i.company_id = c.id
            WHERE i.token = $1
        """
        row = await conn.fetchrow(query, token)
        if row:
            invitation = dict(row)
            invitation['company'] = {
                'id': invitation['company_id'],
                'name': invitation['company_name'],
                'business_name': invitation['company_business_name']
            }
            return invitation
        return None
    
    async def get_user_by_email(self, conn: asyncpg.Connection, email: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM users WHERE email = $1"
        row = await conn.fetchrow(query, email)
        return dict(row) if row else None
    
    async def create_user_with_account(
        self, conn: asyncpg.Connection, email: str, name: str, hashed_password: str
    ) -> Dict[str, Any]:

        user_query = """
            INSERT INTO users (email, name, email_verified, created_at, updated_at)
            VALUES ($1, $2, NOW(), NOW(), NOW())
            RETURNING *
        """
        user = await conn.fetchrow(user_query, email, name)
        user_dict = dict(user)
        
        account_query = """
            INSERT INTO accounts (user_id, type, provider, provider_account_id, access_token)
            VALUES ($1, 'credentials', 'credentials', $2, $3)
        """
        await conn.execute(account_query, user_dict['id'], email, hashed_password)
        
        return user_dict
    
    async def create_company_membership(
        self, conn: asyncpg.Connection, user_id: str, company_id: str, role: str
    ) -> None:
        query = """
            INSERT INTO company_members (user_id, company_id, role, created_at, updated_at)
            VALUES ($1, $2, $3, NOW(), NOW())
        """
        await conn.execute(query, user_id, company_id, role)
    
    async def accept_invitation(self, conn: asyncpg.Connection, invitation_id: str) -> None:
        query = """
            UPDATE invitations 
            SET status = 'accepted', accepted_at = NOW(), updated_at = NOW()
            WHERE id = $1
        """
        await conn.execute(query, invitation_id)
    
    async def get_pending_invitations(
        self, conn: asyncpg.Connection, company_id: str
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM invitations
            WHERE company_id = $1 AND expires_at > NOW()
            ORDER BY created_at DESC
        """
        rows = await conn.fetch(query, company_id)
        return [dict(row) for row in rows]
    
    async def get_accepted_invitations(
        self, conn: asyncpg.Connection, company_id: str
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM invitations
            WHERE company_id = $1 AND status = 'accepted'
            ORDER BY accepted_at DESC
        """
        rows = await conn.fetch(query, company_id)
        return [dict(row) for row in rows]
    
    async def get_expired_invitations(
        self, conn: asyncpg.Connection, company_id: str
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM invitations
            WHERE company_id = $1 AND status = 'pending' AND expires_at < NOW()
            ORDER BY created_at DESC
        """
        rows = await conn.fetch(query, company_id)
        return [dict(row) for row in rows]
    
    async def get_invitation_with_company(
        self, conn: asyncpg.Connection, invitation_id: str
    ) -> Optional[Dict[str, Any]]:
        query = """
            SELECT 
                i.*,
                json_build_object(
                    'id', c.id,
                    'name', c.name,
                    'business_name', c.business_name,
                    'user_id', c.user_id
                ) as company
            FROM invitations i
            JOIN companies c ON i.company_id = c.id
            WHERE i.id = $1
        """
        row = await conn.fetchrow(query, invitation_id)
        return dict(row) if row else None
    
    async def delete_invitation(self, conn: asyncpg.Connection, invitation_id: str) -> None:
        query = "DELETE FROM invitations WHERE id = $1"
        await conn.execute(query, invitation_id)
