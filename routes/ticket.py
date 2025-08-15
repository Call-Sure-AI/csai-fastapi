from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from app.db.postgres_client import get_db_connection
from app.models.schemas import UserResponse
from middleware.auth_middleware import get_current_user
from app.services.ticket_service import AutoTicketService
from pydantic import BaseModel
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tickets", tags=["Tickets"])

class TicketUpdateRequest(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None
    note: Optional[str] = None

class TicketNoteRequest(BaseModel):
    content: str
    is_internal: bool = True

class TicketCloseRequest(BaseModel):
    reason: Optional[str] = None
    resolution_notes: Optional[str] = None
    auto_resolved: bool = False

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
        try:
            ticket_service = AutoTicketService(db)
            
            # Get conversation details for customer info
            conversation_details = None
            try:
                # Try Conversation table first
                conv_query = """
                SELECT call_id, user_phone, agent_id, created_at 
                FROM Conversation WHERE call_id = $1
                """
                conversation_details = await db.fetchrow(conv_query, conversation_id)
                
                if not conversation_details:
                    # Try Conversation_Outcome table
                    outcome_query = """
                    SELECT call_id, user_phone, agent_id, created_at 
                    FROM Conversation_Outcome WHERE call_id = $1
                    """
                    conversation_details = await db.fetchrow(outcome_query, conversation_id)
                    
            except Exception as e:
                logger.warning(f"Could not fetch conversation details: {str(e)}")
            
            # Analyze conversation
            analysis_result = await ticket_service.analyze_conversation_for_tickets(
                conversation_id, latest_messages
            )
            
            if not analysis_result or not analysis_result.should_create_ticket:
                return {
                    "ticket_created": False,
                    "reason": analysis_result.reason if analysis_result else "No support issues detected",
                    "confidence_score": analysis_result.confidence_score if analysis_result else 0
                }

            # Create customer_id (matching your format)
            customer_id = None
            if conversation_details and conversation_details.get('user_phone'):
                phone_clean = str(conversation_details['user_phone']).replace('+', '').replace('-', '').replace(' ', '')
                customer_id = f"CUST-{phone_clean}"
            else:
                customer_id = f"CUST-AUTO-{str(uuid.uuid4())[:8].upper()}"

            # Create ticket data matching your exact structure
            ticket_data = {
                "id": f"TKT-{str(uuid.uuid4())[:8].upper()}",
                "company_id": company_id,  # This matches the URL parameter
                "customer_id": customer_id,
                "title": analysis_result.suggested_title,
                "description": analysis_result.suggested_description,
                "priority": analysis_result.priority.value,
                "status": "new",
                "source": "auto_generated",
                "tags": [
                    "auto-generated",
                    "support",
                    analysis_result.priority.value,
                    *analysis_result.detected_issues[:3]
                ],
                "meta_data": {
                    "source": "auto_conversation_analysis",
                    "auto_generated": True,
                    "confidence_score": analysis_result.confidence_score,
                    "detected_issues": analysis_result.detected_issues,
                    "conversation_id": conversation_id,
                    "agent_id": conversation_details.get('agent_id') if conversation_details else None,
                    "user_phone": conversation_details.get('user_phone') if conversation_details else None,
                    "analysis_timestamp": datetime.utcnow().isoformat()
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            logger.info(f"Creating auto-ticket with data structure matching manual create")
            created_ticket = await ticket_service.create_ticket(ticket_data)
            
            return {
                "ticket_created": True,
                "ticket": created_ticket,
                "confidence_score": analysis_result.confidence_score,
                "detected_issues": analysis_result.detected_issues,
                "customer_id": customer_id,
                "message": f"Auto-created ticket {created_ticket.get('id', 'unknown')} from conversation analysis"
            }
            
        except Exception as e:
            logger.error(f"Error auto-creating ticket: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create ticket: {str(e)}"
            )



@router.post("/analyze-conversation/{conversation_id}")
async def analyze_conversation_for_tickets(
    conversation_id: str,
    latest_messages: List[Dict[str, Any]] = Body(...),
    current_user: UserResponse = Depends(get_current_user),
):
    try:
        async with await get_db_connection() as db:
            ticket_service = AutoTicketService(db)
            analysis_result = await ticket_service.analyze_conversation_for_tickets(
                conversation_id, latest_messages
            )
        
        if not analysis_result:
            return {
                "should_create_ticket": False,
                "reason": "Analysis failed"
            }
        
        return {
            "should_create_ticket": analysis_result.should_create_ticket,
            "confidence_score": analysis_result.confidence_score,
            "detected_issues": analysis_result.detected_issues,
            "priority": analysis_result.priority.value,
            "suggested_title": analysis_result.suggested_title,
            "suggested_description": analysis_result.suggested_description,
            "reason": analysis_result.reason
        }
    except Exception as e:
        logger.error(f"Error analyzing conversation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )

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

@router.patch("/companies/{company_id}/{ticket_id}/close")
async def close_ticket(
    company_id: str,
    ticket_id: str,
    close_data: TicketCloseRequest = Body(...),
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    """Close a ticket with optional reason and resolution notes"""
    async with db_context as db:
        ticket_service = AutoTicketService(db)
        
        try:
            success = await ticket_service.close_ticket(
                ticket_id=ticket_id,
                company_id=company_id,
                closed_by=current_user.email,
                reason=close_data.reason,
                resolution_notes=close_data.resolution_notes,
                auto_resolved=close_data.auto_resolved
            )
            
            if not success:
                raise HTTPException(
                    status_code=404, 
                    detail="Ticket not found or already closed"
                )
            
            return {
                "message": "Ticket closed successfully",
                "ticket_id": ticket_id,
                "closed_by": current_user.email,
                "closed_at": datetime.utcnow().isoformat()
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to close ticket: {str(e)}"
            )