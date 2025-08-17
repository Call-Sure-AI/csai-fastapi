from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
from datetime import datetime
import io

from app.models.schemas import (
    UserResponse, BookingCreate, BookingUpdate, BookingResponse,
    BookingStatusUpdate, BookingBulkUpdate, BookingFilter
)
from middleware.auth_middleware import get_current_user
from handlers.company_handler import CompanyHandler
from app.services.booking_service import BookingService

router = APIRouter(prefix="/bookings", tags=["Bookings"])

async def _ensure_user_access(current_user: UserResponse, company_handler: CompanyHandler):
    company = await company_handler.get_company_by_user(current_user.id)
    if not company:
        raise HTTPException(400, "User has no company")
    return company["id"]

@router.get("", response_model=List[BookingResponse])
async def list_bookings(
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    customer: Optional[str] = Query(None, description="Filter by customer name"),
    status: Optional[str] = Query(None, description="Filter by booking status"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=1000, description="Pagination limit"),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    filters = BookingFilter(
        campaign_id=campaign_id,
        customer=customer,
        status=status,
        start_date=start_date,
        end_date=end_date
    )
    
    try:
        service = BookingService()
        bookings = await service.list_bookings(company_id, filters, offset, limit)
        return bookings
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.post("", status_code=201, response_model=BookingResponse)
async def create_booking(
    booking: BookingCreate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    try:
        service = BookingService()
        result = await service.create_booking(company_id, booking, current_user.id)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.get("/export")
async def export_bookings(
    campaign_id: Optional[str] = Query(None, description="Filter by campaign ID"),
    status: Optional[str] = Query(None, description="Filter by booking status"),
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    filters = BookingFilter(campaign_id=campaign_id, status=status)
    
    try:
        service = BookingService()
        csv_content = await service.export_bookings(company_id, filters)
        
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=bookings_export.csv"}
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = BookingService()
    booking = await service.get_booking(booking_id, company_id)
    
    if not booking:
        raise HTTPException(404, "Booking not found")
    
    return booking

@router.put("/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: str,
    updates: BookingUpdate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    try:
        service = BookingService()
        updated = await service.update_booking(booking_id, company_id, updates)
        
        if not updated:
            raise HTTPException(404, "Booking not found")
        
        return updated
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.delete("/{booking_id}", status_code=204)
async def cancel_booking(
    booking_id: str,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    service = BookingService()
    deleted = await service.delete_booking(booking_id, company_id)
    
    if not deleted:
        raise HTTPException(404, "Booking not found")

@router.patch("/{booking_id}/status", response_model=BookingResponse)
async def update_booking_status(
    booking_id: str,
    status_update: BookingStatusUpdate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    try:
        service = BookingService()
        updated = await service.update_booking_status(
            booking_id, company_id, status_update.status
        )
        
        if not updated:
            raise HTTPException(404, "Booking not found")
        
        return updated
    except ValueError as e:
        raise HTTPException(400, str(e))

@router.post("/bulk-update")
async def bulk_update_bookings(
    bulk_update: BookingBulkUpdate,
    current_user: UserResponse = Depends(get_current_user),
    company_handler: CompanyHandler = Depends(CompanyHandler),
):
    company_id = await _ensure_user_access(current_user, company_handler)
    
    try:
        service = BookingService()
        updated_count = await service.bulk_update_bookings(company_id, bulk_update)
        
        return {"message": f"Successfully updated {updated_count} booking(s)"}
    except ValueError as e:
        raise HTTPException(400, str(e))