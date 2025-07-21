from typing import List, Optional, Dict, Any
import secrets
from app.db.postgres_client import get_db_connection
from app.db.queries.company_queries import CompanyQueries
from app.utils.activity_logger import ActivityLogger
from app.models.schemas import CompanyCreate, CompanyUpdate, Company
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)

class CompanyHandler:
    def __init__(self):
        self.company_queries = CompanyQueries()
        self.activity_logger = ActivityLogger()

    async def get_all_companies_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            async with get_db_connection() as conn:
                companies = await self.company_queries.get_companies_by_user_id(conn, user_id)
                return companies
        except Exception as error:
            logger.error(f"Error fetching companies: {error}")
            raise Exception("Internal server error")

    async def get_company_by_user(self, user_id: str) -> Dict[str, Any]:
        try:
            async with get_db_connection() as conn:
                user_data = await self.company_queries.get_user_with_memberships(conn, user_id)
                
                company = await self.company_queries.get_company_by_user_id_single(conn, user_id)
                
                if not company:
                    if user_data and user_data.get('company_memberships'):
                        membership_company_id = user_data['company_memberships'][0]['company_id']
                        company = await self.company_queries.get_company_by_id(conn, membership_company_id)
                    
                    if not company:
                        raise ValueError("Company not found")
                
                return company
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error fetching company: {error}")
            raise Exception("Internal server error")

    async def get_companies_by_user_id(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            async with get_db_connection() as conn:
                companies = await self.company_queries.get_companies_by_user_id_simple(conn, user_id)
                return companies
        except Exception as error:
            logger.error(f"Error fetching companies: {error}")
            raise Exception("Internal server error")

    async def create_company(self, company_data: CompanyCreate, user_id: str) -> Dict[str, Any]:
        try:
            api_key = secrets.token_hex(32)
            
            async with get_db_connection() as conn:
                company = await self.company_queries.create_company(conn, company_data, user_id, api_key)
                
                try:
                    await self.activity_logger.log({
                        'user_id': user_id,
                        'action': 'CREATE',
                        'entity_type': 'COMPANY',
                        'entity_id': company['id'],
                        'metadata': {
                            'name': company['name'],
                            'business_name': company['business_name'],
                            'email': company['email']
                        }
                    })
                except Exception as log_error:
                    logger.error(f'Failed to log company creation activity: {log_error}')
                
                return company
                
        except Exception as error:
            logger.error(f"Error creating company: {error}")
            if "unique constraint" in str(error).lower() or "duplicate key" in str(error).lower():
                raise ValueError("Email or phone number already exists")
            raise Exception("Internal server error")

    async def create_or_update_company(self, company_data: CompanyCreate, user_id: str) -> Dict[str, Any]:
        try:
            async with get_db_connection() as conn:
                existing_company = await self.company_queries.get_company_by_user_id_single(conn, user_id)
                
                if existing_company:
                    company = await self.company_queries.update_company(
                        conn, existing_company['id'], company_data, user_id
                    )
                    
                    try:
                        await self.activity_logger.log({
                            'user_id': user_id,
                            'action': 'UPDATE',
                            'entity_type': 'COMPANY',
                            'entity_id': existing_company['id'],
                            'metadata': {
                                'updated_fields': company_data.dict(exclude_unset=True)
                            }
                        })
                    except Exception as log_error:
                        logger.error(f'Failed to log company update activity: {log_error}')
                    
                    return company
                else:
                    api_key = secrets.token_hex(32)
                    company = await self.company_queries.create_company(conn, company_data, user_id, api_key)
                    
                    try:
                        await self.activity_logger.log({
                            'user_id': user_id,
                            'action': 'CREATE',
                            'entity_type': 'COMPANY',
                            'entity_id': company['id'],
                            'metadata': {
                                'name': company['name'],
                                'business_name': company['business_name'],
                                'email': company['email']
                            }
                        })
                    except Exception as log_error:
                        logger.error(f'Failed to log company creation activity: {log_error}')
                    
                    return company
                    
        except Exception as error:
            logger.error(f"Error creating/updating company: {error}")
            if "unique constraint" in str(error).lower() or "duplicate key" in str(error).lower():
                raise ValueError("Email or phone number already exists")
            raise Exception("Internal server error")

    async def update_company(self, company_id: str, company_data: CompanyUpdate, user_id: str) -> Dict[str, Any]:
        try:
            async with get_db_connection() as conn:
                # Check if company exists and belongs to user
                company = await self.company_queries.get_company_by_id_and_user(conn, company_id, user_id)
                
                if not company:
                    raise ValueError("Company not found")
            
                updated_company = await self.company_queries.update_company(conn, company_id, company_data, user_id)
                
                try:
                    await self.activity_logger.log({
                        'user_id': user_id,
                        'action': 'UPDATE',
                        'entity_type': 'COMPANY',
                        'entity_id': company_id,
                        'metadata': {
                            'updated_fields': company_data.dict(exclude_unset=True)
                        }
                    })
                except Exception as log_error:
                    logger.error(f'Failed to log company update activity: {log_error}')
                
                return updated_company
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error updating company: {error}")
            if "unique constraint" in str(error).lower() or "duplicate key" in str(error).lower():
                raise ValueError("Email or phone number already exists")
            raise Exception("Internal server error")

    async def delete_company(self, company_id: str, user_id: str) -> Dict[str, Any]:
        try:
            async with get_db_connection() as conn:
                company = await self.company_queries.get_company_by_id_and_user(conn, company_id, user_id)
                
                if not company:
                    raise ValueError("Company not found")
                
                deleted_company = await self.company_queries.delete_company(conn, company_id)
                
                try:
                    await self.activity_logger.log({
                        'user_id': user_id,
                        'action': 'DELETE',
                        'entity_type': 'COMPANY',
                        'entity_id': company_id,
                        'metadata': {
                            'company_name': company['name']
                        }
                    })
                except Exception as log_error:
                    logger.error(f'Failed to log company deletion activity: {log_error}')
                
                return deleted_company
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error deleting company: {error}")
            raise Exception("Internal server error")

    async def regenerate_api_key(self, company_id: str, user_id: str) -> Dict[str, str]:
        try:
            async with get_db_connection() as conn:
                company = await self.company_queries.get_company_by_id_and_user(conn, company_id, user_id)
                
                if not company:
                    raise ValueError("Company not found")
                
                new_api_key = secrets.token_hex(32)

                updated_company = await self.company_queries.update_api_key(conn, company_id, new_api_key)
                
                try:
                    await self.activity_logger.log({
                        'user_id': user_id,
                        'action': 'REGENERATE_API_KEY',
                        'entity_type': 'COMPANY',
                        'entity_id': company_id,
                        'metadata': {
                            'company_name': company['name']
                        }
                    })
                except Exception as log_error:
                    logger.error(f'Failed to log API key regeneration activity: {log_error}')
                
                return {"api_key": updated_company['api_key']}
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error regenerating API key: {error}")
            raise Exception("Internal server error")
