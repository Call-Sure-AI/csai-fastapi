from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from app.models.schemas import (
    UserResponse, CalendarConnectRequest, CalendarConnectResponse,
    CalendarAvailabilityResponse, CalendarTestRequest, CalendarTestResponse
)
from middleware.auth_middleware import get_current_user
from handlers.company_handler import CompanyHandler
from app.services.calendar_service import CalendarService

router = APIRouter(prefix="/integrations/calendar", tags=["Calendar Integrations"])

async def _ensure_user_access(current_user: UserResponse, company_handler: CompanyHandler):
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    return company["id"]

@router.post("/connect", response_model=CalendarConnectResponse)
async def connect_calendar(
    request: CalendarConnectRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    svc = CalendarService()
    result = await svc.connect_calendar(company_id, current_user.id, request)
    
    return result

@router.get("/availability", response_model=CalendarAvailabilityResponse)
async def get_calendar_availability(
    calendar_id: Optional[str] = Query(None, description="Calendar ID (uses primary if not specified)"),
    start_date: Optional[str] = Query(None, description="Start date in ISO 8601 format"),
    end_date: Optional[str] = Query(None, description="End date in ISO 8601 format"),
    duration_minutes: int = Query(30, ge=15, le=120, description="Meeting duration in minutes"),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    svc = CalendarService()
    result = await svc.get_availability(
        company_id, calendar_id, start_date, end_date, duration_minutes
    )
    
    return result

@router.post("/test", response_model=CalendarTestResponse)
async def test_calendar_connection(
    request: CalendarTestRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    svc = CalendarService()
    result = await svc.test_connection(company_id, request.calendar_id, current_user.id)
    
    return result
