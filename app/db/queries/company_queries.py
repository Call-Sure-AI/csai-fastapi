from typing import List, Dict, Any, Optional
from app.models.schemas import CompanyCreate, CompanyUpdate, CompanySettings
import asyncpg
import json
from datetime import datetime
import uuid
import logging
logger = logging.getLogger(__name__)

class CompanyQueries:
    
    @staticmethod
    def count_companies_by_owner_params(user_id: str) -> tuple:
        """Count companies owned by user"""
        query = """
            SELECT COUNT(*) as count FROM "Company" WHERE user_id = $1
        """
        return query, (user_id,)
    
    @staticmethod
    def get_user_first_membership_params(user_id: str) -> tuple:
        """Get user's first company membership"""
        query = """
            SELECT cm.role FROM "CompanyMember" cm
            WHERE cm.user_id = $1
            LIMIT 1
        """
        return query, (user_id,)
        
    async def get_companies_by_user_id(self, conn: asyncpg.Connection, user_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                c.*,
                COUNT(DISTINCT a.id) as agent_count,
                json_agg(DISTINCT jsonb_build_object(
                    'id', a.id,
                    'name', a.name,
                    'type', a.type,
                    'is_active', a.is_active
                )) FILTER (WHERE a.id IS NOT NULL) as agents,
                (
                    SELECT json_agg(
                        jsonb_build_object('id', call_sub.id, 'created_at', call_sub.created_at)
                        ORDER BY call_sub.created_at DESC
                    )
                    FROM "Call" call_sub 
                    WHERE call_sub.company_id = c.id
                    LIMIT 5
                ) as recent_calls,
                (
                    SELECT json_agg(
                        jsonb_build_object('id', conv_sub.id, 'created_at', conv_sub.created_at)
                        ORDER BY conv_sub.created_at DESC
                    )
                    FROM "Conversation" conv_sub 
                    WHERE conv_sub.company_id = c.id
                    LIMIT 5
                ) as recent_conversations
            FROM "Company" c
            LEFT JOIN "Agent" a ON c.id = a.company_id
            WHERE c.user_id = $1
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """
        rows = await conn.fetch(query, user_id)
        return [dict(row) for row in rows]
    
    async def get_user_with_memberships(self, conn: asyncpg.Connection, user_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT 
                u.id,
                json_agg(jsonb_build_object(
                    'company_id', cm.company_id
                )) FILTER (WHERE cm.company_id IS NOT NULL) as company_memberships
            FROM "User" u
            LEFT JOIN "CompanyMember" cm ON u.id = cm.user_id
            WHERE u.id = $1
            GROUP BY u.id
        """
        row = await conn.fetchrow(query, user_id)
        return dict(row) if row else None
    
    async def get_company_by_user_id_single(self, conn: asyncpg.Connection, user_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT 
                c.*,
                (
                    SELECT json_agg(
                        jsonb_build_object(
                            'id', a.id,
                            'name', a.name,
                            'type', a.type,
                            'is_active', a.is_active
                        )
                    )
                    FROM "Agent" a 
                    WHERE a.company_id = c.id
                ) as agents,
                (
                    SELECT json_agg(
                        jsonb_build_object('id', call.id, 'created_at', call.created_at)
                        ORDER BY call.created_at DESC
                    )
                    FROM "Call" call 
                    WHERE call.company_id = c.id
                    LIMIT 10
                ) as recent_calls,
                (
                    SELECT json_agg(
                        jsonb_build_object('id', conv.id, 'created_at', conv.created_at)
                        ORDER BY conv.created_at DESC
                    )
                    FROM "Conversation" conv 
                    WHERE conv.company_id = c.id
                    LIMIT 10
                ) as recent_conversations
            FROM "Company" c
            WHERE c.user_id = $1
            ORDER BY c.created_at DESC
            LIMIT 1
        """
        row = await conn.fetchrow(query, user_id)
        return dict(row) if row else None
    
    async def get_company_by_id(self, conn: asyncpg.Connection, company_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT 
                c.*,
                (
                    SELECT json_agg(
                        jsonb_build_object(
                            'id', a.id,
                            'name', a.name,
                            'type', a.type,
                            'is_active', a.is_active
                        )
                    )
                    FROM "Agent" a 
                    WHERE a.company_id = c.id
                ) as agents,
                (
                    SELECT json_agg(
                        jsonb_build_object('id', call.id, 'created_at', call.created_at)
                        ORDER BY call.created_at DESC
                    )
                    FROM "Call" call 
                    WHERE call.company_id = c.id
                    LIMIT 10
                ) as recent_calls,
                (
                    SELECT json_agg(
                        jsonb_build_object('id', conv.id, 'created_at', conv.created_at)
                        ORDER BY conv.created_at DESC
                    )
                    FROM "Conversation" conv 
                    WHERE conv.company_id = c.id
                    LIMIT 10
                ) as recent_conversations
            FROM "Company" c
            WHERE c.id = $1
        """
        row = await conn.fetchrow(query, company_id)
        return dict(row) if row else None
    
    async def get_companies_by_user_id_simple(self, conn: asyncpg.Connection, user_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT 
                c.*,
                (
                    SELECT json_agg(
                        jsonb_build_object(
                            'id', a.id,
                            'name', a.name,
                            'type', a.type
                        )
                    )
                    FROM "Agent" a 
                    WHERE a.company_id = c.id
                ) as agents,
                (
                    SELECT json_agg(jsonb_build_object('id', call.id))
                    FROM "Call" call 
                    WHERE call.company_id = c.id
                ) as calls
            FROM "Company" c
            WHERE c.user_id = $1
            ORDER BY c.created_at DESC
        """
        rows = await conn.fetch(query, user_id)
        return [dict(row) for row in rows]
    
    async def get_company_by_id_and_user(self, conn: asyncpg.Connection, company_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT * FROM "Company"
            WHERE id = $1 AND user_id = $2
        """
        row = await conn.fetchrow(query, company_id, user_id)
        return dict(row) if row else None
    
    async def create_company(self, conn: asyncpg.Connection, company_data: CompanyCreate, user_id: str, api_key: str) -> Dict[str, Any]:
        company_id = str(uuid.uuid4())
        query = """
            INSERT INTO "Company" (
                id, name, business_name, email, address, website, logo,
                prompt_templates, phone_number, settings, user_id, api_key,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW(), NOW())
            RETURNING *
        """

        company_dict = company_data.model_dump()

        prompt_templates_json = json.dumps(company_dict.get('prompt_templates')) if company_dict.get('prompt_templates') else None
        settings_json = json.dumps(company_dict.get('settings')) if company_dict.get('settings') else None
        
        try:
            row = await conn.fetchrow(
                query,
                company_id,
                company_dict['name'],
                company_dict['business_name'],
                company_dict['email'],
                company_dict['address'],
                str(company_dict.get('website')),
                company_dict.get('logo'),
                prompt_templates_json,
                company_dict.get('phone_number'),
                settings_json,
                user_id,
                api_key
            )
            return dict(row)
        except Exception as e:
            logger.error(f"Database error in create_company: {e}", exc_info=True)
            raise
    
    async def update_company(self, conn: asyncpg.Connection, company_id: str, company_data: CompanyUpdate, user_id: str) -> Dict[str, Any]:
        update_fields = []
        values = []
        param_count = 1
        
        company_dict = company_data.dict(exclude_unset=True)
        
        for field, value in company_dict.items():
            if field in ['prompt_templates', 'settings']:
                values.append(json.dumps(value) if value else None)
            else:
                values.append(value)
            
            update_fields.append(f"{field} = ${param_count}")
            param_count += 1
        
        if not update_fields:
            return await self.get_company_by_id_and_user(conn, company_id, user_id)
        
        update_fields.append(f"updated_at = NOW()")
        values.extend([company_id, user_id])
        
        query = f"""
            UPDATE "Company"
            SET {', '.join(update_fields)}
            WHERE id = ${param_count} AND user_id = ${param_count + 1}
            RETURNING *
        """
        
        row = await conn.fetchrow(query, *values)
        return dict(row)
    
    async def delete_company(self, conn: asyncpg.Connection, company_id: str) -> Dict[str, Any]:
        query = """
            DELETE FROM "Company"
            WHERE id = $1 
            RETURNING *
        """
        row = await conn.fetchrow(query, company_id)
        return dict(row)
    
    async def update_api_key(self, conn: asyncpg.Connection, company_id: str, api_key: str) -> Dict[str, Any]:
        query = """
            UPDATE "Company"
            SET api_key = $1, updated_at = NOW()
            WHERE id = $2
            RETURNING *
        """
        row = await conn.fetchrow(query, api_key, company_id)
        return dict(row)

    # Static methods for auth queries
    COUNT_COMPANIES_BY_OWNER = """
        SELECT COUNT(*) as count FROM "Company" WHERE user_id = $1
    """
    
    GET_USER_FIRST_MEMBERSHIP = """
        SELECT cm.role 
        FROM "CompanyMember" cm 
        WHERE cm.user_id = $1 
        ORDER BY cm.created_at ASC 
        LIMIT 1
    """

    @staticmethod
    def count_companies_by_owner_params(user_id: str) -> tuple:
        """Count companies owned by user"""
        return CompanyQueries.COUNT_COMPANIES_BY_OWNER, (user_id,)
    
    @staticmethod
    def get_user_first_membership_params(user_id: str) -> tuple:
        """Get user's first company membership"""
        return CompanyQueries.GET_USER_FIRST_MEMBERSHIP, (user_id,)
