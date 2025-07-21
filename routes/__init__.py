from fastapi import APIRouter
from .auth import router as auth_router
from .agent import router as agent_router
from .company import router as company_router
from .health_check import router as health_router
from .email import router as email_router
from .s3 import router as s3_router
from .invitation import router as invitation_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(agent_router)
api_router.include_router(company_router)
api_router.include_router(health_router)
api_router.include_router(email_router)
api_router.include_router(invitation_router)
api_router.include_router(s3_router)
