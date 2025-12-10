import asyncio
import asyncpg
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket
from app.db.postgres_client import get_db_connection
import os

logger = logging.getLogger(__name__)


def serialize_row(row_dict: dict) -> dict:
    """Convert database row to JSON-serializable dict"""
    result = {}
    for key, value in row_dict.items():
        if hasattr(value, 'isoformat'):  # datetime, date, time objects
            result[key] = value.isoformat()
        elif hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
            # Handle lists/arrays
            result[key] = list(value)
        else:
            result[key] = value
    return result


class AgentNumberRealtimeService:
    """Service to manage real-time agent number updates via WebSocket"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}  # company_id -> websockets
        self.listener_conn: asyncpg.Connection = None
        
    async def start(self):
        """Start listening for PostgreSQL notifications"""
        try:
            from config import config
            env = os.getenv('FLASK_ENV', 'development')
            app_config = config.get(env, config['default'])
            
            # Create dedicated connection for LISTEN
            self.listener_conn = await asyncpg.connect(app_config.DATABASE_URL)
            
            # Start listening to agent_number_updates channel
            await self.listener_conn.add_listener('agent_number_updates', self._handle_notification)
            
            logger.info("✓ AgentNumber real-time service started - listening for updates")
            
        except Exception as e:
            logger.error(f"Failed to start agent number real-time service: {e}", exc_info=True)
            self.listener_conn = None
    
    async def stop(self):
        """Stop listening and close connection"""
        if self.listener_conn:
            try:
                await self.listener_conn.remove_listener('agent_number_updates', self._handle_notification)
                await self.listener_conn.close()
                logger.info("AgentNumber real-time service stopped")
            except Exception as e:
                logger.error(f"Error stopping agent number service: {e}")
    
    async def _handle_notification(self, connection, pid, channel, payload):
        """Handle PostgreSQL NOTIFY event"""
        try:
            data = json.loads(payload)
            company_id = data.get('company_id')
            
            logger.info(f"📞 AgentNumber updated for company {company_id}: {data.get('event')}")
            
            # Broadcast to all connected clients for this company
            if company_id in self.active_connections:
                await self.broadcast_to_company(company_id, data)
                
        except Exception as e:
            logger.error(f"Error handling agent number notification: {e}")
    
    async def connect(self, websocket: WebSocket, company_id: str):
        """Register a new WebSocket connection"""
        await websocket.accept()
        
        if company_id not in self.active_connections:
            self.active_connections[company_id] = set()
        
        self.active_connections[company_id].add(websocket)
        logger.info(f"✓ WebSocket connected for company {company_id} (AgentNumber)")
        
        # Send current agent numbers immediately upon connection
        await self.send_current_agent_numbers(websocket, company_id)
    
    def disconnect(self, websocket: WebSocket, company_id: str):
        """Unregister a WebSocket connection"""
        if company_id in self.active_connections:
            self.active_connections[company_id].discard(websocket)
            if not self.active_connections[company_id]:
                del self.active_connections[company_id]
        
        logger.info(f"WebSocket disconnected for company {company_id} (AgentNumber)")
    
    async def broadcast_to_company(self, company_id: str, data: dict):
        """Broadcast agent number update to all connections for a company"""
        if company_id not in self.active_connections:
            return
        
        disconnected = set()
        
        for websocket in self.active_connections[company_id]:
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")
                disconnected.add(websocket)
        
        # Clean up disconnected websockets
        for websocket in disconnected:
            self.disconnect(websocket, company_id)
    
    async def send_current_agent_numbers(self, websocket: WebSocket, company_id: str):
        """Send current agent numbers to a newly connected client"""
        try:
            async with await get_db_connection() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        an.id,
                        an.company_id,
                        an.agent_id,
                        an.phone_number,
                        a.name as agent_name,
                        a.type as agent_type,
                        a.is_active as agent_is_active
                    FROM public."AgentNumber" an
                    LEFT JOIN public."Agent" a ON an.agent_id = a.id
                    WHERE an.company_id = $1
                    ORDER BY an.phone_number
                """, company_id)
                
                if rows:
                    agent_numbers = [serialize_row(dict(row)) for row in rows]
                    data = {
                        'event': 'agent_numbers_current',
                        'company_id': company_id,
                        'data': agent_numbers,
                        'count': len(agent_numbers)
                    }
                    await websocket.send_json(data)
                    logger.info(f"✅ Sent {len(agent_numbers)} agent numbers to company {company_id}")
                else:
                    await websocket.send_json({
                        'event': 'agent_numbers_current',
                        'company_id': company_id,
                        'data': [],
                        'count': 0,
                        'message': 'No agent numbers found'
                    })
                    logger.info(f"📤 Sent 'no data' message to company {company_id}")
        
        except Exception as e:
            logger.error(f"Error sending current agent numbers: {e}", exc_info=True)
            try:
                await websocket.send_json({
                    'event': 'error',
                    'company_id': company_id,
                    'error': 'Failed to fetch agent numbers'
                })
            except:
                pass


# Global instance
agent_number_realtime_service = AgentNumberRealtimeService()
