from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.agent_number_realtime_service import agent_number_realtime_service
from app.db.postgres_client import get_db_connection
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-numbers")


@router.websocket("/ws/{company_id}")
async def websocket_agent_numbers_endpoint(
    websocket: WebSocket,
    company_id: str
):
    """
    WebSocket endpoint for real-time agent number updates
    
    Frontend connects to: ws://your-domain/api/agent-numbers/ws/{company_id}
    """
    await agent_number_realtime_service.connect(websocket, company_id)
    
    try:
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            
            if data == "ping":
                await websocket.send_text("pong")
            elif data == "refresh":
                # Re-send current agent numbers
                await agent_number_realtime_service.send_current_agent_numbers(websocket, company_id)
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from agent numbers stream: {company_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        agent_number_realtime_service.disconnect(websocket, company_id)


@router.get("/current/{company_id}")
async def get_current_agent_numbers(company_id: str):
    """
    REST endpoint to get current agent numbers (non-WebSocket)
    """
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
            return {
                "company_id": company_id,
                "agent_numbers": [dict(row) for row in rows],
                "count": len(rows)
            }
        else:
            return {
                "company_id": company_id,
                "agent_numbers": [],
                "count": 0,
                "message": "No agent numbers found"
            }
