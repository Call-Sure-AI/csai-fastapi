from fastapi import Depends, HTTPException, status, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
import jwt
from jwt import InvalidTokenError, ExpiredSignatureError
import os
from typing import Optional
from app.db.postgres_client import postgres_client
from app.models.schemas import UserResponse
import logging
from config import config
from fastapi import HTTPException
from fastapi import WebSocket

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

env = os.getenv('FLASK_ENV', 'development')
app_config = config.get(env, config['default'])()

logger = logging.getLogger(__name__)
security = HTTPBearer()

async def get_current_user_ws(websocket: WebSocket, token: str) -> UserResponse:
    try:
        payload = jwt.decode(token, app_config.JWT_SECRET, algorithms=["HS256"])
        
        user_id = payload.get("id")
        
        if user_id is None:
            raise InvalidTokenError("Invalid token payload: missing user id")

        query = 'SELECT * FROM "User" WHERE id = $1'
        user = await postgres_client.client.execute_query_one(query, (user_id,))
        
        if not user:
            raise InvalidTokenError("User not found")

        role = await get_user_role(user_id)
        
        logger.info(f"WebSocket authenticated: user_id={user_id}, email={user['email']}, role={role}")
        
        return UserResponse(
            id=str(user['id']),
            name=user['name'],
            email=user['email'],
            image=user.get('image'),
            role=role
        )
        
    except ExpiredSignatureError as e:
        logger.warning(f"WebSocket auth failed: Token expired")
        await websocket.close(code=1008, reason="Authentication failed: Token expired")
        raise
    except InvalidTokenError as e:
        logger.warning(f"WebSocket auth failed: {str(e)}")
        await websocket.close(code=1008, reason=f"Authentication failed: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"WebSocket auth error: {e}", exc_info=True)
        await websocket.close(code=1008, reason="Authentication failed")
        raise

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserResponse:

    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            app_config.JWT_SECRET,
            algorithms=["HS256"]
        )
        
        user_id = payload.get("id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user id"
            )

        query = 'SELECT * FROM "User" WHERE id = $1'
        user = await postgres_client.client.execute_query_one(query, (user_id,))
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        role = await get_user_role(user_id)

        return UserResponse(
            id=str(user['id']),
            name=user['name'],
            email=user['email'],
            image=user.get('image'),
            role=role
        )
        
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )


async def get_user_role(user_id: str) -> str:

    try:

        query = 'SELECT COUNT(*) as count FROM "Company" WHERE user_id = $1'
        result = await postgres_client.client.execute_query_one(query, (user_id,))
        
        if result and result['count'] > 0:
            return 'admin'

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

async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))
) -> Optional[UserResponse]:

    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except:
        return None


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        token = credentials.credentials
        payload = jwt.decode(token, app_config.JWT_SECRET, algorithms=["HS256"])  # Use config
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def verify_websocket_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, app_config.JWT_SECRET, algorithms=["HS256"])  # Use config
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")