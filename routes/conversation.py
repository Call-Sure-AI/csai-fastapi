from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from typing import List, Optional, Dict, Any
from app.models.schemas import UserResponse
from handlers.conversation_handler import get_conversation_manager, ConversationManager
from middleware.auth_middleware import get_current_user
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Create router with correct prefix (matching agent.py pattern)
router = APIRouter(prefix="/conversations", tags=["Conversation"])


# Dependency to get conversation manager (matching agent.py pattern)
def get_manager() -> ConversationManager:
    """Dependency to get conversation manager instance"""
    return get_conversation_manager()


@router.get("/", response_model=List[Dict[str, Any]])
async def get_all_conversations(
    current_user: UserResponse = Depends(get_current_user),
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    manager: ConversationManager = Depends(get_manager)
):
    """
    Get all conversations for the current user
    Uses get_current_user dependency like agent routes
    """
    try:
        logger.info(f"get_all_conversations called by user: {current_user.id}")
        logger.info(f"current_user.id: {current_user.id}, type: {type(current_user.id)}")
        
        conversations = []
        for call_id, conv_data in manager.conversation_data.items():
            # Apply filters
            if company_id and conv_data.get('company_id') != company_id:
                continue
            if status and conv_data.get('status') != status:
                continue
                
            conversations.append({
                'call_id': call_id,
                'agent_id': conv_data.get('agent_id'),
                'status': conv_data.get('status'),
                'start_time': conv_data.get('start_time').isoformat() if conv_data.get('start_time') else None,
                'user_phone': conv_data.get('user_phone'),
                'duration': conv_data.get('duration', 0)
            })
        
        logger.info(f"Successfully retrieved {len(conversations)} conversations")
        return conversations
        
    except Exception as e:
        logger.error(f"Error in get_all_conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/test")
async def test_conversation_router():
    """Test endpoint to verify conversation router is working - NO AUTH REQUIRED"""
    return {
        "message": "Conversation router is working!",
        "status": "success"
    }


@router.get("/test-manager")
async def test_manager(
    manager: ConversationManager = Depends(get_manager)
):
    """Test conversation manager - NO AUTH REQUIRED"""
    try:
        active_count = len(manager.active_connections)
        conversation_count = len(manager.conversation_data)
        
        return {
            "status": "success",
            "message": "Conversation manager is working",
            "active_connections": active_count,
            "active_conversations": conversation_count
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Manager test failed: {str(e)}"
        }


@router.get("/active", response_model=List[Dict[str, Any]])
async def get_active_conversations(
    current_user: UserResponse = Depends(get_current_user),
    manager: ConversationManager = Depends(get_manager)
):
    """Get all currently active conversations"""
    try:
        logger.info(f"get_active_conversations called by user: {current_user.id}")
        
        active_conversations = [
            {
                'call_id': call_id,
                'agent_id': conv_data.get('agent_id'),
                'status': conv_data.get('status'),
                'start_time': conv_data.get('start_time').isoformat() if conv_data.get('start_time') else None,
                'user_phone': conv_data.get('user_phone')
            }
            for call_id, conv_data in manager.conversation_data.items()
            if conv_data.get('status') in ['connected', 'active']
        ]
        
        logger.info(f"Found {len(active_conversations)} active conversations")
        return active_conversations
        
    except Exception as e:
        logger.error(f"Error in get_active_conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{call_id}", response_model=Dict[str, Any])
async def get_conversation_by_id(
    call_id: str,
    current_user: UserResponse = Depends(get_current_user),
    manager: ConversationManager = Depends(get_manager)
):
    """Get a specific conversation by call ID"""
    try:
        logger.info(f"get_conversation_by_id called for call: {call_id} by user: {current_user.id}")
        
        if call_id not in manager.conversation_data:
            raise HTTPException(status_code=404, detail=f"Conversation {call_id} not found")
        
        conv_data = manager.conversation_data[call_id]
        
        return {
            'call_id': call_id,
            'agent_id': conv_data.get('agent_id'),
            'status': conv_data.get('status'),
            'start_time': conv_data.get('start_time').isoformat() if conv_data.get('start_time') else None,
            'end_time': conv_data.get('end_time').isoformat() if conv_data.get('end_time') else None,
            'user_phone': conv_data.get('user_phone'),
            'duration': conv_data.get('duration', 0),
            'messages': conv_data.get('messages', []),
            'transcript': conv_data.get('transcript', '')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_conversation_by_id: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{call_id}/transcript")
async def get_conversation_transcript(
    call_id: str,
    current_user: UserResponse = Depends(get_current_user),
    manager: ConversationManager = Depends(get_manager)
):
    """Get the transcript of a specific conversation"""
    try:
        if call_id not in manager.conversation_data:
            raise HTTPException(status_code=404, detail=f"Conversation {call_id} not found")
        
        conv_data = manager.conversation_data[call_id]
        
        return {
            'call_id': call_id,
            'transcript': conv_data.get('transcript', ''),
            'messages': conv_data.get('messages', []),
            'duration': conv_data.get('duration', 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_conversation_transcript: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{call_id}/broadcast")
async def broadcast_to_conversation(
    call_id: str,
    message: Dict[str, Any],
    current_user: UserResponse = Depends(get_current_user),
    manager: ConversationManager = Depends(get_manager)
):
    """Broadcast a message to a specific conversation"""
    try:
        logger.info(f"Broadcasting message to call: {call_id} by user: {current_user.id}")
        
        if call_id not in manager.active_connections:
            raise HTTPException(status_code=404, detail=f"Active connection for call {call_id} not found")
        
        # Add user context
        message['sent_by'] = {
            'id': current_user.id,
            'name': current_user.name,
            'email': current_user.email
        }
        
        await manager.send_message(call_id, message)
        
        return {
            "status": "success",
            "message": "Message broadcasted successfully",
            "call_id": call_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in broadcast_to_conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{call_id}", status_code=204)
async def end_conversation(
    call_id: str,
    current_user: UserResponse = Depends(get_current_user),
    manager: ConversationManager = Depends(get_manager)
):
    """End a conversation"""
    try:
        logger.info(f"Ending conversation {call_id} by user: {current_user.id}")
        
        if call_id not in manager.active_connections:
            raise HTTPException(status_code=404, detail=f"Active conversation {call_id} not found")
        
        # Disconnect the conversation
        manager.disconnect(call_id)
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in end_conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
