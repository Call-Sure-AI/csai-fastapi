from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.db.postgres_client import get_db_connection
from handlers.whatsapp_handler import WhatsAppHandler
from app.models.schemas import (
    WhatsAppOnboardRequest, 
    SendMessageRequest, 
    SendMessageResponse,
    WhatsAppTemplateMessage,
    WhatsAppMediaMessage,
    BulkMessageRequest,
    BulkMessageResponse,
    WhatsAppStatusResponse,
    WhatsAppWebhookPayload,
    MessageResponse,
    UserResponse  # Import the UserResponse type
)
from middleware.auth_middleware import get_current_user
import logging
import os
from utils.whatsapp_onboarding_helper import WhatsAppOnboardingHelper

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
handler = WhatsAppHandler()
onboarding_helper = WhatsAppOnboardingHelper()

@router.post("/onboard")
async def onboard_whatsapp(
    data: WhatsAppOnboardRequest,
    db: AsyncSession = Depends(get_db_connection),
    current_user: UserResponse = Depends(get_current_user)  # Type hint fixed
):
    """
    Onboard a WhatsApp Business Account
    
    - **business_id**: Unique identifier for the business
    - **status**: Either "FINISH" or "CANCEL"
    - **code**: Authorization code (required for FINISH status)
    - **waba_id**: WhatsApp Business Account ID
    - **phone_number_id**: WhatsApp Phone Number ID
    - **current_step**: Current step in onboarding process
    """
    try:
        # Fixed: Access attribute directly instead of using .get()
        logger.info(f"Onboarding request from user {current_user.id} for business {data.business_id}")
        result = await handler.onboard(db, data)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in onboard_whatsapp: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/start-onboarding")
async def start_onboarding(
    business_id: str = Query(..., description="Business ID for onboarding"),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Start a new WhatsApp onboarding session
    
    - **business_id**: Business ID to start onboarding for
    """
    try:
        logger.info(f"Starting onboarding session for user {current_user.id}, business {business_id}")
        
        session = onboarding_helper.create_onboarding_session(
            business_id, 
            current_user.id
        )
        
        return session
        
    except Exception as e:
        logger.error(f"Error starting onboarding session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start onboarding session")

@router.get("/troubleshooting")
async def get_troubleshooting_guide():
    """
    Get troubleshooting guide for onboarding issues
    """
    try:
        return onboarding_helper.get_troubleshooting_guide()
    except Exception as e:
        logger.error(f"Error getting troubleshooting guide: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get troubleshooting guide")

@router.get("/onboarding-status/{business_id}")
async def get_onboarding_status(
    business_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get detailed onboarding status with next steps
    
    - **business_id**: Business ID to check
    """
    try:
        logger.info(f"Getting onboarding status for user {current_user.id}, business {business_id}")
        
        # Get basic status
        status = await handler.get_business_status(db, business_id)
        
        if not status:
            # No record found, provide onboarding URL
            session = onboarding_helper.create_onboarding_session(business_id, current_user.id)
            return {
                "business_id": business_id,
                "status": "not_started",
                "onboarding_required": True,
                "next_steps": session
            }
        
        # Check if onboarding is complete
        if status.get("status") == "FINISH" and status.get("has_token"):
            return {
                "business_id": business_id,
                "status": "completed",
                "onboarding_required": False,
                "details": status
            }
        
        # Onboarding incomplete or failed
        session = onboarding_helper.create_onboarding_session(business_id, current_user.id)
        return {
            "business_id": business_id,
            "status": "incomplete",
            "onboarding_required": True,
            "current_details": status,
            "next_steps": session
        }
        
    except Exception as e:
        logger.error(f"Error getting onboarding status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get onboarding status")

@router.post("/send-message", response_model=SendMessageResponse)
async def send_message(
    payload: SendMessageRequest,
    db: AsyncSession = Depends(get_db_connection),
    current_user: UserResponse = Depends(get_current_user)  # Type hint fixed
):
    """
    Send a WhatsApp text message
    
    - **business_id**: Business ID for the WhatsApp account
    - **to**: Recipient phone number (with country code, e.g., +1234567890)
    - **message**: Text message content
    - **type**: Message type (default: "text")
    - **preview_url**: Enable URL previews (default: true)
    - **context**: Context for replying to messages (optional)
    """
    try:
        # Fixed: Access attribute directly instead of using .get()
        logger.info(f"Send message request from user {current_user.id} to {payload.to}")
        result = await handler.send_message_advanced(db, payload)
        
        if result.status == "failed":
            raise HTTPException(status_code=400, detail=result.error_message or "Failed to send message")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in send_message: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/send-template", response_model=SendMessageResponse)
async def send_template_message(
    payload: WhatsAppTemplateMessage,
    db: AsyncSession = Depends(get_db_connection),
    current_user: UserResponse = Depends(get_current_user)  # Type hint fixed
):
    """
    Send a WhatsApp template message
    
    - **business_id**: Business ID for the WhatsApp account
    - **to**: Recipient phone number
    - **template_name**: Name of the approved template
    - **language_code**: Language code (default: "en")
    - **components**: Template parameters (optional)
    """
    try:
        # Fixed: Access attribute directly instead of using .get()
        logger.info(f"Send template message request from user {current_user.id}")
        result = await handler.send_template_message(db, payload)
        
        if result.status == "failed":
            raise HTTPException(status_code=400, detail=result.error_message or "Failed to send template message")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in send_template_message: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/send-media", response_model=SendMessageResponse)
async def send_media_message(
    payload: WhatsAppMediaMessage,
    db: AsyncSession = Depends(get_db_connection),
    current_user: UserResponse = Depends(get_current_user)  # Type hint fixed
):
    """
    Send a WhatsApp media message (image, document, audio, video)
    
    - **business_id**: Business ID for the WhatsApp account
    - **to**: Recipient phone number
    - **media_type**: Type of media (image, document, audio, video)
    - **media_url**: URL to media file (either this or media_id required)
    - **media_id**: WhatsApp media ID (either this or media_url required)
    - **caption**: Caption for media (optional)
    - **filename**: Filename for documents (optional)
    """
    try:
        # Fixed: Access attribute directly instead of using .get()
        logger.info(f"Send media message request from user {current_user.id}")
        result = await handler.send_media_message(db, payload)
        
        if result.status == "failed":
            raise HTTPException(status_code=400, detail=result.error_message or "Failed to send media message")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in send_media_message: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/send-bulk", response_model=BulkMessageResponse)
async def send_bulk_messages(
    payload: BulkMessageRequest,
    db: AsyncSession = Depends(get_db_connection),
    current_user: UserResponse = Depends(get_current_user)  # Type hint fixed
):
    """
    Send bulk WhatsApp messages
    
    - **business_id**: Business ID for the WhatsApp account
    - **recipients**: List of recipient phone numbers (max 100)
    - **message**: Text message content
    - **type**: Message type (default: "text")
    """
    try:
        # Fixed: Access attribute directly instead of using .get()
        logger.info(f"Send bulk messages request from user {current_user.id} to {len(payload.recipients)} recipients")
        result = await handler.send_bulk_messages(db, payload)
        
        return result
        
    except Exception as e:
        logger.error(f"Unexpected error in send_bulk_messages: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/status/{business_id}")
async def get_whatsapp_status(
    business_id: str,
    db: AsyncSession = Depends(get_db_connection),
    current_user: UserResponse = Depends(get_current_user)  # Type hint fixed
):
    """
    Get WhatsApp onboarding status for a business
    
    - **business_id**: Business ID to check status for
    """
    try:
        # Fixed: Access attribute directly instead of using .get()
        logger.info(f"Status check request from user {current_user.id} for business {business_id}")
        result = await handler.get_business_status(db, business_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Business not found")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_whatsapp_status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/businesses")
async def list_whatsapp_businesses(
    db: AsyncSession = Depends(get_db_connection),
    current_user: UserResponse = Depends(get_current_user),  # Type hint fixed
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    List all WhatsApp businesses for the current user
    
    - **limit**: Maximum number of records to return (max 100)
    - **offset**: Number of records to skip
    """
    try:
        from sqlalchemy import text
        
        # Fixed: Access attribute directly instead of using .get()
        logger.info(f"List businesses request from user {current_user.id}")
        
        query = text("""
            SELECT business_id, waba_id, phone_number_id, status, current_step,
                   created_at, updated_at, (access_token IS NOT NULL) as has_token
            FROM whatsapp_clients
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        
        result = await db.execute(query, {"limit": limit, "offset": offset})
        rows = result.fetchall()
        
        businesses = []
        for row in rows:
            businesses.append({
                "business_id": row.business_id,
                "waba_id": row.waba_id,
                "phone_number_id": row.phone_number_id,
                "status": row.status,
                "current_step": row.current_step,
                "has_token": row.has_token,
                "created_at": row.created_at,
                "updated_at": row.updated_at
            })
        
        return {
            "businesses": businesses,
            "total": len(businesses),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in list_whatsapp_businesses: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/business/{business_id}")
async def delete_whatsapp_business(
    business_id: str,
    db: AsyncSession = Depends(get_db_connection),
    current_user: UserResponse = Depends(get_current_user)  # Type hint fixed
):
    """
    Delete a WhatsApp business configuration
    
    - **business_id**: Business ID to delete
    """
    try:
        from sqlalchemy import text
        
        # Fixed: Access attribute directly instead of using .get()
        logger.info(f"Delete business request from user {current_user.id} for business {business_id}")
        
        # Check if business exists
        check_query = text("SELECT business_id FROM whatsapp_clients WHERE business_id = :business_id")
        result = await db.execute(check_query, {"business_id": business_id})
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Business not found")
        
        # Delete the business
        delete_query = text("DELETE FROM whatsapp_clients WHERE business_id = :business_id")
        await db.execute(delete_query, {"business_id": business_id})
        await db.commit()
        
        return {"message": f"Business {business_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in delete_whatsapp_business: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

# Webhook endpoints
@router.get("/webhook")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge")
):
    """
    Verify WhatsApp webhook
    
    This endpoint is called by WhatsApp to verify the webhook URL.
    """
    try:
        logger.info(f"Webhook verification request: mode={hub_mode}, token={hub_verify_token}")
        
        # Validate the verification token
        expected_token = os.getenv('WHATSAPP_WEBHOOK_VERIFY_TOKEN', 'your_webhook_verify_token')
        
        if hub_mode == "subscribe" and hub_verify_token == expected_token:
            logger.info("Webhook verification successful")
            return PlainTextResponse(hub_challenge)
        else:
            logger.warning("Webhook verification failed - invalid token")
            raise HTTPException(status_code=403, detail="Forbidden")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in verify_webhook: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/webhook")
async def receive_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_connection)
):
    """
    Receive WhatsApp webhook notifications
    
    This endpoint receives incoming messages and status updates from WhatsApp.
    """
    try:
        body = await request.json()
        logger.info(f"Received webhook: {body}")
        
        # Process the webhook
        result = await handler.process_webhook_message(body)
        
        if result.get("status") == "received":
            logger.info(f"Processed incoming message: {result.get('message_id')}")
            
            # Here you can add your custom logic to handle incoming messages
            # For example:
            # - Save message to database
            # - Auto-reply logic
            # - Forward to other systems
            # - etc.
            
        elif result.get("status") == "error":
            logger.error(f"Error processing webhook: {result.get('error')}")
        
        # WhatsApp expects a 200 response
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Unexpected error in receive_webhook: {str(e)}")
        # Still return 200 to avoid WhatsApp retries
        return {"status": "error", "message": str(e)}

# Health check endpoint
@router.get("/health")
async def health_check():
    """
    Health check endpoint for WhatsApp service
    """
    try:
        # You can add more comprehensive health checks here
        # such as checking Facebook API connectivity, database connection, etc.
        
        return {
            "status": "healthy",
            "service": "whatsapp",
            "facebook_version": handler.facebook_version,
            "timestamp": "2025-01-01T00:00:00Z"  # You can use actual timestamp
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

# Configuration endpoints
@router.get("/config")
async def get_whatsapp_config(
    current_user: UserResponse = Depends(get_current_user)  # Type hint fixed
):
    """
    Get WhatsApp configuration for the current user
    """
    try:
        # Fixed: Access attribute directly instead of using .get()
        logger.info(f"Config request from user {current_user.id}")
        
        return {
            "facebook_app_id": handler.fb_app_id,
            "facebook_version": handler.facebook_version,
            "frontend_url": handler.frontend_url,
            "webhook_configured": bool(os.getenv('WHATSAPP_WEBHOOK_VERIFY_TOKEN')),
            "features": {
                "text_messages": True,
                "template_messages": True,
                "media_messages": True,
                "bulk_messages": True,
                "webhooks": True
            }
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in get_whatsapp_config: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/test-connection/{business_id}")
async def test_whatsapp_connection(
    business_id: str,
    db: AsyncSession = Depends(get_db_connection),
    current_user: UserResponse = Depends(get_current_user)  # Type hint fixed
):
    """
    Test WhatsApp connection for a business
    
    - **business_id**: Business ID to test connection for
    """
    try:
        # Fixed: Access attribute directly instead of using .get()
        logger.info(f"Test connection request from user {current_user.id} for business {business_id}")
        
        # Get business status
        status = await handler.get_business_status(db, business_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Business not found")
        
        if status.get("status") != "FINISH" or not status.get("has_token"):
            raise HTTPException(status_code=400, detail="Business not properly onboarded")
        
        # You can add actual API test here by calling WhatsApp Graph API
        # For now, we'll just return the status
        
        return {
            "status": "connected",
            "business_id": business_id,
            "waba_id": status.get("waba_id"),
            "phone_number_id": status.get("phone_number_id"),
            "last_updated": status.get("updated_at")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in test_whatsapp_connection: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")