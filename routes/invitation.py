from fastapi import APIRouter, HTTPException, Depends, Path, Body
from typing import Dict, Any, Optional
from app.models.schemas import InvitationCreate, InvitationAccept, Invitation, UserResponse, SendInvitationEmailRequest
from handlers.invitation_handler import InvitationHandler
from middleware.auth_middleware import get_current_user
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/invitations", tags=["invitations"])
invitation_handler = InvitationHandler()

@router.post("/generate")
async def generate_invitation(
    invitation_data: InvitationCreate,
    current_user: UserResponse = Depends(get_current_user),
    invitation_handler: InvitationHandler = Depends(InvitationHandler)
):
    try:
        user_id = current_user.id
        result = await invitation_handler.generate_invitation(invitation_data, user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error in generate_invitation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/validate/{token}")
async def validate_invitation(
    token: str = Path(..., description="Invitation token"),
    invitation_handler: InvitationHandler = Depends(InvitationHandler)
):
    try:
        result = await invitation_handler.validate_invitation(token)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=404 if "not found" in str(e).lower() else 400, 
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in validate_invitation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/accept/{token}")
async def accept_invitation(
    token: str = Path(..., description="Invitation token"),
    acceptance_data: InvitationAccept = Body(...)
):
    try:
        result = await invitation_handler.accept_invitation(token, acceptance_data)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=404 if "not found" in str(e).lower() else 400, 
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in accept_invitation: {e}")
        if "development" in str(os.getenv('NODE_ENV', '')).lower():
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/list/{company_id}")
async def list_invitations(
    company_id: str = Path(..., description="Company ID"),
    current_user: UserResponse = Depends(get_current_user),
    invitation_handler: InvitationHandler = Depends(InvitationHandler)
):
    try:
        user_id = current_user.id
        result = await invitation_handler.list_invitations(company_id, user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error in list_invitations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/list-accepted/{company_id}")
async def list_accepted_invitations(
    company_id: str = Path(..., description="Company ID"),
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        user_id = current_user.id
        result = await invitation_handler.list_accepted_invitations(company_id, user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error in list_accepted_invitations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/list-expired/{company_id}")
async def list_expired_invitations(
    company_id: str = Path(..., description="Company ID"),
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        user_id = current_user.id
        result = await invitation_handler.list_expired_invitations(company_id, user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error in list_expired_invitations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{invitation_id}")
async def delete_invitation(
    invitation_id: str = Path(..., description="Invitation ID"),
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        user_id = current_user.id
        result = await invitation_handler.delete_invitation(invitation_id, user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error in delete_invitation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ADD this new endpoint as a workaround
@router.post("/{invitation_id}/delete")
async def delete_invitation_via_post(
    invitation_id: str = Path(..., description="Invitation ID"),
    current_user: UserResponse = Depends(get_current_user)
):
    """Alternative endpoint to delete invitation using POST (workaround for CORS issues)"""
    try:
        user_id = current_user.id
        result = await invitation_handler.delete_invitation(invitation_id, user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error in delete_invitation_via_post: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.options("/{invitation_id}")
async def options_invitation(invitation_id: str):
    """Handle OPTIONS request for CORS preflight"""
    return {"message": "OK"}

@router.post("/send-email")
async def send_invitation_email(
    request: SendInvitationEmailRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        user_id = current_user.id
        result = await invitation_handler.send_invitation_email(request.invitation_id, user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Error in send_invitation_email: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")