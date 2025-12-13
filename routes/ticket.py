# routes/ticket.py
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

class CreateTicketRequest(BaseModel):
    customer_id: str
    title: str
    description: str
    priority: Optional[str] = "medium"
    status: Optional[str] = "new"
    source: Optional[str] = "web_form"
    tags: Optional[List[str]] = []
    meta_data: Optional[Dict[str, Any]] = {}
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None


@router.post("/companies/{company_id}/create")
async def create_ticket(
    company_id: str,
    ticket_data: CreateTicketRequest = Body(...),
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    """Create a new ticket for a company"""
    async with db_context as db:
        ticket_service = AutoTicketService(db)
        
        try:
            # Generate ticket ID
            ticket_id = f"TKT-{str(uuid.uuid4())[:8].upper()}"
            
            # Build ticket data dict
            ticket_dict = {
                "id": ticket_id,
                "company_id": company_id,
                "customer_id": ticket_data.customer_id,
                "title": ticket_data.title,
                "description": ticket_data.description,
                "priority": ticket_data.priority or "medium",
                "status": ticket_data.status or "new",
                "source": ticket_data.source or "web_form",
                "tags": ticket_data.tags or [],
                "meta_data": ticket_data.meta_data or {},
                "customer_name": ticket_data.customer_name,
                "customer_email": ticket_data.customer_email,
                "customer_phone": ticket_data.customer_phone,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            
            created_ticket = await ticket_service.create_ticket(ticket_dict)
            return {
                "message": "Ticket created successfully",
                "ticket": created_ticket
            }
        except Exception as e:
            logger.error(f"Error creating ticket: {str(e)}")
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
                "company_id": company_id,
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
    priority: Optional[List[str]] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    """Get all tickets for a company with optional filters"""
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


@router.get("/companies/{company_id}/stats")
async def get_ticket_statistics(
    company_id: str,
    days: int = Query(7, description="Number of days to analyze", ge=1, le=365),
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    """Get ticket statistics for a company"""
    async with db_context as db:
        try:
            # Fixed query - using company_id instead of ticket_id
            stats_query = '''
                SELECT 
                    COUNT(*) as total_tickets,
                    COUNT(CASE WHEN status = 'new' THEN 1 END) as new_tickets,
                    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_tickets,
                    COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_tickets,
                    COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved_tickets,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_tickets,
                    COUNT(CASE WHEN source = 'auto_generated' THEN 1 END) as auto_generated,
                    COUNT(CASE WHEN source = 'email' THEN 1 END) as email_source,
                    COUNT(CASE WHEN source = 'phone' THEN 1 END) as phone_source,
                    COUNT(CASE WHEN source = 'chat' THEN 1 END) as chat_source,
                    COUNT(CASE WHEN source = 'web_form' THEN 1 END) as web_form_source,
                    COUNT(CASE WHEN priority = 'low' THEN 1 END) as low_priority,
                    COUNT(CASE WHEN priority = 'medium' THEN 1 END) as medium_priority,
                    COUNT(CASE WHEN priority = 'high' THEN 1 END) as high_priority,
                    COUNT(CASE WHEN priority = 'critical' THEN 1 END) as critical_priority,
                    AVG(CASE WHEN resolved_at IS NOT NULL THEN 
                        EXTRACT(EPOCH FROM (resolved_at - created_at))/3600 
                    END) as avg_resolution_hours
                FROM "Ticket" 
                WHERE company_id = $1 
                AND created_at >= NOW() - INTERVAL '1 day' * $2
            '''
            
            stats = await db.fetchrow(stats_query, company_id, days)
            
            if not stats:
                # Return default stats if no data
                return {
                    "total_tickets": 0,
                    "new_tickets": 0,
                    "open_tickets": 0,
                    "in_progress_tickets": 0,
                    "resolved_tickets": 0,
                    "closed_tickets": 0,
                    "avg_resolution_time_hours": 0,
                    "tickets_by_priority": {
                        "low": 0,
                        "medium": 0,
                        "high": 0,
                        "critical": 0
                    },
                    "tickets_by_source": {
                        "auto_generated": 0,
                        "email": 0,
                        "phone": 0,
                        "chat": 0,
                        "web_form": 0
                    }
                }

            # Format response to match frontend expectations
            avg_hours = stats['avg_resolution_hours']
            if avg_hours is not None:
                avg_hours = round(float(avg_hours), 2)
            else:
                avg_hours = 0
            
            return {
                "total_tickets": stats['total_tickets'] or 0,
                "new_tickets": stats['new_tickets'] or 0,
                "open_tickets": stats['open_tickets'] or 0,
                "in_progress_tickets": stats['in_progress_tickets'] or 0,
                "resolved_tickets": stats['resolved_tickets'] or 0,
                "closed_tickets": stats['closed_tickets'] or 0,
                "avg_resolution_time_hours": avg_hours,
                "tickets_by_priority": {
                    "low": stats['low_priority'] or 0,
                    "medium": stats['medium_priority'] or 0,
                    "high": stats['high_priority'] or 0,
                    "critical": stats['critical_priority'] or 0
                },
                "tickets_by_source": {
                    "auto_generated": stats['auto_generated'] or 0,
                    "email": stats['email_source'] or 0,
                    "phone": stats['phone_source'] or 0,
                    "chat": stats['chat_source'] or 0,
                    "web_form": stats['web_form_source'] or 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting ticket statistics: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve ticket statistics: {str(e)}"
            )


@router.get("/companies/{company_id}/{ticket_id}")
async def get_ticket_details(
    company_id: str,
    ticket_id: str,
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    """Get details of a specific ticket"""
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
    """Update a ticket's status, priority, or assignment"""
    async with db_context as db:
        try:
            updated_by = current_user.email
            updates_made = []
            
            # Build dynamic update query
            update_fields = []
            params = []
            param_index = 1
            
            if update_data.status is not None:
                update_fields.append(f"status = ${param_index}")
                params.append(update_data.status)
                param_index += 1
                updates_made.append("status")
            
            if update_data.priority is not None:
                update_fields.append(f"priority = ${param_index}")
                params.append(update_data.priority)
                param_index += 1
                updates_made.append("priority")
            
            if update_data.assigned_to is not None:
                update_fields.append(f"assigned_to = ${param_index}")
                params.append(update_data.assigned_to)
                param_index += 1
                updates_made.append("assigned_to")
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No valid fields to update")
            
            # Always update the updated_at timestamp
            update_fields.append(f"updated_at = ${param_index}")
            params.append(datetime.utcnow())
            param_index += 1
            
            # Add ticket_id and company_id to params
            params.append(ticket_id)
            params.append(company_id)
            
            update_query = f'''
                UPDATE "Ticket" 
                SET {", ".join(update_fields)}
                WHERE id = ${param_index} AND company_id = ${param_index + 1}
                RETURNING *
            '''
            
            result = await db.fetchrow(update_query, *params)
            
            if not result:
                raise HTTPException(status_code=404, detail="Ticket not found")
            
            # Add note if provided
            if update_data.note:
                note_content = f"Updated {', '.join(updates_made)} by {updated_by}: {update_data.note}"
                note_query = '''
                    INSERT INTO "TicketNote" (id, ticket_id, content, author, is_internal, created_at) 
                    VALUES ($1, $2, $3, $4, TRUE, NOW())
                '''
                await db.execute(note_query, str(uuid.uuid4()), ticket_id, note_content, updated_by)
            
            return {
                "message": "Ticket updated successfully",
                "updated_fields": updates_made,
                "ticket": dict(result)
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating ticket {ticket_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update ticket: {str(e)}")


@router.post("/companies/{company_id}/{ticket_id}/notes")
async def add_ticket_note(
    company_id: str,
    ticket_id: str,
    note_data: TicketNoteRequest = Body(...),
    current_user: UserResponse = Depends(get_current_user),
    db_context = Depends(get_db_connection),
):
    """Add a note to a ticket"""
    async with db_context as db:
        ticket_service = AutoTicketService(db)
        success = await ticket_service.add_ticket_note(
            ticket_id, note_data.content, current_user.email, company_id, note_data.is_internal
        )
        if not success:
            raise HTTPException(status_code=400, detail="Failed to add note")
        return {"message": "Note added successfully"}


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
