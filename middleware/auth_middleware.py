from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os
from typing import Optional
from app.db.postgres_client import postgres_client
from app.models.schemas import UserResponse

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserResponse:
    """
    Extract user from JWT token and fetch user from DB.
    """
    token = credentials.credentials
    try:
        # Decode the JWT token
        payload = jwt.decode(
            token,
            os.getenv("JWT_SECRET", "your-secret-key"),
            algorithms=["HS256"]
        )
        user_id = payload.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user id"
            )
        
        # Fetch user from DB using the correct table name with quotes
        query = 'SELECT * FROM "User" WHERE id = $1'
        user = await postgres_client.client.execute_query_one(query, (user_id,))
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Determine user role based on company ownership
        role = await _get_user_role(user_id)
        
        # Return UserResponse object
        return UserResponse(
            id=str(user['id']),
            name=user['name'],
            email=user['email'],
            image=user.get('image'),
            role=role
        )
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    except Exception as e:
        # Log the error for debugging
        print(f"Auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

async def _get_user_role(user_id: str) -> str:
    """Helper function to determine user role"""
    try:
        # Check if user owns any companies
        query = 'SELECT COUNT(*) as count FROM "Company" WHERE user_id = $1'
        result = await postgres_client.client.execute_query_one(query, (user_id,))
        
        if result and result['count'] > 0:
            return 'admin'
        
        # Check company memberships
        membership_query = '''
            SELECT role FROM "CompanyMember" 
            WHERE user_id = $1 
            ORDER BY created_at DESC 
            LIMIT 1
        '''
        membership = await postgres_client.client.execute_query_one(membership_query, (user_id,))
        
        if membership:
            return membership['role']
        
        return 'member'
    except:
        return 'member'

# Optional: Create a dependency that doesn't require authentication
async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))
) -> Optional[UserResponse]:
    """
    Get current user if token is provided, otherwise return None
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except:
        return None