import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from app.models.tickets import Ticket, TicketNote, TicketStatus, TicketPriority, TicketSource
from app.models.conversation import Conversation
from sqlalchemy import select, update
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

    async def analyze_conversation_for_tickets(self, conversation_id: str, latest_messages: List[Dict[str, Any]]):
        query = select(Conversation).where(Conversation.id == conversation_id)
        conversation = await self.db.fetchrow(query)
        if not conversation:
            return None
        combined_text = " ".join([msg.get("content", "") for msg in latest_messages]).lower()
        issue_detected = any(keyword in combined_text for keyword in self.issue_keywords)
        if not issue_detected:
            return None
        priority = self._determine_priority(combined_text)
        title = self._generate_ticket_title(latest_messages)
        description = self._generate_ticket_description(latest_messages, conversation)
        ticket_data = {
            "id": f"TKT-{str(uuid.uuid4())[:8].upper()}",
            "company_id": conversation["company_id"],
            "conversation_id": conversation_id,
            "customer_id": conversation["customer_id"],
            "title": title,
            "description": description,
            "priority": priority,
            "status": TicketStatus.NEW,
            "source": TicketSource.AUTO_GENERATED,
            "customer_name": self._extract_customer_name(conversation),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        return ticket_data

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
            f"Auto-generated ticket from conversation {conversation['id']} (customer: {conversation.get('customer_id','')}).",
            "Recent messages:"
        ]
        for msg in messages[-5:]:
            parts.append(f"{msg.get('role','?')} [{msg.get('timestamp','')}] : {msg.get('content','')[:200]}")
        return "\n".join(parts)

    def _extract_customer_name(self, conversation: dict) -> Optional[str]:
        metadata = conversation.get("meta_data") or {}
        return metadata.get("customer_name") or metadata.get("client_info", {}).get("name")

    async def create_ticket(self, ticket_data: dict) -> dict:
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
        return dict(ticket)


    async def get_tickets_for_company(self, company_id: str, status_filter: Optional[List[str]] = None, limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        query = f'SELECT * FROM "Ticket" WHERE company_id=$1'
        params = [company_id]
        if status_filter:
            query += " AND status = ANY($2)"
            params.append(status_filter)
        query += " ORDER BY created_at DESC LIMIT $3 OFFSET $4"
        params.extend([limit, offset])
        rows = await self.db.fetch(query, *params)
        count_query = 'SELECT COUNT(*) FROM "Ticket" WHERE company_id=$1'
        total = await self.db.fetchval(count_query, company_id)
        return [dict(r) for r in rows], total or 0

    async def get_ticket_details(self, ticket_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        query = 'SELECT * FROM "Ticket" WHERE id=$1 AND company_id=$2'
        ticket = await self.db.fetchrow(query, ticket_id, company_id)
        if not ticket:
            return None
        notes_query = 'SELECT * FROM "TicketNote" WHERE ticket_id=$1 ORDER BY created_at ASC'
        notes = await self.db.fetch(notes_query, ticket_id)
        ticket_details = dict(ticket)
        ticket_details["notes"] = [dict(n) for n in notes]
        return ticket_details

    async def update_ticket_status(self, ticket_id: str, new_status: str, company_id: str, updated_by: str, note: Optional[str] = None) -> bool:
        update_query = 'UPDATE "Ticket" SET status=$1, updated_at=NOW() WHERE id=$2 AND company_id=$3'
        result = await self.db.execute(update_query, new_status, ticket_id, company_id)
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
        return True
