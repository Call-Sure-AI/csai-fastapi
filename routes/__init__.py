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
from .campaigns import router as campaign_router
from .integrations import router as integration_router
from .bookings import router as booking_router
from .notifications import router as notification_router
from .leads import router as lead_router
from .script import router as script_router
from .voice import router as voice_router
from .users import router as user_router
from .analytics_realtime import router as analytics_realtime_router
from .agent_number import router as agent_number_router
from .agent_stats_realtime import router as agent_stats_realtime_router
from .phone_numbers import router as phone_numbers_router
from .company_metrics import router as company_metrics_router
from .call_reports import router as call_reports_router
from .sentiment_analysis import router as sentiment_router
from .urgency_detection import router as urgency_router

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
api_router.include_router(campaign_router, tags=["Campaign"])
api_router.include_router(integration_router, tags=["Integration"])
api_router.include_router(booking_router, tags=["Booking"])
api_router.include_router(notification_router, tags=["Notification"])
api_router.include_router(lead_router, tags=["Lead"])
api_router.include_router(script_router, tags=["Script"])
api_router.include_router(voice_router, tags=["Voice Clone"])
api_router.include_router(user_router, tags=["User Router"])
api_router.include_router(analytics_realtime_router, tags=["Analytics Realtime"]) 
api_router.include_router(agent_number_router, tags=["Agent Numbers"])
api_router.include_router(agent_stats_realtime_router, tags=["Agent Statistics"])
api_router.include_router(phone_numbers_router, prefix="/phone-numbers", tags=["Phone Numbers"])
api_router.include_router(company_metrics_router, prefix="/company-metrics", tags=["Company Metrics"])
api_router.include_router(call_reports_router, prefix="/call_reports", tags=["Call Reports"])
api_router.include_router(sentiment_router, prefix="/sentiment-analysis", tags=["Sentiment Analytics"])
api_router.include_router(urgency_router, prefix="/urgency-detection", tags=["Urgency Detection"])

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
v1_router.include_router(campaign_router, tags=["Campaign"])
v1_router.include_router(integration_router, tags=["Integration"])
v1_router.include_router(booking_router, tags=["Booking"])
v1_router.include_router(notification_router, tags=["Notification"])
v1_router.include_router(lead_router, tags=["Lead"])
v1_router.include_router(script_router, tags=["Script"])
v1_router.include_router(voice_router, tags=["Voice Clone"])
v1_router.include_router(user_router, tags=["User Router"])
v1_router.include_router(analytics_realtime_router, tags=["Analytics Realtime"])
v1_router.include_router(agent_number_router, tags=["Agent Numbers"])
v1_router.include_router(agent_stats_realtime_router, tags=["Agent Statistics"])
v1_router.include_router(phone_numbers_router, prefix="/phone-numbers", tags=["Phone Numbers"])
v1_router.include_router(company_metrics_router, prefix="/company-metrics", tags=["Company Metrics"])
v1_router.include_router(call_reports_router, prefix="/call_reports", tags=["Call Reports"])
v1_router.include_router(urgency_router, prefix="/urgency-detection", tags=["Urgency Detection"])

__all__ = ["api_router", "v1_router"]