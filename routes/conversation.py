from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.models.schemas import UserResponse
from handlers.conversation_handler import get_conversation_manager, ConversationManager
from middleware.auth_middleware import get_current_user
import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/conversations", tags=["Conversation"])


def get_manager() -> ConversationManager:
    return get_conversation_manager()


@router.get("/", response_model=List[Dict[str, Any]])
async def get_all_conversations(
    current_user: UserResponse = Depends(get_current_user),
    company_id: Optional[str] = Query(None, description="Filter by company ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    manager: ConversationManager = Depends(get_manager)
):

    try:
        logger.info(f"get_all_conversations called by user: {current_user.id}")
        logger.info(f"current_user.id: {current_user.id}, type: {type(current_user.id)}")
        
        conversations = []
        for call_id, conv_data in manager.conversation_data.items():

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
    return {
        "message": "Conversation router is working!",
        "status": "success"
    }


@router.get("/test-manager")
async def test_manager(
    manager: ConversationManager = Depends(get_manager)
):
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


@router.post("/create", status_code=201)
async def create_conversation(
    call_id: str = Query(..., description="Unique call ID"),
    agent_id: str = Query(..., description="Agent ID"),
    user_phone: Optional[str] = Query(None, description="User phone number"),
    current_user: UserResponse = Depends(get_current_user),
    manager: ConversationManager = Depends(get_manager)
):

    try:
        logger.info(f"Creating conversation: call_id={call_id}, agent_id={agent_id}, user={current_user.id}")

        if call_id in manager.conversation_data:
            raise HTTPException(status_code=400, detail=f"Conversation {call_id} already exists")

        manager.conversation_data[call_id] = {
            'call_id': call_id,
            'agent_id': agent_id,
            'start_time': datetime.utcnow(),
            'messages': [],
            'transcript': '',
            'user_phone': user_phone,
            'status': 'active',
            'created_by': current_user.id,
            'created_by_name': current_user.name,
            'company_id': None
        }
        
        logger.info(f"Conversation {call_id} created successfully")
        
        return {
            "status": "success",
            "message": "Conversation created",
            "conversation": {
                "call_id": call_id,
                "agent_id": agent_id,
                "status": "active",
                "user_phone": user_phone,
                "created_by": current_user.name,
                "start_time": manager.conversation_data[call_id]['start_time'].isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{call_id}/message", status_code=201)
async def add_message_to_conversation(
    call_id: str,
    message_type: str = Query(..., description="Message type: transcript_update, user_joined, agent_response"),
    speaker: Optional[str] = Query(None, description="Speaker: agent or user"),
    text: Optional[str] = Query(None, description="Message text"),
    phone: Optional[str] = Query(None, description="User phone (for user_joined)"),
    current_user: UserResponse = Depends(get_current_user),
    manager: ConversationManager = Depends(get_manager)
):

    try:
        logger.info(f"Adding message to conversation {call_id}: type={message_type}")
        
        if call_id not in manager.conversation_data:
            raise HTTPException(status_code=404, detail=f"Conversation {call_id} not found")

        message_data = {'type': message_type}
        
        if message_type == 'transcript_update':
            if not text or not speaker:
                raise HTTPException(status_code=400, detail="text and speaker required for transcript_update")
            message_data['transcript'] = text
            message_data['speaker'] = speaker
            
        elif message_type == 'user_joined':
            if not phone:
                raise HTTPException(status_code=400, detail="phone required for user_joined")
            message_data['phone'] = phone
            message_data['user_details'] = {}
            
        elif message_type == 'agent_response':
            if not text:
                raise HTTPException(status_code=400, detail="text required for agent_response")
            message_data['response'] = text
            message_data['action'] = 'send_message'

        await manager.handle_message(call_id, message_data)
        
        return {
            "status": "success",
            "message": "Message added to conversation",
            "call_id": call_id,
            "message_type": message_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_message_to_conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{call_id}/end", status_code=200)
async def end_conversation_with_outcome(
    call_id: str,
    outcome: str = Query("completed", description="Outcome: completed, callback_requested, not_interested"),
    current_user: UserResponse = Depends(get_current_user),
    manager: ConversationManager = Depends(get_manager)
):
    try:
        logger.info(f"Ending conversation {call_id} with outcome: {outcome}")
        
        if call_id not in manager.conversation_data:
            raise HTTPException(status_code=404, detail=f"Conversation {call_id} not found")

        message_data = {
            'type': 'call_ended',
            'outcome': outcome
        }
        
        await manager.handle_message(call_id, message_data)
        
        return {
            "status": "success",
            "message": "Conversation ended",
            "call_id": call_id,
            "outcome": outcome
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in end_conversation_with_outcome: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/active", response_model=List[Dict[str, Any]])
async def get_active_conversations(
    current_user: UserResponse = Depends(get_current_user),
    manager: ConversationManager = Depends(get_manager)
):
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
    try:
        logger.info(f"Broadcasting message to call: {call_id} by user: {current_user.id}")
        
        if call_id not in manager.active_connections:
            raise HTTPException(status_code=404, detail=f"Active connection for call {call_id} not found")

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
    try:
        logger.info(f"Ending conversation {call_id} by user: {current_user.id}")
        
        if call_id not in manager.conversation_data:
            raise HTTPException(status_code=404, detail=f"Conversation {call_id} not found")

        if call_id in manager.conversation_data:
            del manager.conversation_data[call_id]

        if call_id in manager.active_connections:
            manager.disconnect(call_id)
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in end_conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
