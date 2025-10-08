from fastapi import APIRouter
from .auth import router as auth_router
from .agent import router as agent_router
from .company import router as company_router
from .health_check import router as health_router
from .email import router as email_router
from .s3 import router as s3_router
from .invitation import router as invitation_router
from .whatsapp import router as whatsapp_router
from .activity import router as activity_router
from .ticket import router as ticket_router
from .analytics import router as analytics_router
from .conversation import router as conversation_router
from .campaigns import router as campaign_router
from .integrations import router as integration_router
from .bookings import router as booking_router
from .notifications import router as notification_router
from .leads import router as lead_router
from .script import router as script_router
from .voice import router as voice_router
from .websocket import router as websocket_router

# Create the main API router
api_router = APIRouter()

# Include all routers with their prefixes
# Note: Each router already has its own prefix defined, so we don't add extra prefixes here
api_router.include_router(auth_router, tags=["Authentication"])
api_router.include_router(agent_router, tags=["Agents"])
api_router.include_router(company_router, tags=["Companies"])
api_router.include_router(health_router, tags=["Health"])
api_router.include_router(email_router, tags=["Email"])
api_router.include_router(invitation_router, tags=["Invitations"])
api_router.include_router(s3_router, tags=["File Storage"])
api_router.include_router(whatsapp_router, tags=["WhatsApp"])
api_router.include_router(activity_router, tags=["Activities"])
api_router.include_router(ticket_router, tags=["Tickets"])
api_router.include_router(analytics_router, tags=["Analytics"])
api_router.include_router(conversation_router, tags=["Conversation"])
api_router.include_router(campaign_router, tags=["Campaign"])
api_router.include_router(integration_router, tags=["Integration"])
api_router.include_router(booking_router, tags=["Booking"])
api_router.include_router(notification_router, tags=["Notification"])
api_router.include_router(lead_router, tags=["Lead"])
api_router.include_router(script_router, tags=["Script"])
api_router.include_router(voice_router, tags=["Voice Clone"])
api_router.include_router(websocket_router, tags=["Websocket Router"])

# You can also create versioned API routers
v1_router = APIRouter()
v1_router.include_router(auth_router, tags=["Authentication"])
v1_router.include_router(agent_router, tags=["Agents"])
v1_router.include_router(company_router, tags=["Companies"])
v1_router.include_router(health_router, tags=["Health"])
v1_router.include_router(email_router, tags=["Email"])
v1_router.include_router(invitation_router, tags=["Invitations"])
v1_router.include_router(s3_router, tags=["File Storage"])
v1_router.include_router(whatsapp_router, tags=["WhatsApp"])
v1_router.include_router(activity_router, tags=["Activities"])
v1_router.include_router(ticket_router, tags=["Tickets"])
v1_router.include_router(analytics_router, tags=["Analytics"])
v1_router.include_router(conversation_router, tags=["Conversation"])
v1_router.include_router(campaign_router, tags=["Campaign"])
v1_router.include_router(integration_router, tags=["Integration"])
v1_router.include_router(booking_router, tags=["Booking"])
v1_router.include_router(notification_router, tags=["Notification"])
v1_router.include_router(lead_router, tags=["Lead"])
v1_router.include_router(script_router, tags=["Script"])
v1_router.include_router(voice_router, tags=["Voice Clone"])
v1_router.include_router(websocket_router, tags=["Websocket Router"])

__all__ = ["api_router", "v1_router"]