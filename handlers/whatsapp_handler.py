import aiohttp
import os
import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.models.schemas import (
    WhatsAppOnboardRequest, 
    SendMessageRequest, 
    SendMessageResponse,
    WhatsAppMessageRequest,
    WhatsAppTemplateMessage,
    WhatsAppMediaMessage,
    BulkMessageRequest,
    BulkMessageResponse
)
from config import Config
from utils.whatsapp_onboarding_helper import WhatsAppOnboardingHelper


# Set up logging
logger = logging.getLogger(__name__)

class WhatsAppHandler:
    def __init__(self):
        self.fb_app_id = Config.FACEBOOK_APP_ID
        self.fb_app_secret = os.getenv('FACEBOOK_APP_SECRET')
        self.facebook_version = Config.FACEBOOK_VERSION
        self.frontend_url = Config.FRONTEND_URL
        self.onboarding_helper = WhatsAppOnboardingHelper()

        # Validate required configuration
        if not self.fb_app_id:
            raise ValueError("FACEBOOK_APP_ID is required but not found in configuration")
        if not self.fb_app_secret:
            raise ValueError("FACEBOOK_APP_SECRET is required but not found in environment variables")
        
    async def onboard(self, db: AsyncSession, payload: WhatsAppOnboardRequest) -> Dict[str, Any]:
        """Handle WhatsApp onboarding process"""
        try:
            logger.info(f"Starting onboarding process for business_id: {payload.business_id}")
            
            if payload.status == "CANCEL":
                await self.save_client(payload, db, access_token=None)
                logger.info(f"Onboarding cancelled for business_id: {payload.business_id}")
                return {"message": "Signup cancelled and saved", "status": "cancelled"}

            if payload.status == "FINISH":
                if not payload.code:
                    logger.error(f"Authorization code missing for business_id: {payload.business_id}")
                    return {
                        "error": "Authorization code missing",
                        "error_type": "missing_code",
                        "action_required": "Please restart the WhatsApp onboarding process"
                    }

                # Exchange code for token
                try:
                    access_token = await self.exchange_code_for_token(payload.code)
                    if not access_token:
                        logger.error(f"Failed to retrieve access token for business_id: {payload.business_id}")
                        return {
                            "error": "Failed to retrieve access token", 
                            "error_type": "token_exchange_failed",
                            "action_required": "Please restart the WhatsApp onboarding process"
                        }

                    await self.save_client(payload, db, access_token=access_token)
                    logger.info(f"Client onboarded successfully for business_id: {payload.business_id}")
                    return {"message": "Client onboarded successfully", "status": "completed"}
                    
                except FacebookAPIError as e:
                    logger.error(f"Facebook API error during onboarding for business_id: {payload.business_id}, error: {str(e)}")
                    return self.onboarding_helper.generate_onboarding_response(
                        payload.business_id, 
                        error_type="expired_code"
                    )
            
            # Handle unknown status
            logger.warning(f"Unknown status '{payload.status}' for business_id: {payload.business_id}")
            return {"error": f"Unknown status: {payload.status}"}
                
        except Exception as e:
            logger.error(f"Onboarding failed for business_id: {payload.business_id}, error: {str(e)}")
            return {"error": f"Onboarding failed: {str(e)}"}

    async def exchange_code_for_token(self, code: str) -> Optional[str]:
        """Exchange authorization code for access token"""
        try:
            redirect_uri = f"{self.frontend_url}/whatsapp/callback"
            
            token_url = (
                f"https://graph.facebook.com/{self.facebook_version}/oauth/access_token"
                f"?client_id={self.fb_app_id}"
                f"&client_secret={self.fb_app_secret}"
                f"&redirect_uri={redirect_uri}"
                f"&code={code}"
            )
            
            logger.info("Exchanging authorization code for access token")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(token_url) as resp:
                    response_text = await resp.text()
                    
                    if resp.status != 200:
                        logger.error(f"Token exchange failed with status {resp.status}: {response_text}")
                        
                        # Try to parse error response
                        try:
                            error_data = await resp.json() if resp.content_type == 'application/json' else {"error": {"message": response_text}}
                        except:
                            error_data = {"error": {"message": response_text}}
                        
                        raise FacebookAPIError.from_response(resp.status, error_data)
                    
                    try:
                        data = await resp.json()
                    except:
                        logger.error(f"Failed to parse JSON response: {response_text}")
                        raise Exception(f"Invalid response format: {response_text}")
                    
                    if 'error' in data:
                        logger.error(f"Facebook API error: {data}")
                        raise FacebookAPIError.from_response(resp.status, data)
                    
                    access_token = data.get("access_token")
                    if access_token:
                        logger.info("Successfully obtained access token")
                        
                        # Log token expiration info if available
                        expires_in = data.get("expires_in")
                        if expires_in:
                            logger.info(f"Access token expires in {expires_in} seconds")
                    else:
                        logger.error("Access token not found in response")
                    
                    return access_token
                    
        except FacebookAPIError:
            raise  # Re-raise Facebook API errors
        except Exception as e:
            logger.error(f"Error exchanging code for token: {str(e)}")
            raise

    async def save_client(self, payload: WhatsAppOnboardRequest, db: AsyncSession, access_token: Optional[str] = None) -> Optional[Any]:
        """Save or update WhatsApp client in database"""
        try:
            query = text("""
                INSERT INTO whatsapp_clients (
                    business_id, waba_id, phone_number_id, access_token, 
                    status, current_step, created_at, updated_at
                )
                VALUES (
                    :business_id, :waba_id, :phone_number_id, :access_token,
                    :status, :current_step, NOW(), NOW()
                )
                ON CONFLICT (business_id) DO UPDATE
                SET 
                    waba_id = EXCLUDED.waba_id,
                    phone_number_id = EXCLUDED.phone_number_id,
                    access_token = EXCLUDED.access_token,
                    status = EXCLUDED.status,
                    current_step = EXCLUDED.current_step,
                    updated_at = NOW()
                RETURNING id, business_id
            """)
            
            result = await db.execute(query, {
                "business_id": payload.business_id,
                "waba_id": payload.waba_id,
                "phone_number_id": payload.phone_number_id,
                "access_token": access_token,
                "status": payload.status,
                "current_step": payload.current_step,
            })
            
            await db.commit()
            saved_record = result.fetchone()
            
            if saved_record:
                logger.info(f"Successfully saved/updated client record for business_id: {payload.business_id}")
            else:
                logger.warning(f"No record returned after save for business_id: {payload.business_id}")
            
            return saved_record
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error saving client data for business_id: {payload.business_id}, error: {str(e)}")
            raise

    async def send_message(self, db: AsyncSession, business_id: str, to: str, message: str) -> SendMessageResponse:
        """Send WhatsApp message"""
        try:
            logger.info(f"Sending message to {to} for business_id: {business_id}")
            
            # Validate phone number format
            if not to.startswith('+'):
                logger.warning(f"Phone number {to} doesn't start with +, adding it")
                to = f"+{to}"
            
            # Fetch client credentials
            query = text("""
                SELECT phone_number_id, access_token 
                FROM whatsapp_clients
                WHERE business_id = :business_id 
                AND status = 'FINISH' 
                AND access_token IS NOT NULL
                LIMIT 1
            """)
            
            result = await db.execute(query, {"business_id": business_id})
            row = result.fetchone()
            
            if not row:
                logger.error(f"Business {business_id} not found, not onboarded, or missing access token")
                return SendMessageResponse(
                    message_id="",
                    status="failed",
                    to=to,
                    error_message="Business not onboarded or missing access token"
                )

            phone_number_id, access_token = row.phone_number_id, row.access_token
            
            # Send message via WhatsApp API
            url = f"https://graph.facebook.com/{self.facebook_version}/{phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            json_payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": message},
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=json_payload, headers=headers) as resp:
                    response_data = await resp.json()
                    
                    if resp.status != 200:
                        logger.error(f"WhatsApp API error {resp.status}: {response_data}")
                        
                        # Handle rate limiting
                        if resp.status == 429:
                            return SendMessageResponse(
                                message_id="",
                                status="rate_limited",
                                to=to,
                                error_message="Rate limit exceeded"
                            )
                        
                        # Handle authentication errors
                        if resp.status in [401, 403]:
                            return SendMessageResponse(
                                message_id="",
                                status="unauthorized",
                                to=to,
                                error_message="Authentication failed"
                            )
                        
                        return SendMessageResponse(
                            message_id="",
                            status="failed",
                            to=to,
                            error_message=str(response_data)
                        )
                    
                    # Extract message ID from response
                    messages = response_data.get("messages", [])
                    if messages:
                        message_id = messages[0].get("id", "unknown")
                        logger.info(f"Message sent successfully. ID: {message_id}")
                        
                        return SendMessageResponse(
                            message_id=message_id,
                            status="sent",
                            to=to
                        )
                    else:
                        logger.warning(f"No message ID in response: {response_data}")
                        return SendMessageResponse(
                            message_id="unknown",
                            status="sent",
                            to=to
                        )
                    
        except Exception as e:
            logger.error(f"Error sending message to {to} for business_id {business_id}: {str(e)}")
            return SendMessageResponse(
                message_id="",
                status="failed",
                to=to,
                error_message=str(e)
            )

    async def send_message_advanced(self, db: AsyncSession, request: SendMessageRequest) -> SendMessageResponse:
        """Send WhatsApp message using the SendMessageRequest schema"""
        return await self.send_message(db, request.business_id, request.to, request.message)

    async def send_template_message(self, db: AsyncSession, request: WhatsAppTemplateMessage) -> SendMessageResponse:
        """Send WhatsApp template message"""
        try:
            logger.info(f"Sending template message '{request.template_name}' to {request.to}")
            
            # Fetch client credentials
            query = text("""
                SELECT phone_number_id, access_token 
                FROM whatsapp_clients
                WHERE business_id = :business_id 
                AND status = 'FINISH' 
                AND access_token IS NOT NULL
                LIMIT 1
            """)
            
            result = await db.execute(query, {"business_id": request.business_id})
            row = result.fetchone()
            
            if not row:
                logger.error(f"Business {request.business_id} not found or not onboarded")
                return SendMessageResponse(
                    message_id="",
                    status="failed",
                    to=request.to,
                    error_message="Business not onboarded"
                )

            phone_number_id, access_token = row.phone_number_id, row.access_token
            
            # Build template message payload
            url = f"https://graph.facebook.com/{self.facebook_version}/{phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            json_payload = {
                "messaging_product": "whatsapp",
                "to": request.to,
                "type": "template",
                "template": {
                    "name": request.template_name,
                    "language": {"code": request.language_code}
                }
            }
            
            # Add components if provided
            if request.components:
                json_payload["template"]["components"] = request.components

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=json_payload, headers=headers) as resp:
                    response_data = await resp.json()
                    
                    if resp.status != 200:
                        logger.error(f"WhatsApp template API error {resp.status}: {response_data}")
                        return SendMessageResponse(
                            message_id="",
                            status="failed",
                            to=request.to,
                            error_message=str(response_data)
                        )
                    
                    messages = response_data.get("messages", [])
                    if messages:
                        message_id = messages[0].get("id", "unknown")
                        return SendMessageResponse(
                            message_id=message_id,
                            status="sent",
                            to=request.to
                        )
                    else:
                        return SendMessageResponse(
                            message_id="unknown",
                            status="sent",
                            to=request.to
                        )
                    
        except Exception as e:
            logger.error(f"Error sending template message: {str(e)}")
            return SendMessageResponse(
                message_id="",
                status="failed",
                to=request.to,
                error_message=str(e)
            )

    async def send_media_message(self, db: AsyncSession, request: WhatsAppMediaMessage) -> SendMessageResponse:
        """Send WhatsApp media message (image, document, audio, video)"""
        try:
            logger.info(f"Sending {request.media_type} message to {request.to}")
            
            # Fetch client credentials
            query = text("""
                SELECT phone_number_id, access_token 
                FROM whatsapp_clients
                WHERE business_id = :business_id 
                AND status = 'FINISH' 
                AND access_token IS NOT NULL
                LIMIT 1
            """)
            
            result = await db.execute(query, {"business_id": request.business_id})
            row = result.fetchone()
            
            if not row:
                return SendMessageResponse(
                    message_id="",
                    status="failed",
                    to=request.to,
                    error_message="Business not onboarded"
                )

            phone_number_id, access_token = row.phone_number_id, row.access_token
            
            # Build media message payload
            url = f"https://graph.facebook.com/{self.facebook_version}/{phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Build media object
            media_obj = {}
            if request.media_id:
                media_obj["id"] = request.media_id
            elif request.media_url:
                media_obj["link"] = request.media_url
            
            if request.caption and request.media_type in ["image", "video", "document"]:
                media_obj["caption"] = request.caption
            
            if request.filename and request.media_type == "document":
                media_obj["filename"] = request.filename
            
            json_payload = {
                "messaging_product": "whatsapp",
                "to": request.to,
                "type": request.media_type,
                request.media_type: media_obj
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=json_payload, headers=headers) as resp:
                    response_data = await resp.json()
                    
                    if resp.status != 200:
                        logger.error(f"WhatsApp media API error {resp.status}: {response_data}")
                        return SendMessageResponse(
                            message_id="",
                            status="failed",
                            to=request.to,
                            error_message=str(response_data)
                        )
                    
                    messages = response_data.get("messages", [])
                    if messages:
                        message_id = messages[0].get("id", "unknown")
                        return SendMessageResponse(
                            message_id=message_id,
                            status="sent",
                            to=request.to
                        )
                    else:
                        return SendMessageResponse(
                            message_id="unknown",
                            status="sent",
                            to=request.to
                        )
                    
        except Exception as e:
            logger.error(f"Error sending media message: {str(e)}")
            return SendMessageResponse(
                message_id="",
                status="failed",
                to=request.to,
                error_message=str(e)
            )

    async def send_bulk_messages(self, db: AsyncSession, request: BulkMessageRequest) -> BulkMessageResponse:
        """Send bulk WhatsApp messages"""
        results = []
        successful = 0
        failed = 0
        
        logger.info(f"Starting bulk message send to {len(request.recipients)} recipients")
        
        for recipient in request.recipients:
            try:
                result = await self.send_message(db, request.business_id, recipient, request.message)
                results.append(result)
                
                if result.status == "sent":
                    successful += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Error sending bulk message to {recipient}: {str(e)}")
                results.append(SendMessageResponse(
                    message_id="",
                    status="failed",
                    to=recipient,
                    error_message=str(e)
                ))
                failed += 1
        
        logger.info(f"Bulk message completed: {successful} successful, {failed} failed")
        
        return BulkMessageResponse(
            total_messages=len(request.recipients),
            successful=successful,
            failed=failed,
            results=results
        )

    async def get_business_status(self, db: AsyncSession, business_id: str) -> Optional[Dict[str, Any]]:
        """Get WhatsApp onboarding status for a business"""
        try:
            query = text("""
                SELECT business_id, waba_id, phone_number_id, status, current_step,
                       created_at, updated_at, (access_token IS NOT NULL) as has_token
                FROM whatsapp_clients
                WHERE business_id = :business_id
                LIMIT 1
            """)
            
            result = await db.execute(query, {"business_id": business_id})
            row = result.fetchone()
            
            if not row:
                return None
                
            return {
                "business_id": row.business_id,
                "waba_id": row.waba_id,
                "phone_number_id": row.phone_number_id,
                "status": row.status,
                "current_step": row.current_step,
                "has_token": row.has_token,
                "created_at": row.created_at,
                "updated_at": row.updated_at
            }
            
        except Exception as e:
            logger.error(f"Error getting business status for {business_id}: {str(e)}")
            return None

    async def validate_webhook(self, verify_token: str, hub_verify_token: str) -> bool:
        """Validate WhatsApp webhook verification"""
        expected_token = os.getenv('WHATSAPP_WEBHOOK_VERIFY_TOKEN', 'your_webhook_verify_token')
        return verify_token == expected_token

    async def process_webhook_message(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming WhatsApp webhook message"""
        try:
            # Extract message data from webhook
            entry = webhook_data.get('entry', [])
            if not entry:
                return {"status": "no_entry"}
            
            changes = entry[0].get('changes', [])
            if not changes:
                return {"status": "no_changes"}
            
            value = changes[0].get('value', {})
            messages = value.get('messages', [])
            
            if not messages:
                return {"status": "no_messages"}
            
            message = messages[0]
            
            return {
                "status": "received",
                "message_id": message.get('id'),
                "from": message.get('from'),
                "timestamp": message.get('timestamp'),
                "type": message.get('type'),
                "text": message.get('text', {}).get('body') if message.get('type') == 'text' else None
            }
            
        except Exception as e:
            logger.error(f"Error processing webhook message: {str(e)}")
            return {"status": "error", "error": str(e)}


class FacebookAPIError(Exception):
    """Custom exception for Facebook API errors"""
    
    def __init__(self, message: str, error_type: str = None, error_code: int = None, error_subcode: int = None):
        self.message = message
        self.error_type = error_type
        self.error_code = error_code
        self.error_subcode = error_subcode
        super().__init__(self.message)
    
    @classmethod
    def from_response(cls, status_code: int, response_data: dict):
        """Create FacebookAPIError from API response"""
        error_info = response_data.get('error', {})
        message = error_info.get('message', 'Unknown Facebook API error')
        error_type = error_info.get('type', 'UnknownError')
        error_code = error_info.get('code', status_code)
        error_subcode = error_info.get('error_subcode')
        
        return cls(message, error_type, error_code, error_subcode)
    
    def get_user_action(self) -> str:
        """Get user-friendly action based on error type"""
        if self.error_subcode == 36007:  # Expired authorization code
            return "The authorization code has expired. Please restart the WhatsApp onboarding process from the beginning."
        elif self.error_code == 100:  # OAuth errors
            return "There was an authentication error. Please try the onboarding process again."
        elif self.error_code == 190:  # Invalid access token
            return "Your access token is invalid. Please complete the onboarding process again."
        else:
            return "Please try the onboarding process again. If the problem persists, contact support."