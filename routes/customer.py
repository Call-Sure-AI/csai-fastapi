from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
import asyncpg
import json
import logging

from app.db.postgres_client import get_db_pool
from handlers.conversation_handler import get_conversation_manager
from middleware.auth_middleware import verify_websocket_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversation", tags=["Conversation"])

@router.websocket("/ws/{call_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    call_id: str,
    agent_id: str = Query(...),
    token: str = Query(...),
    db_pool: asyncpg.Pool = Depends(get_db_pool)
):

    try:
        user_data = await verify_websocket_token(token)
        if not user_data:
            await websocket.close(code=4001, reason="Unauthorized")
            return
    except Exception as e:
        await websocket.close(code=4001, reason="Invalid token")
        return

    manager = get_conversation_manager(db_pool)
    
    try:
        await manager.connect(websocket, call_id, agent_id)

        await manager.send_message(call_id, {
            'type': 'connected',
            'call_id': call_id,
            'agent_id': agent_id,
            'message': 'WebSocket connection established'
        })

        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)

                await manager.handle_message(call_id, message_data)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for call {call_id}")
                break
            except json.JSONDecodeError:
                await manager.send_message(call_id, {
                    'type': 'error',
                    'message': 'Invalid JSON format'
                })
            except Exception as e:
                logger.error(f"Error in WebSocket for call {call_id}: {str(e)}")
                await manager.send_message(call_id, {
                    'type': 'error',
                    'message': f'Server error: {str(e)}'
                })
                
    except Exception as e:
        logger.error(f"Failed to establish WebSocket connection for call {call_id}: {str(e)}")
    finally:
        manager.disconnect(call_id)

@router.get("/active-calls")
async def get_active_calls(
    db_pool: asyncpg.Pool = Depends(get_db_pool)
):
    """Get list of active calls"""
    manager = get_conversation_manager(db_pool)
    active_calls = list(manager.active_connections.keys())
    return {"active_calls": active_calls, "count": len(active_calls)}
