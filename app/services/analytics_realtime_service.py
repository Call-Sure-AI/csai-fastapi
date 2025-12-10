import asyncio
import asyncpg
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket
from app.db.postgres_client import get_db_connection  # Use existing connection
import os

logger = logging.getLogger(__name__)


class AnalyticsRealtimeService:
    """Service to manage real-time analytics updates via WebSocket"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.listener_conn: asyncpg.Connection = None
        self.listener_task: asyncio.Task = None
        
    async def start(self):
        """Start listening for PostgreSQL notifications"""
        try:
            from config import config
            env = os.getenv('FLASK_ENV', 'development')
            app_config = config.get(env, config['default'])
            
            # Create dedicated connection ONLY for LISTEN
            self.listener_conn = await asyncpg.connect(app_config.DATABASE_URL)
            
            # Start listening to analytics_updates channel
            await self.listener_conn.add_listener('analytics_updates', self._handle_notification)
            
            logger.info("✓ Analytics real-time service started - listening for updates")
            
        except Exception as e:
            logger.error(f"Failed to start analytics real-time service: {e}", exc_info=True)
            # Set listener_conn to None so we know it failed
            self.listener_conn = None

    def serialize_row(self, row_dict: dict) -> dict:
        """Convert database row to JSON-serializable dict"""
        result = {}
        for key, value in row_dict.items():
            if hasattr(value, 'isoformat'):
                result[key] = value.isoformat()
            else:
                result[key] = value
        return result

    async def stop(self):
        """Stop listening and close connection"""
        if self.listener_conn:
            try:
                await self.listener_conn.remove_listener('analytics_updates', self._handle_notification)
                await self.listener_conn.close()
                logger.info("Analytics real-time service stopped")
            except Exception as e:
                logger.error(f"Error stopping analytics service: {e}")
    
    async def _handle_notification(self, connection, pid, channel, payload):
        """Handle PostgreSQL NOTIFY event"""
        try:
            data = json.loads(payload)
            company_id = data.get('company_id')
            
            logger.info(f"📊 Analytics updated for company {company_id}")
            
            # Broadcast to all connected clients for this company
            if company_id in self.active_connections:
                await self.broadcast_to_company(company_id, data)
                
        except Exception as e:
            logger.error(f"Error handling notification: {e}")
    
    async def connect(self, websocket: WebSocket, company_id: str):
        """Register a new WebSocket connection"""
        await websocket.accept()
        
        if company_id not in self.active_connections:
            self.active_connections[company_id] = set()
        
        self.active_connections[company_id].add(websocket)
        logger.info(f"✓ WebSocket connected for company {company_id}")
        
        # Send current analytics data immediately upon connection
        await self.send_current_analytics(websocket, company_id)
    
    def disconnect(self, websocket: WebSocket, company_id: str):
        """Unregister a WebSocket connection"""
        if company_id in self.active_connections:
            self.active_connections[company_id].discard(websocket)
            if not self.active_connections[company_id]:
                del self.active_connections[company_id]
        
        logger.info(f"WebSocket disconnected for company {company_id}")
    
    async def broadcast_to_company(self, company_id: str, data: dict):
        """Broadcast analytics update to all connections for a company"""
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
    
    async def send_current_analytics(self, websocket: WebSocket, company_id: str):
        """Send current analytics data to a newly connected client"""
        try:
            async with await get_db_connection() as conn:
                row = await conn.fetchrow("""
                    SELECT 
                        company_id, total_calls, completed_calls, failed_calls,
                        resolution_rate, total_bookings, pending_bookings,
                        confirmed_bookings, cancelled_bookings, avg_call_duration,
                        total_call_cost, avg_quality_score, updated_at
                    FROM public."Analytics"
                    WHERE company_id = $1
                """, company_id)
                
                if row:
                    data = {
                        'event': 'analytics_current',
                        'company_id': company_id,
                        'data': self.serialize_row(dict(row))
                    }
                    await websocket.send_json(data)
                    logger.info(f"Sent current analytics to company {company_id}")
                else:
                    await websocket.send_json({
                        'event': 'analytics_current',
                        'company_id': company_id,
                        'data': {
                            'message': 'No analytics data yet',
                            'total_calls': 0,
                            'completed_calls': 0,
                            'failed_calls': 0,
                            'resolution_rate': 0.0,
                            'total_bookings': 0,
                            'updated_at': None
                        }
                    })
                    logger.info(f"Sent 'no data' message to company {company_id}")
        
        except Exception as e:
            logger.error(f"Error sending current analytics: {e}", exc_info=True)
            try:
                await websocket.send_json({
                    'event': 'error',
                    'company_id': company_id,
                    'error': 'Failed to fetch analytics data'
                })
            except:
                pass

# Global instance
analytics_realtime_service = AnalyticsRealtimeService()
