import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.models.schemas import (
    UserResponse, BookingConfirmationRequest, MeetingReminderRequest, 
    CancellationNoticeRequest, NotificationResponse
)
from middleware.auth_middleware import get_current_user
from handlers.company_handler import CompanyHandler
from handlers.email_handler import EmailHandler
from app.db.postgres_client import get_db_connection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["Notifications"])

async def _ensure_user_access(current_user: UserResponse, company_handler: CompanyHandler):
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    return company["id"]

@router.post("/email/confirmation", response_model=NotificationResponse)
async def send_booking_confirmation(
    request: BookingConfirmationRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    try:
        company_id = await _ensure_user_access(current_user, company_handler)

        notification_id = f"NOTIF-{uuid.uuid4().hex[:8].upper()}"

        template_data = {
            'customer_name': request.customer_name,
            'meeting_title': request.meeting_title,
            'meeting_date': request.meeting_date.isoformat() if hasattr(request.meeting_date, 'isoformat') else str(request.meeting_date),
            'meeting_duration_minutes': request.meeting_duration_minutes,
            'meeting_location': request.meeting_location or 'Virtual Meeting',
            'meeting_url': request.meeting_url,
            'host_name': request.host_name,
            'host_email': request.host_email,
            'booking_id': request.booking_id,
            'additional_notes': request.additional_notes,
            'company_name': request.company_name or 'Callsure AI',
            'customer_email': request.customer_email
        }
        
        email_response = await EmailHandler.send_template_email(
            to=request.customer_email,
            template_name='booking_confirmation',
            template_data=template_data,
            subject=f"Booking Confirmed - {request.meeting_title}"
        )
        
        if email_response.success:
            background_tasks.add_task(
                _log_notification,
                notification_id,
                company_id,
                current_user.id,
                'booking_confirmation',
                request.customer_email,
                request.booking_id
            )
            
            logger.info(f"Booking confirmation sent: {notification_id} to {request.customer_email}")
            
            return NotificationResponse(
                success=True,
                message="Booking confirmation sent successfully",
                notification_id=notification_id
            )
        else:
            raise HTTPException(500, f"Failed to send confirmation: {email_response.message}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending booking confirmation: {str(e)}")
        raise HTTPException(500, f"Failed to send booking confirmation: {str(e)}")

@router.post("/email/reminder", response_model=NotificationResponse)
async def send_meeting_reminder(
    request: MeetingReminderRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    try:
        company_id = await _ensure_user_access(current_user, company_handler)

        notification_id = f"NOTIF-{uuid.uuid4().hex[:8].upper()}"

        template_data = {
            'customer_name': request.customer_name,
            'meeting_title': request.meeting_title,
            'meeting_date': request.meeting_date.isoformat() if hasattr(request.meeting_date, 'isoformat') else str(request.meeting_date),
            'meeting_duration_minutes': request.meeting_duration_minutes,
            'meeting_location': request.meeting_location or 'Virtual Meeting',
            'meeting_url': request.meeting_url,
            'host_name': request.host_name,
            'booking_id': request.booking_id,
            'reminder_type': request.reminder_type,
            'time_until_meeting': request.time_until_meeting,
            'company_name': request.company_name or 'Callsure AI'
        }

        reminder_subjects = {
            '24h': f"Meeting Tomorrow - {request.meeting_title}",
            '1h': f"Meeting in 1 Hour - {request.meeting_title}",
            '15m': f"Meeting Starting Soon - {request.meeting_title}"
        }
        subject = reminder_subjects.get(request.reminder_type, f"Meeting Reminder - {request.meeting_title}")

        email_response = await EmailHandler.send_template_email(
            to=request.customer_email,
            template_name='meeting_reminder',
            template_data=template_data,
            subject=subject
        )
        
        if email_response.success:
            background_tasks.add_task(
                _log_notification,
                notification_id,
                company_id,
                current_user.id,
                'meeting_reminder',
                request.customer_email,
                request.booking_id,
                {'reminder_type': request.reminder_type}
            )
            
            logger.info(f"Meeting reminder sent: {notification_id} to {request.customer_email}")
            
            return NotificationResponse(
                success=True,
                message=f"Meeting reminder ({request.reminder_type}) sent successfully",
                notification_id=notification_id
            )
        else:
            raise HTTPException(500, f"Failed to send reminder: {email_response.message}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending meeting reminder: {str(e)}")
        raise HTTPException(500, f"Failed to send meeting reminder: {str(e)}")

@router.post("/email/cancellation", response_model=NotificationResponse)
async def send_cancellation_notice(
    request: CancellationNoticeRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    try:
        company_id = await _ensure_user_access(current_user, company_handler)

        notification_id = f"NOTIF-{uuid.uuid4().hex[:8].upper()}"

        template_data = {
            'customer_name': request.customer_name,
            'meeting_title': request.meeting_title,
            'original_meeting_date': request.original_meeting_date.isoformat() if hasattr(request.original_meeting_date, 'isoformat') else str(request.original_meeting_date),
            'cancelled_by': request.cancelled_by,
            'cancellation_reason': request.cancellation_reason,
            'host_name': request.host_name,
            'booking_id': request.booking_id,
            'reschedule_link': request.reschedule_link,
            'company_name': request.company_name or 'Callsure AI',
            'customer_email': request.customer_email
        }

        email_response = await EmailHandler.send_template_email(
            to=request.customer_email,
            template_name='cancellation_notice',
            template_data=template_data,
            subject=f"Meeting Cancelled - {request.meeting_title}"
        )
        
        if email_response.success:
            background_tasks.add_task(
                _log_notification,
                notification_id,
                company_id,
                current_user.id,
                'cancellation_notice',
                request.customer_email,
                request.booking_id,
                {'cancelled_by': request.cancelled_by, 'reason': request.cancellation_reason}
            )
            
            logger.info(f"Cancellation notice sent: {notification_id} to {request.customer_email}")
            
            return NotificationResponse(
                success=True,
                message="Cancellation notice sent successfully",
                notification_id=notification_id
            )
        else:
            raise HTTPException(500, f"Failed to send cancellation notice: {email_response.message}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending cancellation notice: {str(e)}")
        raise HTTPException(500, f"Failed to send cancellation notice: {str(e)}")

async def _log_notification(
    notification_id: str,
    company_id: str,
    user_id: str,
    notification_type: str,
    recipient_email: str,
    booking_id: str,
    metadata: dict = None
):
    try:
        async with (await get_db_connection()) as conn:
            await conn.execute("""
                INSERT INTO notification_logs 
                (id, company_id, user_id, notification_type, recipient_email, 
                 booking_id, metadata, sent_at, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, notification_id, company_id, user_id, notification_type, 
                 recipient_email, booking_id, metadata or {}, 
                 datetime.utcnow(), datetime.utcnow())
            
        logger.info(f"Notification logged: {notification_id}")
        
    except Exception as e:
        logger.error(f"Failed to log notification {notification_id}: {str(e)}")
