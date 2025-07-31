from typing import List, Optional, Dict, Any
import secrets
from app.db.postgres_client import get_db_connection
from app.db.queries.company_queries import CompanyQueries
from app.utils.activity_logger import ActivityLogger
from app.models.schemas import CompanyCreate, CompanyUpdate, Company, CompanySettings
from pydantic import ValidationError
import logging
import json
import asyncpg

logger = logging.getLogger(__name__)

class CompanyHandler:
    def __init__(self):
        self.company_queries = CompanyQueries()
        self.activity_logger = ActivityLogger()

    def _parse_json_fields(self, company: Dict[str, Any]) -> Dict[str, Any]:
        if not company:
            return company
            
        json_fields = ['prompt_templates', 'settings']
        
        for field in json_fields:
            if field in company and company[field] is not None:
                if isinstance(company[field], str):
                    try:
                        if company[field].strip() in ['{}', '']:
                            company[field] = {} if field == 'prompt_templates' else None
                        else:
                            parsed_data = json.loads(company[field])
                            company[field] = parsed_data  # ✅ Convert to dict
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Failed to parse JSON field {field}: {company[field]}, error: {e}")
                        company[field] = {} if field == 'prompt_templates' else None
                elif company[field] == '':
                    company[field] = {} if field == 'prompt_templates' else None
        
        return company


    async def get_all_companies_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            connection = await get_db_connection()
            async with connection as conn:
                companies = await self.company_queries.get_companies_by_user_id(conn, user_id)
                if not companies:
                    return []

                parsed_companies = []
                for company in companies:
                    parsed_company = self._parse_json_fields(company)
                    parsed_companies.append(parsed_company)
                
                logger.info(f"Returning {len(parsed_companies)} companies with parsed JSON fields")
                return parsed_companies
                
        except Exception as error:
            logger.error(f"Error fetching companies: {error}")
            raise Exception("Internal server error")

    async def get_company_by_user(self, user_id: str) -> Dict[str, Any]:
        try:
            connection = await get_db_connection()
            async with connection as conn:
                user_data = await self.company_queries.get_user_with_memberships(conn, user_id)
                company = await self.company_queries.get_company_by_user_id_single(conn, user_id)
                
                if not company:
                    if user_data and user_data.get('company_memberships'):
                        membership_company_id = user_data['company_memberships'][0]['company_id']
                        company = await self.company_queries.get_company_by_id(conn, membership_company_id)
                    
                    if not company:
                        raise ValueError("Company not found")
                
                parsed_company = self._parse_json_fields(company)
                logger.info(f"Returning company with parsed JSON fields: {parsed_company.get('id')}")
                return parsed_company
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error fetching company: {error}")
            raise Exception("Internal server error")

    async def get_company_by_user(self, user_id: str) -> Dict[str, Any]:
        try:
            connection = await get_db_connection()
            async with connection as conn:
                user_data = await self.company_queries.get_user_with_memberships(conn, user_id)
                company = await self.company_queries.get_company_by_user_id_single(conn, user_id)
                
                if not company:
                    if user_data and user_data.get('company_memberships'):
                        membership_company_id = user_data['company_memberships'][0]['company_id']
                        company = await self.company_queries.get_company_by_id(conn, membership_company_id)
                    
                    if not company:
                        raise ValueError("Company not found")
                
                parsed_company = self._parse_json_fields(company)
                logger.info(f"Returning company with parsed JSON fields: {parsed_company.get('id')}")
                return parsed_company
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error fetching company: {error}")
            raise Exception("Internal server error")


    async def get_companies_by_user_id(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            connection = await get_db_connection()
            async with connection as conn:
                companies = await self.company_queries.get_companies_by_user_id_simple(conn, user_id)
                if not companies:
                    return []

                parsed_companies = []
                for company in companies:
                    parsed_company = self._parse_json_fields(company)
                    parsed_companies.append(parsed_company)
                
                return parsed_companies
                
        except Exception as error:
            logger.error(f"Error fetching companies: {error}")
            raise Exception("Internal server error")

    async def create_company(self, company_data: CompanyCreate, user_id: str) -> Dict[str, Any]:
        try:
            logger.info(f"Creating company for user_id: {user_id}")
            api_key = secrets.token_hex(32)
            
            connection = await get_db_connection()
            async with connection as conn:
                logger.info("Database connection established")
                company = await self.company_queries.create_company(conn, company_data, user_id, api_key)
                logger.info(f"Company created successfully: {company.get('id')}")

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
                    logger.warning(f'Failed to log company creation activity: {log_error}')

                parsed_company = self._parse_json_fields(company)
                logger.info("Company creation completed successfully")
                return parsed_company
                
        except Exception as error:
            logger.error(f"Error creating company: {error}", exc_info=True)

            error_str = str(error).lower()
            if "unique constraint" in error_str or "duplicate key" in error_str:
                raise ValueError("Email or phone number already exists")
            elif "invalid input" in error_str and "httpurl" in error_str:
                raise ValueError("Invalid website URL format")
            elif "violates not-null constraint" in error_str:
                raise ValueError("Required field is missing")
            else:
                raise error

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
                    
                    return self._parse_json_fields(company)
                    
        except Exception as error:
            logger.error(f"Error creating/updating company: {error}")
            if "unique constraint" in str(error).lower() or "duplicate key" in str(error).lower():
                raise ValueError("Email or phone number already exists")
            raise Exception("Internal server error")

    async def update_company(self, company_id: str, company_data: CompanyUpdate, user_id: str) -> Dict[str, Any]:
        try:
            connection = await get_db_connection()
            async with connection as conn:
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
                
                return self._parse_json_fields(updated_company)
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Error updating company: {error}")
            if "unique constraint" in str(error).lower() or "duplicate key" in str(error).lower():
                raise ValueError("Email or phone number already exists")
            raise Exception("Internal server error")

    async def delete_company(self, company_id: str, user_id: str) -> Dict[str, Any]:
        try:
            connection = await get_db_connection()
            async with connection as conn:
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
            connection = await get_db_connection()
            async with connection as conn:
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
