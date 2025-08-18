from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import Optional
from app.models.schemas import (
    UserResponse, CalendarConnectRequest, CalendarConnectResponse,
    CalendarAvailabilityResponse, CalendarTestRequest, CalendarTestResponse,
    ConflictCheckRequest, ConflictCheckResponse, BlockTimeRequest, BlockTimeResponse,
    CreateEventRequest, CreateEventResponse, RescheduleEventRequest, RescheduleEventResponse,
    CancelEventRequest, CancelEventResponse, SyncCalendarRequest, SyncCalendarResponse,
    SyncStatusResponse
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

@router.post("/check-conflicts", response_model=ConflictCheckResponse)
async def check_calendar_conflicts(
    request: ConflictCheckRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    svc = CalendarService()
    result = await svc.check_conflicts(
        company_id=company_id,
        calendar_id=request.calendar_id,
        start_time=request.start_time,
        end_time=request.end_time
    )
    
    return result

@router.post("/block-time", response_model=BlockTimeResponse)
async def block_calendar_time(
    request: BlockTimeRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    svc = CalendarService()
    result = await svc.block_time(
        company_id=company_id,
        user_id=current_user.id,
        request=request
    )
    
    return result

@router.post("/create-event", response_model=CreateEventResponse)
async def create_calendar_event(
    request: CreateEventRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    svc = CalendarService()
    result = await svc.create_event(
        company_id=company_id,
        user_id=current_user.id,
        request=request
    )
    
    return result

@router.put("/reschedule", response_model=RescheduleEventResponse)
async def reschedule_meeting(
    request: RescheduleEventRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    svc = CalendarService()
    result = await svc.reschedule_event(
        company_id=company_id,
        user_id=current_user.id,
        request=request
    )
    
    return result

@router.delete("/cancel", response_model=CancelEventResponse)
async def cancel_calendar_event(
    request: CancelEventRequest,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    svc = CalendarService()
    result = await svc.cancel_event(
        company_id=company_id,
        user_id=current_user.id,
        request=request
    )
    
    return result

@router.post("/sync/google", response_model=SyncCalendarResponse)
async def sync_google_calendar(
    request: SyncCalendarRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    svc = CalendarService()
    
    if request.full_sync:
        background_tasks.add_task(
            svc.full_sync_google_calendar, 
            company_id, 
            current_user.id, 
            request.date_range_days
        )
        
        return SyncCalendarResponse(
            success=True,
            calendar_type="google",
            events_synced=0,
            last_sync=datetime.utcnow(),
            message="Full sync initiated in background"
        )
    else:
        result = await svc.sync_google_calendar(
            company_id=company_id,
            user_id=current_user.id,
            request=request
        )
        return result

@router.post("/sync/outlook", response_model=SyncCalendarResponse)
async def sync_outlook_calendar(
    request: SyncCalendarRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    svc = CalendarService()
    
    if request.full_sync:
        background_tasks.add_task(
            svc.full_sync_outlook_calendar,
            company_id,
            current_user.id,
            request.date_range_days
        )
        
        return SyncCalendarResponse(
            success=True,
            calendar_type="outlook",
            events_synced=0,
            last_sync=datetime.utcnow(),
            message="Full sync initiated in background"
        )
    else:
        result = await svc.sync_outlook_calendar(
            company_id=company_id,
            user_id=current_user.id,
            request=request
        )
        return result

@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_calendar_sync_status(
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    svc = CalendarService()
    result = await svc.get_sync_status(company_id)
    
    return result