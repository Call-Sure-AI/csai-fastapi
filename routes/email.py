from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from handlers.email_handler import EmailHandler, EmailRequest, EmailResponse
from app.models.schemas import BulkEmailRequest, TemplateEmailRequest, OTPEmailRequest, UserResponse, VerificationEmailRequest
from middleware.auth_middleware import get_current_user
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/email", tags=["email"])
email_handler = EmailHandler()

class QueuedEmailResponse(BaseModel):
    status: str = "queued"
    message: str = "Email has been queued for delivery"
    queued_at: datetime = None
    
    def __init__(self, **data):
        if 'queued_at' not in data:
            data['queued_at'] = datetime.utcnow()
        super().__init__(**data)

async def send_email_background(email_request: dict, user_id: str):
    """Background task to send email"""
    try:
        handler = EmailHandler()
        await handler.send_email(EmailRequest(**email_request))
        logger.info(f"Email sent successfully to {email_request['to']} by user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send email in background: {e}")

async def send_otp_background(email: str, code: str):
    """Background task to send OTP"""
    try:
        handler = EmailHandler()
        await handler.send_otp_email(email, code)
        logger.info(f"OTP email sent successfully to {email}")
    except Exception as e:
        logger.error(f"Failed to send OTP email in background: {e}")

async def send_bulk_background(recipients: List[str], subject: str, html: str, batch_size: int = 50):
    """Background task to send bulk emails in batches"""
    try:
        handler = EmailHandler()
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            await handler.send_bulk_emails(batch, subject, html)
            logger.info(f"Sent batch of {len(batch)} emails")
    except Exception as e:
        logger.error(f"Failed to send bulk emails in background: {e}")

async def send_template_background(to: str, template_name: str, template_data: dict, subject: Optional[str] = None):
    """Background task to send template email"""
    try:
        handler = EmailHandler()
        await handler.send_template_email(to, template_name, template_data, subject)
        logger.info(f"Template email '{template_name}' sent to {to}")
    except Exception as e:
        logger.error(f"Failed to send template email in background: {e}")

@router.post("/send", response_model=QueuedEmailResponse)
async def send_email(
    email_request: EmailRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user)
):

    try:
        if not email_request.to or not email_request.subject:
            raise HTTPException(status_code=400, detail="Missing required fields")

        background_tasks.add_task(
            send_email_background,
            email_request.dict(),
            current_user.id
        )
        
        return QueuedEmailResponse(
            message=f"Email to {email_request.to} has been queued for delivery"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queuing email: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue email")

@router.post("/send-otp", response_model=QueuedEmailResponse)
async def send_otp_email(
    otp_request: OTPEmailRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user)
):
    """Send OTP email asynchronously"""
    try:
        background_tasks.add_task(
            send_otp_background,
            otp_request.email,
            otp_request.code
        )
        
        return QueuedEmailResponse(
            message=f"OTP email to {otp_request.email} has been queued"
        )
    except Exception as e:
        logger.error(f"Error queuing OTP email: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue OTP email")

@router.post("/send-bulk", response_model=QueuedEmailResponse)
async def send_bulk_emails(
    bulk_request: BulkEmailRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user)
):
    """Send bulk emails asynchronously in batches"""
    try:
        # Validate recipients
        if not bulk_request.recipients:
            raise HTTPException(status_code=400, detail="No recipients provided")
        
        if len(bulk_request.recipients) > 1000:
            raise HTTPException(status_code=400, detail="Maximum 1000 recipients allowed per request")
        
        background_tasks.add_task(
            send_bulk_background,
            bulk_request.recipients,
            bulk_request.subject,
            bulk_request.html
        )
        
        return QueuedEmailResponse(
            message=f"Bulk email to {len(bulk_request.recipients)} recipients has been queued"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queuing bulk emails: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue bulk emails")

@router.post("/send-template", response_model=QueuedEmailResponse)
async def send_template_email(
    template_request: TemplateEmailRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user)
):
    """Send template email asynchronously"""
    try:
        background_tasks.add_task(
            send_template_background,
            template_request.to,
            template_request.template_name,
            template_request.template_data,
            template_request.subject
        )
        
        return QueuedEmailResponse(
            message=f"Template email '{template_request.template_name}' to {template_request.to} has been queued"
        )
    except Exception as e:
        logger.error(f"Error queuing template email: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue template email")

@router.post("/send-welcome", response_model=QueuedEmailResponse)
async def send_welcome_email(
    to: EmailStr,
    name: str,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user)
):
    """Send welcome email asynchronously"""
    try:
        background_tasks.add_task(
            send_template_background,
            to,
            "welcome",
            {"name": name}
        )
        
        return QueuedEmailResponse(
            message=f"Welcome email to {to} has been queued"
        )
    except Exception as e:
        logger.error(f"Error queuing welcome email: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue welcome email")

@router.post("/send-password-reset", response_model=QueuedEmailResponse)
async def send_password_reset_email(
    to: EmailStr,
    reset_link: str,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user)
):
    """Send password reset email asynchronously"""
    try:
        background_tasks.add_task(
            send_template_background,
            to,
            "password_reset",
            {"reset_link": reset_link}
        )
        
        return QueuedEmailResponse(
            message=f"Password reset email to {to} has been queued"
        )
    except Exception as e:
        logger.error(f"Error queuing password reset email: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue password reset email")

@router.post("/send-verification", response_model=QueuedEmailResponse)
async def send_verification_email(
    to: EmailStr,
    verification_link: str,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user)
):
    """Send verification email asynchronously"""
    try:
        background_tasks.add_task(
            send_template_background,
            to,
            "verification",
            {"verification_link": verification_link}
        )
        
        return QueuedEmailResponse(
            message=f"Verification email to {to} has been queued"
        )
    except Exception as e:
        logger.error(f"Error queuing verification email: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue verification email")

# Optional: Add synchronous versions for critical emails that need immediate confirmation
@router.post("/send-sync", response_model=EmailResponse)
async def send_email_sync(
    email_request: EmailRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    """Send email synchronously - waits for completion (use for critical emails only)"""
    try:
        handler = EmailHandler()
        result = await handler.send_email(email_request)
        return result
    except Exception as e:
        logger.error(f"Error in sync email send: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")

# Optional: Add email status tracking
@router.get("/status/{email_id}")
async def get_email_status(
    email_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get status of a queued email (requires implementing email tracking in database)"""
    # This would require tracking emails in a database
    # For now, return a placeholder
    return {
        "email_id": email_id,
        "status": "queued",
        "message": "Email status tracking not yet implemented"
    }