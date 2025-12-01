from fastapi import APIRouter, Depends
from middleware.auth_middleware import get_current_user
from app.models.schemas import UserResponse
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["users"])

class UserIdResponse(BaseModel):
    user_id: str

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get current authenticated user information
    """
    return current_user

@router.get("/me/id", response_model=UserIdResponse)
async def get_current_user_id(
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Get current authenticated user ID only
    """
    return UserIdResponse(user_id=current_user.id)