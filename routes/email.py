from fastapi import APIRouter, HTTPException, Depends
from handlers.email_handler import EmailHandler, EmailRequest, EmailResponse
from app.models.schemas import BulkEmailRequest, TemplateEmailRequest, OTPEmailRequest, UserResponse, VerificationEmailRequest
from middleware.auth_middleware import get_current_user
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/email", tags=["email"])
email_handler = EmailHandler()

@router.post("/send", response_model=EmailResponse)
async def send_email(
    email_request: EmailRequest,
    current_user: UserResponse = Depends(get_current_user),
    email_handler: EmailHandler = Depends(EmailHandler)
):
    try:
        user_id = current_user.id
        result = await email_handler.send_email(email_request)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_email: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/send-otp", response_model=EmailResponse)
async def send_otp_email(
    otp_request: OTPEmailRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        result = await email_handler.send_otp_email(otp_request.email, otp_request.code)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_otp_email: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/send-bulk", response_model=EmailResponse)
async def send_bulk_emails(
    bulk_request: BulkEmailRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        result = await email_handler.send_bulk_emails(
            recipients=bulk_request.recipients,
            subject=bulk_request.subject,
            html=bulk_request.html
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_bulk_emails: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/send-template", response_model=EmailResponse)
async def send_template_email(
    template_request: TemplateEmailRequest,
    current_user: UserResponse = Depends(get_current_user),
    email_handler: EmailHandler = Depends(EmailHandler)
):
    try:
        user_id = current_user.id
        result = await email_handler.send_template_email(
            to=template_request.to,
            template_name=template_request.template_name,
            template_data=template_request.template_data,
            subject=template_request.subject
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_template_email: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/send-welcome", response_model=EmailResponse)
async def send_welcome_email(
    to: EmailStr,
    name: str,
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        result = await email_handler.send_template_email(
            to=to,
            template_name="welcome",
            template_data={"name": name}
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_welcome_email: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/send-password-reset", response_model=EmailResponse)
async def send_password_reset_email(
    to: EmailStr,
    reset_link: str,
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        result = await email_handler.send_template_email(
            to=to,
            template_name="password_reset",
            template_data={"reset_link": reset_link}
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_password_reset_email: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/send-verification", response_model=EmailResponse)
async def send_verification_email(
    to: EmailStr,
    verification_link: str,
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        result = await email_handler.send_template_email(
            to=to,
            template_name="verification",
            template_data={"verification_link": verification_link}
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_verification_email: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
