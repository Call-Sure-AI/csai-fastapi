# app/services/ticket_service.py
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from app.models.tickets import TicketStatus, TicketPriority, ConversationAnalysisResult
from app.db.postgres_client import get_db_connection
import uuid
import json

logger = logging.getLogger(__name__)

class AutoTicketService:
    def __init__(self, db_session):
        self.db = db_session
        self.issue_keywords = [
            "problem", "issue", "error", "bug", "broken", "not working", 
            "can't", "cannot", "unable", "help", "support", "complaint",
            "refund", "billing", "charge", "payment", "account", "access"
        ]
        self.urgency_keywords = {
            "critical": ["urgent", "emergency", "critical", "asap", "immediately"],
            "high": ["important", "soon", "quickly", "priority"],
            "medium": ["when possible", "sometime", "eventually"],
            "low": ["minor", "small", "tiny", "cosmetic"]
        }

    # ==================== HISTORY METHODS ====================
    
    async def add_history_entry(
        self, 
        ticket_id: str, 
        action: str, 
        changed_by: str,
        field_name: str = None,
        old_value: str = None,
        new_value: str = None
    ) -> None:
        """Add a history entry for a ticket"""
        try:
            query = '''
                INSERT INTO "TicketHistory" (id, ticket_id, action, field_name, old_value, new_value, changed_by, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            '''
            await self.db.execute(
                query, 
                str(uuid.uuid4()),
                ticket_id, 
                action, 
                field_name, 
                old_value, 
                new_value, 
                changed_by
            )
            logger.info(f"History entry added for ticket {ticket_id}: {action}")
        except Exception as e:
            logger.error(f"Error adding history entry: {e}")

    async def get_ticket_history(self, ticket_id: str) -> List[Dict]:
        """Get history for a ticket"""
        try:
            query = '''
                SELECT id, ticket_id, action, field_name, old_value, new_value, changed_by, created_at
                FROM "TicketHistory"
                WHERE ticket_id = $1
                ORDER BY created_at DESC
            '''
            rows = await self.db.fetch(query, ticket_id)
            return [{
                'id': str(row['id']),
                'ticket_id': row['ticket_id'],
                'action': row['action'],
                'field_name': row['field_name'],
                'old_value': row['old_value'],
                'new_value': row['new_value'],
                'changed_by': row['changed_by'],
                'created_at': row['created_at'].isoformat() if row['created_at'] else None
            } for row in rows]
        except Exception as e:
            logger.error(f"Error getting ticket history: {e}")
            return []

    # ==================== TEAM MEMBERS ====================

    async def get_team_members(self, company_id: str) -> List[Dict]:
        """Get team members for ticket assignment"""
        try:
            query = '''
                SELECT u.id, u.email, u.name, cm.role
                FROM "User" u
                JOIN "CompanyMember" cm ON u.id = cm.user_id
                WHERE cm.company_id = $1
                ORDER BY u.name ASC, u.email ASC
            '''
            rows = await self.db.fetch(query, company_id)
            return [{
                'id': str(row['id']),
                'email': row['email'],
                'name': row['name'] or row['email'],
                'role': row['role'] or 'member'
            } for row in rows]
        except Exception as e:
            logger.error(f"Error getting team members: {e}")
            return []

    # ==================== TICKET ANALYSIS ====================

    async def analyze_conversation_for_tickets(
        self, 
        conversation_id: str, 
        latest_messages: List[Dict[str, Any]]
    ) -> Optional[ConversationAnalysisResult]:
        
        try:
            conversation = None
            try:
                async with await get_db_connection() as conn:
                    conversation_query = """
                    SELECT call_id, user_phone, agent_id, status, created_at, id, duration, outcome
                    FROM Conversation WHERE call_id = $1
                    """
                    conversation = await self.db.fetchrow(conversation_query, conversation_id)

                    if not conversation:
                        outcome_query = """
                        SELECT 
                            call_id, 
                            user_phone, 
                            agent_id, 
                            'completed' as status, 
                            created_at,
                            id,
                            conversation_duration as duration,
                            outcome
                        FROM Conversation_Outcome WHERE call_id = $1
                        """
                        conversation = await conn.fetchrow(outcome_query, conversation_id)
                        logger.info(f"Found conversation in Conversation_Outcome: {conversation_id}")
                        
            except Exception as e:
                logger.warning(f"Could not fetch conversation {conversation_id}: {str(e)}")

            combined_text = " ".join([
                msg.get("content", "") for msg in latest_messages
            ]).lower()

            detected_issues = []
            confidence_score = 0.0
            
            for keyword in self.issue_keywords:
                if keyword in combined_text:
                    detected_issues.append(keyword)
                    confidence_score += 0.1

            question_indicators = ["how do i", "how to", "can you help", "?"]
            for indicator in question_indicators:
                if indicator in combined_text:
                    confidence_score += 0.05

            should_create_ticket = confidence_score >= 0.1 and len(detected_issues) > 0

            if not should_create_ticket:
                return ConversationAnalysisResult(
                    should_create_ticket=False,
                    confidence_score=confidence_score,
                    detected_issues=detected_issues,
                    priority=TicketPriority.MEDIUM,
                    suggested_title="",
                    suggested_description="",
                    reason="No support issues detected in conversation"
                )

            priority = self._determine_priority(combined_text)
            title = self._generate_ticket_title(latest_messages)

            conversation_dict = dict(conversation) if conversation else {"call_id": conversation_id}
            description = self._generate_ticket_description(latest_messages, conversation_dict)

            return ConversationAnalysisResult(
                should_create_ticket=True,
                confidence_score=min(confidence_score, 1.0),
                detected_issues=detected_issues,
                priority=priority,
                suggested_title=title,
                suggested_description=description
            )

        except Exception as e:
            logger.error(f"Error analyzing conversation {conversation_id}: {str(e)}")
            return ConversationAnalysisResult(
                should_create_ticket=False,
                confidence_score=0.0,
                detected_issues=[],
                priority=TicketPriority.MEDIUM,
                suggested_title="",
                suggested_description="",
                reason=f"Analysis failed: {str(e)}"
            )

    def _determine_priority(self, text: str) -> str:
        for priority, keywords in self.urgency_keywords.items():
            if any(keyword in text for keyword in keywords):
                return priority
        return "medium"

    def _generate_ticket_title(self, messages: List[Dict[str, Any]]) -> str:
        first_user_msg = next((msg for msg in messages if msg.get("role") == "user"), {})
        content = first_user_msg.get("content", "")
        title = content[:100].strip()
        if len(content) > 100:
            title += "..."
        return title or "Customer Support Request"

    def _generate_ticket_description(self, messages: List[Dict[str, Any]], conversation: dict) -> str:
        parts = [
            f"Auto-generated ticket from conversation {conversation.get('call_id', 'Unknown')}",
            f"Data source: {conversation.get('source_table', 'Unknown')} table",
            f"Customer Phone: {conversation.get('user_phone', 'N/A')}",
            f"Agent: {conversation.get('agent_id', 'N/A')}",
            ""
        ]

        if conversation.get('duration'):
            parts.insert(-1, f"Duration: {conversation['duration']} seconds")
        
        parts.extend([
            "Recent conversation messages:",
            ""
        ])

        for msg in messages[-5:]:
            role = msg.get('role', 'unknown')
            timestamp = msg.get('timestamp', '')
            content = msg.get('content', '')[:200]
            parts.append(f"[{role.upper()}] {timestamp}: {content}")
        
        return "\n".join(parts)

    def _extract_customer_name(self, conversation: dict) -> Optional[str]:
        metadata = conversation.get("meta_data") or {}
        return metadata.get("customer_name") or metadata.get("client_info", {}).get("name")

    # ==================== TICKET CRUD ====================

    async def create_ticket(self, ticket_data: dict, created_by: str = None) -> dict:
        processed_data = {}
        for key, value in ticket_data.items():
            if key == 'meta_data':
                processed_data[key] = json.dumps(value) if isinstance(value, dict) else value
            elif key == 'tags':
                if isinstance(value, str):
                    try:
                        parsed = json.loads(value)
                        processed_data[key] = parsed if isinstance(parsed, list) else []
                    except:
                        processed_data[key] = []
                elif isinstance(value, list):
                    processed_data[key] = value
                else:
                    processed_data[key] = value
            elif key in ['created_at', 'updated_at', 'resolved_at', 'closed_at']:
                if isinstance(value, str):
                    try:
                        processed_data[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except ValueError:
                        processed_data[key] = datetime.utcnow()
                elif value is None:
                    processed_data[key] = None
                else:
                    processed_data[key] = value
            else:
                processed_data[key] = value
        
        columns = ', '.join(processed_data.keys())
        placeholders = ', '.join(f'${i+1}' for i in range(len(processed_data)))
        values = list(processed_data.values())
        
        query = f'INSERT INTO "Ticket" ({columns}) VALUES ({placeholders}) RETURNING *'
        ticket = await self.db.fetchrow(query, *values)
        ticket_dict = dict(ticket)
        
        # Log ticket creation in history
        if created_by:
            await self.add_history_entry(
                ticket_id=ticket_dict['id'],
                action='created',
                changed_by=created_by,
                field_name=None,
                old_value=None,
                new_value=None
            )
        
        return ticket_dict

    async def get_tickets_for_company(
        self,
        company_id: str,
        status_filter: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:

        rows = await self.db.fetch(
            '''
            SELECT *
            FROM "Ticket"
            WHERE company_id = $1
              AND (
                $2::text[] IS NULL
                OR status = ANY($2::text[])
              )
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
            ''',
            company_id,
            status_filter,
            limit,
            offset,
        )

        total = await self.db.fetchval(
            '''
            SELECT COUNT(*)
            FROM "Ticket"
            WHERE company_id = $1
              AND (
                $2::text[] IS NULL
                OR status = ANY($2::text[])
              )
            ''',
            company_id,
            status_filter,
        )

        return [dict(r) for r in rows], total or 0

    async def get_ticket_details(self, ticket_id: str, company_id: str) -> Optional[Dict]:
        """Get ticket with all notes and history"""
        try:
            # Get ticket
            ticket_query = '''
                SELECT * FROM "Ticket" 
                WHERE id = $1 AND company_id = $2
            '''
            ticket = await self.db.fetchrow(ticket_query, ticket_id, company_id)
            
            if not ticket:
                return None
            
            # Get notes
            notes_query = '''
                SELECT id, ticket_id, content, author, is_internal, created_at 
                FROM "TicketNote" 
                WHERE ticket_id = $1 
                ORDER BY created_at ASC
            '''
            notes = await self.db.fetch(notes_query, ticket_id)
            
            # Get history
            history = await self.get_ticket_history(ticket_id)
            
            # Combine
            ticket_dict = dict(ticket)
            
            # Map notes with correct field name
            ticket_dict['notes'] = [{
                'id': note['id'],
                'ticket_id': note['ticket_id'],
                'content': note['content'],
                'created_by': note['author'],
                'is_internal': note['is_internal'],
                'created_at': note['created_at'].isoformat() if note['created_at'] else None
            } for note in notes]
            
            # Add history
            ticket_dict['history'] = history
            
            return ticket_dict
            
        except Exception as e:
            logger.error(f"Error getting ticket details: {e}")
            return None

    async def update_ticket_status(self, ticket_id: str, new_status: str, company_id: str, updated_by: str, note: Optional[str] = None) -> bool:
        # Get old status for history
        old_ticket = await self.db.fetchrow(
            'SELECT status FROM "Ticket" WHERE id=$1 AND company_id=$2',
            ticket_id, company_id
        )
        old_status = old_ticket['status'] if old_ticket else None
        
        update_query = 'UPDATE "Ticket" SET status=$1, updated_at=NOW() WHERE id=$2 AND company_id=$3'
        result = await self.db.execute(update_query, new_status, ticket_id, company_id)
        
        # Log history
        await self.add_history_entry(
            ticket_id=ticket_id,
            action='status_changed',
            changed_by=updated_by,
            field_name='status',
            old_value=old_status,
            new_value=new_status
        )
        
        if note:
            note_query = 'INSERT INTO "TicketNote" (id, ticket_id, content, author, is_internal, created_at) VALUES ($1, $2, $3, $4, TRUE, NOW())'
            await self.db.execute(note_query, str(uuid.uuid4()), ticket_id, note, updated_by)
        return True

    async def add_ticket_note(self, ticket_id: str, content: str, author: str, company_id: str, is_internal: bool=True) -> bool:
        ticket_query = 'SELECT 1 FROM "Ticket" WHERE id=$1 AND company_id=$2'
        t = await self.db.fetchrow(ticket_query, ticket_id, company_id)
        if not t:
            return False
        note_query = 'INSERT INTO "TicketNote" (id, ticket_id, content, author, is_internal, created_at) VALUES ($1, $2, $3, $4, $5, NOW())'
        await self.db.execute(note_query, str(uuid.uuid4()), ticket_id, content, author, is_internal)
        
        # Log history
        await self.add_history_entry(
            ticket_id=ticket_id,
            action='note_added',
            changed_by=author
        )
        
        return True

    async def close_ticket(
        self, 
        ticket_id: str, 
        company_id: str, 
        closed_by: str,
        reason: Optional[str] = None,
        resolution_notes: Optional[str] = None,
        auto_resolved: bool = False
    ) -> bool:

        try:
            ticket_check_query = '''
                SELECT id, status FROM "Ticket" 
                WHERE id = $1 AND company_id = $2
            '''
            ticket = await self.db.fetchrow(ticket_check_query, ticket_id, company_id)
            
            if not ticket:
                logger.warning(f"Ticket {ticket_id} not found for company {company_id}")
                return False

            if ticket['status'] == 'closed':
                logger.info(f"Ticket {ticket_id} is already closed")
                return False

            old_status = ticket['status']
            close_timestamp = datetime.utcnow()
            update_query = '''
                UPDATE "Ticket" 
                SET 
                    status = $1,
                    closed_at = $2,
                    updated_at = $3,
                    auto_resolved = $4,
                    resolution_notes = COALESCE($5, resolution_notes)
                WHERE id = $6 AND company_id = $7
            '''
            
            await self.db.execute(
                update_query,
                'closed',
                close_timestamp,
                close_timestamp,
                auto_resolved,
                resolution_notes,
                ticket_id,
                company_id
            )

            # Log history
            await self.add_history_entry(
                ticket_id=ticket_id,
                action='closed',
                changed_by=closed_by,
                field_name='status',
                old_value=old_status,
                new_value='closed'
            )

            if reason:
                close_note_content = f"Ticket closed by {closed_by}. Reason: {reason}"
                await self._add_system_note(ticket_id, close_note_content, closed_by)
            else:
                close_note_content = f"Ticket closed by {closed_by}."
                await self._add_system_note(ticket_id, close_note_content, closed_by)
            
            logger.info(f"Ticket {ticket_id} successfully closed by {closed_by}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing ticket {ticket_id}: {e}")
            raise

    async def _add_system_note(self, ticket_id: str, content: str, author: str) -> None:
        """Add a system-generated note to a ticket"""
        note_query = '''
            INSERT INTO "TicketNote" (id, ticket_id, content, author, is_internal, created_at) 
            VALUES ($1, $2, $3, $4, TRUE, NOW())
        '''
        await self.db.execute(
            note_query, 
            str(uuid.uuid4()), 
            ticket_id, 
            content, 
            author
        )

    async def get_closable_tickets(self, company_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            query = '''
                SELECT id, title, status, priority, customer_name, created_at, updated_at
                FROM "Ticket" 
                WHERE company_id = $1 
                AND status IN ('resolved', 'in_progress', 'open')
                ORDER BY updated_at DESC
                LIMIT $2
            '''
            
            tickets = await self.db.fetch(query, company_id, limit)
            return [dict(ticket) for ticket in tickets]
            
        except Exception as e:
            logger.error(f"Error getting closable tickets for company {company_id}: {e}")
            return []