from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from handlers.conversation_handler import get_conversation_manager
from middleware.auth_middleware import get_current_user_ws
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Create router with correct prefix (matching agent.py pattern)
router = APIRouter(prefix="/ws", tags=["WebSocket"])


# Dependency to get conversation manager (matching agent.py pattern)
def get_manager():
    """Dependency to get conversation manager instance"""
    return get_conversation_manager()


@router.websocket("/conversations/{call_id}")
async def conversation_websocket(
    websocket: WebSocket,
    call_id: str,
    agent_id: str = Query(..., description="Agent ID for the conversation"),
    token: str = Query(..., description="JWT authentication token")
):
    """
    WebSocket endpoint for real-time conversation handling
    Uses get_current_user_ws for authentication (WebSocket equivalent of get_current_user)
    """
    manager = get_manager()
    current_user = None
    
    try:
        # Authenticate user using get_current_user_ws (WebSocket version)
        logger.info(f"Authenticating WebSocket for call {call_id}")
        current_user = await get_current_user_ws(websocket, token)
        logger.info(f"User {current_user.id} ({current_user.email}) authenticated for call {call_id}")
        
        # Connect to conversation
        await manager.connect(websocket, call_id, agent_id)
        
        # Send connection confirmation with user details
        await manager.send_message(call_id, {
            'type': 'connection_established',
            'call_id': call_id,
            'agent_id': agent_id,
            'user': {
                'id': current_user.id,
                'name': current_user.name,
                'email': current_user.email,
                'role': current_user.role
            },
            'timestamp': datetime.utcnow().isoformat()
        })
        
        logger.info(f"WebSocket connected: call={call_id}, user={current_user.id}")
        
        # Handle incoming messages
        while True:
            try:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Add user context to message (like we have current_user in HTTP routes)
                message_data['user_id'] = current_user.id
                message_data['user_email'] = current_user.email
                message_data['user_name'] = current_user.name
                
                logger.debug(f"Message from {current_user.email}: {message_data.get('type')}")
                
                # Process message
                await manager.handle_message(call_id, message_data)
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from user {current_user.id}: {str(e)}")
                await manager.send_message(call_id, {
                    'type': 'error',
                    'message': 'Invalid message format. Expected JSON.',
                    'timestamp': datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        logger.info(f"User {current_user.email if current_user else 'unknown'} disconnected from call {call_id}")
        manager.disconnect(call_id)
        
    except Exception as e:
        logger.error(f"WebSocket error for call {call_id}: {str(e)}", exc_info=True)
        if call_id in manager.active_connections:
            manager.disconnect(call_id)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass


@router.websocket("/monitor/{company_id}")
async def monitor_websocket(
    websocket: WebSocket,
    company_id: str,
    token: str = Query(..., description="JWT authentication token")
):
    """
    WebSocket endpoint for monitoring company conversations
    Uses get_current_user_ws for authentication
    """
    manager = get_manager()
    monitoring_key = None
    current_user = None
    
    try:
        # Authenticate user using get_current_user_ws
        logger.info(f"Authenticating monitor for company {company_id}")
        current_user = await get_current_user_ws(websocket, token)
        logger.info(f"User {current_user.id} (role: {current_user.role}) authenticated for monitoring {company_id}")
        
        # Accept connection after authentication
        await websocket.accept()
        
        # Add to monitoring connections
        monitoring_key = f"monitor_{company_id}_{current_user.id}"
        manager.monitoring_connections[monitoring_key] = websocket
        
        # Send connection confirmation
        await websocket.send_json({
            'type': 'monitor_connected',
            'company_id': company_id,
            'user': {
                'id': current_user.id,
                'name': current_user.name,
                'email': current_user.email,
                'role': current_user.role
            },
            'timestamp': datetime.utcnow().isoformat()
        })
        
        logger.info(f"Monitor connected: {monitoring_key}")
        
        # Handle commands
        while True:
            try:
                data = await websocket.receive_text()
                command = json.loads(data)
                
                command_type = command.get('type')
                logger.debug(f"Monitor command from {current_user.email}: {command_type}")
                
                if command_type == 'ping':
                    await websocket.send_json({
                        'type': 'pong',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                elif command_type == 'get_active_calls':
                    active_calls = [
                        {
                            'call_id': call_id,
                            'agent_id': data.get('agent_id'),
                            'status': data.get('status'),
                            'start_time': data.get('start_time', '').isoformat() if data.get('start_time') else None
                        }
                        for call_id, data in manager.conversation_data.items()
                        if data.get('status') in ['connected', 'active']
                    ]
                    await websocket.send_json({
                        'type': 'active_calls',
                        'calls': active_calls,
                        'count': len(active_calls),
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from monitor {current_user.email}: {str(e)}")
                await websocket.send_json({
                    'type': 'error',
                    'message': 'Invalid command format',
                    'timestamp': datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        logger.info(f"Monitor disconnected: {monitoring_key}")
        
    except Exception as e:
        logger.error(f"Monitor WebSocket error: {str(e)}", exc_info=True)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
        
    finally:
        if monitoring_key and monitoring_key in manager.monitoring_connections:
            del manager.monitoring_connections[monitoring_key]
            logger.info(f"Cleaned up monitor: {monitoring_key}")


@router.websocket("/analytics/{company_id}")
async def analytics_websocket(
    websocket: WebSocket,
    company_id: str,
    token: str = Query(..., description="JWT authentication token")
):
    """WebSocket endpoint for real-time analytics updates"""
    connection_key = None
    manager = get_manager()
    current_user = None
    
    try:
        # Authenticate user
        current_user = await get_current_user_ws(websocket, token)
        logger.info(f"User {current_user.id} authenticated for analytics {company_id}")
        
        # Accept connection
        await websocket.accept()
        
        connection_key = f"analytics_{company_id}_{current_user.id}"
        manager.active_connections[connection_key] = websocket
        
        # Send confirmation
        await websocket.send_json({
            'type': 'analytics_connected',
            'company_id': company_id,
            'user': {
                'id': current_user.id,
                'name': current_user.name
            },
            'timestamp': datetime.utcnow().isoformat()
        })
        
        logger.info(f"Analytics connected: {connection_key}")
        
        # Handle commands
        while True:
            try:
                data = await websocket.receive_text()
                command = json.loads(data)
                
                if command.get('type') == 'ping':
                    await websocket.send_json({
                        'type': 'pong',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                elif command.get('type') == 'refresh':
                    await websocket.send_json({
                        'type': 'analytics_refreshed',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        logger.info(f"Analytics disconnected: {connection_key}")
        
    except Exception as e:
        logger.error(f"Analytics WebSocket error: {str(e)}", exc_info=True)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
        
    finally:
        if connection_key and connection_key in manager.active_connections:
            del manager.active_connections[connection_key]


@router.websocket("/notifications/{user_id}")
async def notifications_websocket(
    websocket: WebSocket,
    user_id: str,
    token: str = Query(..., description="JWT authentication token")
):
    """WebSocket endpoint for real-time user notifications"""
    connection_key = None
    manager = get_manager()
    current_user = None
    
    try:
        # Authenticate user
        current_user = await get_current_user_ws(websocket, token)
        
        # Verify user is requesting their own notifications
        if current_user.id != user_id:
            logger.warning(f"User {current_user.id} attempted to access notifications for {user_id}")
            await websocket.close(code=1008, reason="Unauthorized: Can only access own notifications")
            return
        
        logger.info(f"User {current_user.id} authenticated for notifications")
        
        # Accept connection
        await websocket.accept()
        
        connection_key = f"notifications_{user_id}"
        manager.active_connections[connection_key] = websocket
        
        # Send confirmation
        await websocket.send_json({
            'type': 'notifications_connected',
            'user': {
                'id': current_user.id,
                'name': current_user.name
            },
            'timestamp': datetime.utcnow().isoformat()
        })
        
        logger.info(f"Notifications connected: {connection_key}")
        
        # Handle commands
        while True:
            try:
                data = await websocket.receive_text()
                command = json.loads(data)
                
                if command.get('type') == 'mark_read':
                    notification_id = command.get('notification_id')
                    logger.info(f"Marking notification {notification_id} as read for {user_id}")
                    await websocket.send_json({
                        'type': 'notification_marked_read',
                        'notification_id': notification_id,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                elif command.get('type') == 'ping':
                    await websocket.send_json({
                        'type': 'pong',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        logger.info(f"Notifications disconnected: {connection_key}")
        
    except Exception as e:
        logger.error(f"Notifications WebSocket error: {str(e)}", exc_info=True)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
        
    finally:
        if connection_key and connection_key in manager.active_connections:
            del manager.active_connections[connection_key]


@router.get("/test")
async def test_websocket_router():
    """Test endpoint to verify WebSocket router is working - NO AUTH REQUIRED"""
    return {
        "message": "WebSocket router is working!",
        "status": "success",
        "endpoints": [
            "/ws/conversations/{call_id}",
            "/ws/monitor/{company_id}",
            "/ws/analytics/{company_id}",
            "/ws/notifications/{user_id}"
        ]
    }
