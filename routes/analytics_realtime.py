from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.analytics_realtime_service import analytics_realtime_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics")


@router.websocket("/ws/{company_id}")
async def websocket_analytics_endpoint(
    websocket: WebSocket,
    company_id: str
):
    """
    WebSocket endpoint for real-time analytics updates
    
    Frontend connects to: ws://your-domain/api/analytics/ws/{company_id}
    """
    await analytics_realtime_service.connect(websocket, company_id)
    
    try:
        # Keep connection alive and wait for messages
        while True:
            # Receive ping/pong or client messages
            data = await websocket.receive_text()
            
            # Handle client ping
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from analytics stream: {company_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        analytics_realtime_service.disconnect(websocket, company_id)


@router.get("/current/{company_id}")
async def get_current_analytics(company_id: str):
    """
    REST endpoint to get current analytics (non-WebSocket)
    """
    from app.db.postgres_client import get_db_connection
    
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
            return dict(row)
        else:
            return {"message": "No analytics data available"}
