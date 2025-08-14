import asyncio
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
import asyncpg
from fastapi import WebSocket, WebSocketDisconnect
import logging

from handlers.analytics_handler import AnalyticsHandler
from app.db.queries.conversation_queries import ConversationQueries

logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.active_connections: Dict[str, WebSocket] = {}
        self.conversation_data: Dict[str, Dict] = {}
        self.analytics_handler = AnalyticsHandler(db_pool)

    async def connect(self, websocket: WebSocket, call_id: str, agent_id: str):
        await websocket.accept()
        self.active_connections[call_id] = websocket

        self.conversation_data[call_id] = {
            'call_id': call_id,
            'agent_id': agent_id,
            'start_time': datetime.utcnow(),
            'messages': [],
            'transcript': '',
            'user_phone': None,
            'status': 'connected'
        }
        
        logger.info(f"WebSocket connection established for call {call_id}")

    def disconnect(self, call_id: str):
        if call_id in self.active_connections:
            del self.active_connections[call_id]
        logger.info(f"WebSocket connection closed for call {call_id}")

    async def send_message(self, call_id: str, message: dict):
        if call_id in self.active_connections:
            websocket = self.active_connections[call_id]
            await websocket.send_text(json.dumps(message))

    async def broadcast_to_agents(self, message: dict):
        disconnected = []
        for call_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except:
                disconnected.append(call_id)

        for call_id in disconnected:
            self.disconnect(call_id)

    async def handle_message(self, call_id: str, message_data: dict):
        try:
            message_type = message_data.get('type')
            
            if message_type == 'user_joined':
                await self._handle_user_joined(call_id, message_data)
            elif message_type == 'transcript_update':
                await self._handle_transcript_update(call_id, message_data)
            elif message_type == 'call_ended':
                await self._handle_call_ended(call_id, message_data)
            elif message_type == 'agent_response':
                await self._handle_agent_response(call_id, message_data)
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling message for call {call_id}: {str(e)}")

    async def _handle_user_joined(self, call_id: str, message_data: dict):
        if call_id in self.conversation_data:
            self.conversation_data[call_id]['user_phone'] = message_data.get('phone')
            self.conversation_data[call_id]['user_details'] = message_data.get('user_details', {})

            conversation_queries = ConversationQueries()
            await conversation_queries.create_conversation(
                self.db_pool,
                call_id,
                message_data.get('phone'),
                self.conversation_data[call_id]['agent_id']
            )

            await self.send_message(call_id, {
                'type': 'user_joined',
                'phone': message_data.get('phone'),
                'user_details': message_data.get('user_details', {})
            })

    async def _handle_transcript_update(self, call_id: str, message_data: dict):
        if call_id in self.conversation_data:
            transcript_chunk = message_data.get('transcript', '')
            speaker = message_data.get('speaker', 'unknown')  # 'user' or 'agent'

            self.conversation_data[call_id]['messages'].append({
                'speaker': speaker,
                'text': transcript_chunk,
                'timestamp': datetime.utcnow().isoformat()
            })

            self.conversation_data[call_id]['transcript'] += f"{speaker}: {transcript_chunk}\n"

            await self.send_message(call_id, {
                'type': 'transcript_update',
                'speaker': speaker,
                'text': transcript_chunk,
                'timestamp': datetime.utcnow().isoformat()
            })

    async def _handle_agent_response(self, call_id: str, message_data: dict):
        if call_id in self.conversation_data:
            response_text = message_data.get('response', '')
            action = message_data.get('action')  # 'send_message', 'schedule_callback', etc.
            
            if action == 'send_message':
                await self._handle_transcript_update(call_id, {
                    'transcript': response_text,
                    'speaker': 'agent'
                })
            elif action == 'schedule_callback':
                self.conversation_data[call_id]['callback_requested'] = True
                self.conversation_data[call_id]['callback_details'] = message_data.get('callback_details')

    async def _handle_call_ended(self, call_id: str, message_data: dict):
        if call_id not in self.conversation_data:
            return
            
        conversation = self.conversation_data[call_id]
        end_time = datetime.utcnow()
        duration = int((end_time - conversation['start_time']).total_seconds())

        conversation['end_time'] = end_time
        conversation['duration'] = duration
        conversation['status'] = 'completed'

        outcome = self.analyze_conversation_outcome(conversation)
        lead_score = self.calculate_lead_score(conversation)
        extracted_details = self.extract_customer_details(conversation)

        try:
            await self.analytics_handler.record_conversation_outcome(
                call_id=call_id,
                user_phone=conversation.get('user_phone'),
                conversation_duration=duration,
                outcome=outcome,
                lead_score=lead_score,
                extracted_details=extracted_details,
                agent_id=conversation['agent_id']
            )
        except Exception as e:
            logger.error(f"Failed to record analytics for call {call_id}: {str(e)}")

        conversation_queries = ConversationQueries()
        await conversation_queries.update_conversation_outcome(
            self.db_pool,
            call_id,
            outcome,
            json.dumps(conversation['messages']),
            duration
        )

        await self.send_message(call_id, {
            'type': 'call_completed',
            'outcome': outcome,
            'lead_score': lead_score,
            'duration': duration,
            'extracted_details': extracted_details
        })

        del self.conversation_data[call_id]

    def analyze_conversation_outcome(self, conversation_data: dict) -> str:
        transcript = conversation_data.get('transcript', '').lower()

        if conversation_data.get('callback_requested'):
            return 'callback_requested'

        if any(phrase in transcript for phrase in ['yes, schedule', 'book a call', 'interested in meeting']):
            return 'callback_requested'
        elif any(phrase in transcript for phrase in ['sounds good', 'interested', 'tell me more']):
            return 'interested'
        elif any(phrase in transcript for phrase in ['not interested', 'no thanks', 'busy']):
            return 'not_interested'
        else:
            return 'incomplete'

    def calculate_lead_score(self, conversation_data: dict) -> int:
        """Calculate lead score based on conversation quality"""
        score = 50
        
        transcript = conversation_data.get('transcript', '').lower()
        duration = conversation_data.get('duration', 0)

        if duration > 120:
            score += 20
        elif duration > 60:
            score += 10

        if any(word in transcript for word in ['budget', 'timeline', 'decision']):
            score += 15
        
        if any(word in transcript for word in ['email', 'contact', 'schedule']):
            score += 10

        if any(word in transcript for word in ['busy', 'not now', 'call back later']):
            score -= 10
            
        return max(min(score, 100), 0)

    def extract_customer_details(self, conversation_data: dict) -> Dict[str, Any]:
        transcript = conversation_data.get('transcript', '').lower()
        details = conversation_data.get('user_details', {})

        extracted = {
            'phone': conversation_data.get('user_phone'),
            'initial_details': details,
            'conversation_duration': conversation_data.get('duration', 0),
            'engagement_level': 'high' if conversation_data.get('duration', 0) > 120 else 'medium'
        }
        
        # You can enhance this with NLP to extract:
        # - Company name
        # - Budget mentions
        # - Timeline mentions
        # - Pain points
        # - Decision maker info
        
        return extracted

conversation_manager = None

def get_conversation_manager(db_pool: asyncpg.Pool) -> ConversationManager:
    global conversation_manager
    if conversation_manager is None:
        conversation_manager = ConversationManager(db_pool)
    return conversation_manager
