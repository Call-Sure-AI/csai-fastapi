from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from middleware.auth_middleware import get_current_user
from app.models.schemas import UserResponse
from app.utils.activity_logger import ActivityLogger
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/activity", tags=["activities"])

@router.get("", response_model=List[Dict[str, Any]])
async def get_user_activity(
    current_user: UserResponse = Depends(get_current_user),
    limit: Optional[int] = Query(50, description="Number of activities to return"),
    offset: Optional[int] = Query(0, description="Number of activities to skip"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type")
):
    """Get activity log for current user"""
    try:
        activities = await ActivityLogger.get_user_activity(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            entity_type=entity_type
        )
        
        return activities
    except Exception as e:
        logger.error(f"Error fetching user activity: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")