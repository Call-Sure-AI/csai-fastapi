from fastapi import APIRouter
from .auth import router as auth_router
from .agent import router as agent_router
from .company import router as company_router
from .health_check import router as health_router
from .email import router as email_router
from .s3 import router as s3_router
from .invitation import router as invitation_router

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

# You can also create versioned API routers
v1_router = APIRouter()
v1_router.include_router(auth_router, tags=["Authentication"])
v1_router.include_router(agent_router, tags=["Agents"])
v1_router.include_router(company_router, tags=["Companies"])
v1_router.include_router(health_router, tags=["Health"])
v1_router.include_router(email_router, tags=["Email"])
v1_router.include_router(invitation_router, tags=["Invitations"])
v1_router.include_router(s3_router, tags=["File Storage"])

# Export both for flexibility
__all__ = ["api_router", "v1_router"]