from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from app.db.postgres_client import get_db_connection
from app.models.schemas import UserResponse
from middleware.auth_middleware import get_current_user
from app.services.ticket_service import AutoTicketService
from pydantic import BaseModel

router = APIRouter(prefix="/tickets", tags=["Tickets"])

class TicketUpdateRequest(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None
    note: Optional[str] = None

class TicketNoteRequest(BaseModel):
    content: str
    is_internal: bool = True

@router.post("/companies/{company_id}/create")
async def create_ticket(
    company_id: str,
    ticket_data: Dict[str, Any] = Body(...),
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    async with db_context as db:
        ticket_service = AutoTicketService(db)
        if ticket_data.get("company_id") != company_id:
            raise HTTPException(
                status_code=400, 
                detail="Company ID mismatch between URL and ticket data"
            )
        
        try:
            created_ticket = await ticket_service.create_ticket(ticket_data)
            return {
                "message": "Ticket created successfully",
                "ticket": created_ticket
            }
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create ticket: {str(e)}"
            )

@router.post("/companies/{company_id}/auto-create-from-conversation/{conversation_id}")
async def auto_create_ticket_from_conversation(
    company_id: str,
    conversation_id: str,
    latest_messages: List[Dict[str, Any]] = Body(...),
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    """Analyze conversation and auto-create ticket if support issue detected"""
    async with db_context as db:
        ticket_service = AutoTicketService(db)
        ticket_data = await ticket_service.analyze_conversation_for_tickets(
            conversation_id, latest_messages
        )
        
        if not ticket_data:
            return {
                "ticket_created": False,
                "reason": "No support issues detected in conversation"
            }

        try:
            created_ticket = await ticket_service.create_ticket(ticket_data)
            return {
                "ticket_created": True,
                "ticket": created_ticket,
                "message": f"Auto-created ticket {created_ticket['id']} from conversation analysis"
            }
        except Exception as e:
            return {
                "ticket_created": False,
                "error": f"Failed to create ticket: {str(e)}"
            }

@router.post("/analyze-conversation/{conversation_id}")
async def analyze_conversation_for_tickets(
    conversation_id: str,
    latest_messages: List[Dict[str, Any]] = Body(...),
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    async with db_context as db:
        ticket_service = AutoTicketService(db)
        ticket_data = await ticket_service.analyze_conversation_for_tickets(
            conversation_id, latest_messages
        )
        
        if not ticket_data:
            return {"should_create_ticket": False, "reason": "No support issues detected"}
        
        return {
            "should_create_ticket": True,
            "ticket_data": ticket_data,
            "message": "Support issue detected. Ticket data generated."
        }


@router.get("/companies/{company_id}")
async def get_company_tickets(
    company_id: str,
    status: Optional[List[str]] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    async with db_context as db:
        ticket_service = AutoTicketService(db)
        tickets, total_count = await ticket_service.get_tickets_for_company(
            company_id, status, limit, offset
        )
        return {
            "tickets": tickets,
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }

@router.get("/companies/{company_id}/{ticket_id}")
async def get_ticket_details(
    company_id: str,
    ticket_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    async with db_context as db:
        ticket_service = AutoTicketService(db)
        ticket_details = await ticket_service.get_ticket_details(ticket_id, company_id)
        if not ticket_details:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return ticket_details

@router.patch("/companies/{company_id}/{ticket_id}")
async def update_ticket(
    company_id: str,
    ticket_id: str,
    update_data: TicketUpdateRequest = Body(...),
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    async with db_context as db:
        ticket_service = AutoTicketService(db)
        updated_by = current_user.email
        if update_data.status:
            success = await ticket_service.update_ticket_status(
                ticket_id, update_data.status, company_id, updated_by, update_data.note
            )
            if not success:
                raise HTTPException(status_code=400, detail="Failed to update ticket")
        return {"message": "Ticket updated successfully"}

@router.post("/companies/{company_id}/{ticket_id}/notes")
async def add_ticket_note(
    company_id: str,
    ticket_id: str,
    note_data: TicketNoteRequest = Body(...),
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    async with db_context as db:
        ticket_service = AutoTicketService(db)
        success = await ticket_service.add_ticket_note(
            ticket_id, note_data.content, current_user.email, company_id, note_data.is_internal
        )
        if not success:
            raise HTTPException(status_code=400, detail="Failed to add note")
        return {"message": "Note added successfully"}

@router.get("/companies/{ticket_id}/stats")
async def get_ticket_statistics(
    company_id: str,
    days: int = Query(7, description="Number of days to analyze", ge=1, le=365),
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    async with db_context as db:
        stats_query = '''
            SELECT 
                COUNT(*) as total_tickets,
                COUNT(CASE WHEN status = 'new' THEN 1 END) as new_tickets,
                COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
                COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_tickets,
                COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved_tickets,
                COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_tickets,
                COUNT(CASE WHEN source = 'auto_generated' THEN 1 END) as auto_generated,
                COUNT(CASE WHEN priority = 'critical' THEN 1 END) as critical_priority,
                COUNT(CASE WHEN priority = 'high' THEN 1 END) as high_priority,
                AVG(CASE WHEN resolved_at IS NOT NULL THEN 
                    EXTRACT(EPOCH FROM (resolved_at - created_at))/3600 
                END) as avg_resolution_hours
            FROM "Ticket" 
            WHERE ticket_id = $1 
            AND created_at >= NOW() - INTERVAL '1 day' * $2
        '''
        
        try:
            stats = await db.fetchrow(stats_query, company_id, days)

            statistics = dict(stats) if stats else {}

            if statistics.get('avg_resolution_hours'):
                statistics['avg_resolution_hours'] = round(float(statistics['avg_resolution_hours']), 2)
            
            return {
                "company_id": company_id,
                "period_days": days,
                "date_range": {
                    "from": f"NOW() - {days} days",
                    "to": "NOW()"
                },
                "statistics": statistics
            }
            
        except Exception as e:
            logger.error(f"Error getting ticket statistics: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve ticket statistics"
            )
