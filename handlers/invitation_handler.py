import secrets
import os
import jwt
import bcrypt
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.db.postgres_client import get_db_connection
from app.db.queries.invitation_queries import InvitationQueries
from app.utils.activity_logger import ActivityLogger
from handlers.email_handler import EmailHandler, EmailRequest
from app.models.schemas import InvitationCreate, InvitationAccept, Invitation
import logging
import json

logger = logging.getLogger(__name__)

class InvitationHandler:
    def __init__(self):
        self.invitation_queries = InvitationQueries()
        self.activity_logger = ActivityLogger()
        self.email_handler = EmailHandler()

    async def generate_invitation(
        self, 
        invitation_data: InvitationCreate, 
        user_id: str
    ) -> Dict[str, Any]:
        try:
            connection = await get_db_connection()
            async with connection as conn:
                company = await self.invitation_queries.get_company_by_id(conn, invitation_data.company_id)
                
                if not company:
                    raise ValueError("Company not found")
                
                if company['user_id'] != user_id:
                    raise PermissionError("Not authorized to invite users to this company")
                
                token = secrets.token_hex(32)
                expires_at = datetime.now() + timedelta(days=7)
                
                existing_invitation = await self.invitation_queries.get_invitation_by_email_and_company(
                    conn, invitation_data.email, invitation_data.company_id
                )
                
                if existing_invitation:
                    invitation = await self.invitation_queries.update_invitation(
                        conn, existing_invitation['id'], token, 
                        invitation_data.role or existing_invitation['role'], 
                        expires_at
                    )
                else:
                    invitation = await self.invitation_queries.create_invitation(
                        conn, invitation_data, token, expires_at
                    )
                
                invitation_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/invite?token={token}"
                
                return {
                    "message": "Invitation created successfully",
                    "invitation_url": invitation_url,
                    "invitation": {
                        "id": invitation['id'],
                        "email": invitation['email'],
                        "expires_at": invitation['expires_at']
                    }
                }
                
        except (ValueError, PermissionError):
            raise
        except Exception as error:
            logger.error(f"Generate invitation error: {error}")
            raise Exception("Internal server error")

    async def validate_invitation(self, token: str) -> Dict[str, Any]:
        try:
            logger.info(f"Validating invitation with token {token}")
            
            if not token:
                raise ValueError("Token is required")
            
            connection = await get_db_connection()
            async with connection as conn:
                invitation = await self.invitation_queries.get_invitation_by_token(conn, token)
                
                if not invitation:
                    raise ValueError("Invitation not found")
                
                if datetime.now() > invitation['expires_at']:
                    raise ValueError("Invitation has expired")
                
                if invitation['status'] == 'accepted':
                    raise ValueError("Invitation has already been accepted")
                
                company_data = invitation['company']
                if isinstance(company_data, str):
                    try:
                        company = json.loads(company_data)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse company JSON: {company_data}")
                        company = {"id": None, "name": "Unknown", "business_name": "Unknown"}
                else:
                    company = company_data
                
                return {
                    "invitation": {
                        "email": invitation['email'],
                        "company": {
                            "id": company['id'],
                            "name": company['name'],
                            "business_name": company['business_name']
                        },
                        "role": invitation['role'],
                        "expires_at": invitation['expires_at']
                    }
                }
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Validate invitation error: {error}")
            raise Exception("Internal server error")

    async def accept_invitation(
        self, 
        token: str, 
        acceptance_data: InvitationAccept
    ) -> Dict[str, Any]:
        try:
            if not token:
                raise ValueError("Token is required")
            
            connection = await get_db_connection()
            async with connection as conn:
                invitation = await self.invitation_queries.get_invitation_by_token_with_company(
                    conn, token
                )
                
                if not invitation:
                    raise ValueError("Invitation not found")
                
                if datetime.now() > invitation['expires_at']:
                    raise ValueError("Invitation has expired")
                
                if invitation['status'] == 'accepted':
                    raise ValueError("Invitation has already been accepted")
                
                user = await self.invitation_queries.get_user_by_email(conn, invitation['email'])
                
                async with conn.transaction():
                    if not user:
                        if not acceptance_data.password:
                            raise ValueError("Password is required for new users")
                        
                        hashed_password = bcrypt.hashpw(
                            acceptance_data.password.encode('utf-8'), 
                            bcrypt.gensalt()
                        ).decode('utf-8')
                        
                        user = await self.invitation_queries.create_user_with_account(
                            conn, 
                            invitation['email'], 
                            acceptance_data.name or invitation['email'].split('@')[0],
                            hashed_password
                        )

                    await self.invitation_queries.create_company_membership(
                        conn, user['id'], invitation['company']['id'], invitation['role']
                    )

                    try:
                        await self.activity_logger.log({
                            'user_id': user['id'],
                            'action': 'joined_company',
                            'entity_type': 'company',
                            'entity_id': invitation['company']['id'],
                            'metadata': {
                                'role': invitation['role'],
                                'invitation_id': invitation['id'],
                                'company_name': invitation['company']['name']
                            }
                        })
                    except Exception as log_error:
                        logger.error(f'Failed to log activity: {log_error}')

                    await self.invitation_queries.accept_invitation(conn, invitation['id'])

                jwt_payload = {
                    'id': user['id'],
                    'email': user['email'],
                    'name': user['name']
                }
                
                jwt_token = jwt.encode(
                    jwt_payload,
                    os.getenv('JWT_SECRET', 'your-secret-key'),
                    algorithm='HS256'
                )
                
                return {
                    "message": "Invitation accepted successfully",
                    "token": jwt_token,
                    "user": {
                        "id": user['id'],
                        "email": user['email'],
                        "name": user['name'],
                        "image": user.get('image')
                    },
                    "company": invitation['company']
                }
                
        except ValueError:
            raise
        except Exception as error:
            logger.error(f"Accept invitation error: {error}", exc_info=True)
            raise Exception("Internal server error")

    async def list_invitations(self, company_id: str, user_id: str) -> Dict[str, Any]:
        try:
            logger.info(f"Listing invitations for company {company_id}")
            
            connection = await get_db_connection()
            async with connection as conn:
                company = await self.invitation_queries.get_company_by_id(conn, company_id)
                
                if not company:
                    raise ValueError("Company not found")
                
                if company['user_id'] != user_id:
                    raise PermissionError("Not authorized to view invitations for this company")
                
                invitations = await self.invitation_queries.get_pending_invitations(conn, company_id)
                
                mapped_invitations = [
                    {
                        "id": inv['id'],
                        "email": inv['email'],
                        "role": inv['role'],
                        "status": inv['status'],
                        "expires_at": inv['expires_at'],
                        "created_at": inv['created_at'],
                        "accepted_at": inv.get('accepted_at'),
                        "invitation_url": f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/invite?token={inv['token']}"
                    }
                    for inv in invitations
                ]
                
                return {"invitations": mapped_invitations}
                
        except (ValueError, PermissionError):
            raise
        except Exception as error:
            logger.error(f"List invitations error: {error}")
            raise Exception("Internal server error")

    async def list_accepted_invitations(self, company_id: str, user_id: str) -> Dict[str, Any]:
        try:
            logger.info(f"Listing accepted invitations for company {company_id}")
            
            connection = await get_db_connection()
            async with connection as conn:
                company = await self.invitation_queries.get_company_by_id(conn, company_id)
                
                if not company:
                    raise ValueError("Company not found")
                
                if company['user_id'] != user_id:
                    raise PermissionError("Not authorized to view invitations for this company")
                
                invitations = await self.invitation_queries.get_accepted_invitations(conn, company_id)
                
                mapped_invitations = [
                    {
                        "id": inv['id'],
                        "email": inv['email'],
                        "role": inv['role'],
                        "accepted_at": inv['accepted_at'],
                        "created_at": inv['created_at']
                    }
                    for inv in invitations
                ]
                
                return {"invitations": mapped_invitations}
                
        except (ValueError, PermissionError):
            raise
        except Exception as error:
            logger.error(f"List accepted invitations error: {error}")
            raise Exception("Internal server error")

    async def list_expired_invitations(self, company_id: str, user_id: str) -> Dict[str, Any]:
        try:
            connection = await get_db_connection()
            async with connection as conn:
                company = await self.invitation_queries.get_company_by_id(conn, company_id)
                
                if not company:
                    raise ValueError("Company not found")
                
                if company['user_id'] != user_id:
                    raise PermissionError("Not authorized to view invitations for this company")
                
                invitations = await self.invitation_queries.get_expired_invitations(conn, company_id)
                
                mapped_invitations = [
                    {
                        "id": inv['id'],
                        "email": inv['email'],
                        "role": inv['role'],
                        "expires_at": inv['expires_at'],
                        "created_at": inv['created_at']
                    }
                    for inv in invitations
                ]
                
                return {"invitations": mapped_invitations}
                
        except (ValueError, PermissionError):
            raise
        except Exception as error:
            logger.error(f"List expired invitations error: {error}")
            raise Exception("Internal server error")

    async def delete_invitation(self, invitation_id: str, user_id: str) -> Dict[str, str]:
        try:
            connection = await get_db_connection()
            async with connection as conn:
                invitation = await self.invitation_queries.get_invitation_with_company(
                    conn, invitation_id
                )
                
                if not invitation:
                    raise ValueError("Invitation not found")
                
                if invitation['company']['user_id'] != user_id:
                    raise PermissionError("Not authorized to delete this invitation")
                
                await self.invitation_queries.delete_invitation(conn, invitation_id)
                
                return {"message": "Invitation deleted successfully"}
                
        except (ValueError, PermissionError):
            raise
        except Exception as error:
            logger.error(f"Delete invitation error: {error}")
            raise Exception("Internal server error")

    async def send_invitation_email(self, invitation_id: str, user_id: str) -> Dict[str, str]:
        try:
            connection = await get_db_connection()
            async with connection as conn:
                invitation = await self.invitation_queries.get_invitation_with_company(
                    conn, invitation_id
                )
                
                if not invitation:
                    raise ValueError("Invitation not found")
                
                if invitation['company']['user_id'] != user_id:
                    raise PermissionError("Not authorized to send emails for this invitation")
                
                invitation_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/invite?token={invitation['token']}"
                
                logger.info(f"Sending invitation to {invitation['email']} for company {invitation['company']['name']}")
                logger.info(f"Invitation URL: {invitation_url}")
                
                # Create email HTML
                html_content = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background: linear-gradient(135deg, #162a47 0%, #3362A6 100%); padding: 30px; border-radius: 10px; text-align: center;">
                        <h1 style="color: white; margin: 0;">Callsure AI</h1>
                    </div>
                    
                    <div style="padding: 30px; background: #f9f9f9; border-radius: 0 0 10px 10px;">
                        <h1 style="color: #162a47; margin-bottom: 20px;">You've been invited to join {invitation['company']['name']}</h1>
                        <p style="color: #666; font-size: 16px; line-height: 1.5;">
                            You've been invited to join {invitation['company']['business_name']} as a {invitation['role']}.
                        </p>
                        <p style="color: #666; font-size: 16px; line-height: 1.5;">
                            Click the link below to accept the invitation:
                        </p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{invitation_url}" style="background: #3362A6; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                                Accept Invitation
                            </a>
                        </div>
                        
                        <p style="color: #666; font-size: 14px;">
                            This invitation will expire on {invitation['expires_at'].strftime('%B %d, %Y')}.
                        </p>
                    </div>
                </div>
                """
                
                # Send email
                email_request = EmailRequest(
                    to=invitation['email'],
                    subject=f"You've been invited to join {invitation['company']['name']}",
                    html=html_content
                )
                
                await self.email_handler.send_email(email_request)
                
                return {"message": "Invitation email sent successfully"}
                
        except (ValueError, PermissionError):
            raise
        except Exception as error:
            logger.error(f"Send invitation email error: {error}")
            raise Exception("Internal server error")
