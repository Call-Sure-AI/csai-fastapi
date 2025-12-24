from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.db.postgres_client import get_db_connection
from datetime import datetime, timedelta
import logging
import json
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-stats")


def serialize_row(row_dict: dict) -> dict:
    """Convert database row to JSON-serializable dict"""
    result = {}
    for key, value in row_dict.items():
        if hasattr(value, 'isoformat'):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


async def get_weekly_agent_stats(company_id: str):
    """Get agent call statistics for the current week"""
    async with await get_db_connection() as conn:
        # Calculate start of current week (Monday)
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        
        rows = await conn.fetch("""
            SELECT 
                an.agent_id,
                an.agent_name,
                COALESCE(a.name, an.agent_name) as agent_display_name,
                COUNT(c.id) as total_calls,
                COUNT(CASE WHEN c.status = 'completed' THEN 1 END) as completed_calls,
                COUNT(CASE WHEN c.status = 'failed' THEN 1 END) as failed_calls,
                AVG(c.duration) as avg_duration,
                SUM(c.cost) as total_cost
            FROM public."AgentNumber" an
            LEFT JOIN public."Agent" a ON an.agent_id = a.id
            LEFT JOIN public."Call" c ON c.from_number = an.phone_number 
                AND c.created_at >= $2
            WHERE an.company_id = $1
            GROUP BY an.agent_id, an.agent_name, a.name
            ORDER BY total_calls DESC
        """, company_id, start_of_week)
        
        return [serialize_row(dict(row)) for row in rows]


@router.websocket("/ws/{company_id}")
async def websocket_agent_stats_endpoint(
    websocket: WebSocket,
    company_id: str
):
    """
    WebSocket endpoint for real-time agent statistics
    
    Sends weekly stats and updates every 30 seconds
    Frontend connects to: ws://your-domain/api/agent-stats/ws/{company_id}
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for agent stats: {company_id}")
    
    try:
        # Send initial stats immediately
        stats = await get_weekly_agent_stats(company_id)

        for stat in stats:
            if stat["total_calls"]:
                stat["success_rate"] = (stat["completed_calls"] / stat["total_calls"])*100
            else:
                stat["success_rate"] = 0

        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        
        await websocket.send_json({
            'event': 'agent_stats_current',
            'company_id': company_id,
            'week_start': start_of_week.isoformat(),
            'data': stats,
            'count': len(stats),
            'timestamp': datetime.now().isoformat()
        })
        logger.info(f"Sent initial agent stats to {company_id}")
        
        # Keep connection alive and refresh every 30 seconds
        while True:
            try:
                # Wait for client message or timeout after 30 seconds
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                if data == "ping":
                    await websocket.send_text("pong")
                elif data == "refresh":
                    # Manual refresh requested
                    stats = await get_weekly_agent_stats(company_id)
                    await websocket.send_json({
                        'event': 'agent_stats_updated',
                        'company_id': company_id,
                        'week_start': start_of_week.isoformat(),
                        'data': stats,
                        'count': len(stats),
                        'timestamp': datetime.now().isoformat()
                    })
                    logger.info(f"Sent refreshed agent stats to {company_id}")
                    
            except asyncio.TimeoutError:
                # Auto-refresh every 30 seconds
                stats = await get_weekly_agent_stats(company_id)
                await websocket.send_json({
                    'event': 'agent_stats_updated',
                    'company_id': company_id,
                    'week_start': start_of_week.isoformat(),
                    'data': stats,
                    'count': len(stats),
                    'timestamp': datetime.now().isoformat()
                })
                logger.info(f"Auto-refreshed agent stats for {company_id}")
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from agent stats: {company_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                'event': 'error',
                'company_id': company_id,
                'error': str(e)
            })
        except:
            pass


@router.get("/weekly/{company_id}")
async def get_weekly_stats_rest(company_id: str):
    """
    REST endpoint to get weekly agent statistics (non-WebSocket)
    """
    try:
        stats = await get_weekly_agent_stats(company_id)
        
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        
        return {
            "company_id": company_id,
            "week_start": start_of_week.isoformat(),
            "week_end": (start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)).isoformat(),
            "stats": stats,
            "count": len(stats),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching weekly stats: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to fetch weekly statistics")
