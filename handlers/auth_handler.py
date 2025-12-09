import os
import jwt
import bcrypt
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from fastapi import HTTPException, Response, Request
from google.auth.transport import requests
from google.oauth2 import id_token
from app.db.postgres_client import postgres_client
from app.db.queries.auth_queries import AuthQueries
from app.db.queries.user_queries import UserQueries
from app.db.queries.account_queries import AccountQueries
#from app.db.queries.otp_queries import OTPQueries
from app.db.repositories.otp_repository import otp_repository
from app.db.queries.company_queries import CompanyQueries
from app.models.schemas import (
    GoogleAuthRequest, EmailCheckRequest, SignUpRequest, SignInRequest,
    GenerateOTPRequest, VerifyOTPRequest, AuthResponse, EmailCheckResponse,
    MessageResponse, UserResponse
)
from .email_handler import email_handler
from app.db.repositories.otp_repository import otp_repository
from config import config

env = os.getenv('FLASK_ENV', 'development')
app_config = config.get(env, config['default'])()

class AuthHandler:
    
    @staticmethod
    async def google_auth(auth_request: GoogleAuthRequest, response: Response) -> AuthResponse:
        try:
            new_user = False
            
            # Verify the ID token
            try:
                idinfo = id_token.verify_oauth2_token(
                    auth_request.idToken, 
                    requests.Request(), 
                    os.getenv('GOOGLE_CLIENT_ID')
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid Google token: {str(e)}")
            
            google_id = idinfo.get('sub')
            email = idinfo.get('email')
            name = idinfo.get('name')
            picture = idinfo.get('picture')
            email_verified = idinfo.get('email_verified', False)
            
            if not email:
                raise HTTPException(status_code=400, detail="Email is required")
            
            # Find existing user
            query, params = UserQueries.get_user_by_email_params(email)
            user = await postgres_client.client.execute_query(query, params)
            user = user[0] if user else None
            
            if not user:
                # Create new user with Google account
                new_user = True
                userId = str(uuid.uuid4())
                
                transaction_queries = AuthQueries.create_user_with_google_account_transaction(
                    userId, email, name or email.split('@')[0], picture,
                    datetime.utcnow() if email_verified else None,
                    google_id, auth_request.idToken
                )
                
                results = await postgres_client.client.execute_transaction(transaction_queries)
                user = results[0][0] if results[0] else None
                
            else:
                # Check if Google account exists
                query, params = AccountQueries.get_google_account_params(user['id'])
                accounts = await postgres_client.client.execute_query(query, params)
                
                if not accounts:
                    # Link Google account
                    query, params = AccountQueries.create_google_account_params(
                        user['id'], google_id, auth_request.idToken
                    )
                    await postgres_client.client.execute_update(query, params)
            
            if not user:
                raise HTTPException(status_code=500, detail="Failed to create or find user")
            
            # Determine user role
            role = await AuthHandler._get_user_role(user['id'])
            
            # Generate JWT token
            token = jwt.encode(
                {
                    'id': str(user['id']),
                    'email': user['email'],
                    'name': user['name'],
                    'role': role,
                    'exp': datetime.utcnow() + timedelta(days=7)
                },
                app_config.JWT_SECRET,
                algorithm='HS256'
            )
            
            user_data = UserResponse(
                id=str(user['id']),
                email=user['email'],
                name=user['name'],
                image=user.get('image'),
                role=role
            )
            
            # Set cookies
            response.set_cookie(
                key="token", 
                value=token, 
                httponly=True, 
                secure=True, 
                samesite='lax',
                max_age=7 * 24 * 60 * 60
            )
            response.set_cookie(
                key="user", 
                value=user_data.model_dump_json(),
                max_age=7 * 24 * 60 * 60
            )
            
            return AuthResponse(
                token=token,
                user=user_data,
                newUser=new_user,
                companies=[]
            )
                
        except HTTPException:
            raise
        except Exception as error:
            print(f'Google auth error: {error}')
            raise HTTPException(
                status_code=500, 
                detail={
                    'error': 'Authentication failed',
                    'details': str(error) if os.getenv('FLASK_ENV') == 'development' else None
                }
            )

    @staticmethod
    async def check_email(email_request: EmailCheckRequest) -> EmailCheckResponse:
        try:
            query, params = UserQueries.get_user_by_email_params(email_request.email)
            user = await postgres_client.client.execute_query(query, params)
            
            return EmailCheckResponse(exists=bool(user))
            
        except Exception as error:
            print(f'Email check error: {error}')
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def sign_up(signup_request: SignUpRequest, response: Response) -> AuthResponse:
        try:
            # Check if user exists
            query, params = UserQueries.get_user_by_email_params(signup_request.email)
            existing_user = await postgres_client.client.execute_query(query, params)
            
            if existing_user:
                raise HTTPException(status_code=400, detail="User already exists")
            
            # Hash password
            hashed_password = bcrypt.hashpw(signup_request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Create user and credentials account in transaction
            userId = str(uuid.uuid4())
            transaction_queries = AuthQueries.create_user_with_credentials_transaction(
                userId, signup_request.email, signup_request.name, hashed_password
            )
            
            results = await postgres_client.client.execute_transaction(transaction_queries)
            user = results[0][0] if results[0] else None
            
            if not user:
                raise HTTPException(status_code=500, detail="Failed to create user")
            
            # Generate JWT token
            token = jwt.encode(
                {
                    'id': str(user['id']),
                    'email': user['email'],
                    'exp': datetime.utcnow() + timedelta(days=1)
                },
                app_config.JWT_SECRET,
                algorithm='HS256'
            )
            
            user_data = UserResponse(
                id=str(user['id']),
                email=user['email'],
                name=user['name'],
                role='member'
            )
            
            # Set cookies
            response.set_cookie(key="token", value=token, httponly=True)
            response.set_cookie(key="user", value=user_data.model_dump_json())
            
            return AuthResponse(
                token=token,
                user=user_data,
                newUser=True
            )
            
        except HTTPException:
            raise
        except Exception as error:
            print(f'Sign up error: {error}')
            raise HTTPException(status_code=500, detail="Internal server error")

    """@staticmethod
    async def generate_otp(otp_request: GenerateOTPRequest) -> MessageResponse:
        try:
            # Generate 6-digit OTP
            code = str(random.randint(100000, 999999))
            expires_at = datetime.utcnow() + timedelta(minutes=10)
            
            # Generate OTP transaction
            transaction_queries = AuthQueries.generate_otp_transaction(
                otp_request.email, code, expires_at
            )
            
            await postgres_client.client.execute_transaction(transaction_queries)
            
            # Send email
            await email_handler.send_otp_email(otp_request.email, code)
            
            return MessageResponse(message="OTP sent successfully")
            
        except Exception as error:
            print(f'Generate OTP error: {error}')
            raise HTTPException(status_code=500, detail="Internal server error")"""

    @staticmethod
    async def generate_otp(otp_request: GenerateOTPRequest) -> MessageResponse:
        try:
            code = str(random.randint(100000, 999999))
            expires_at = datetime.utcnow() + timedelta(minutes=10)

            await otp_repository.put_otp(otp_request.email, code, expires_at)

            await email_handler.send_otp_email(otp_request.email, code)
            
            return MessageResponse(message="OTP sent successfully")
            
        except Exception as error:
            print(f'Generate OTP error: {error}')
            raise HTTPException(status_code=500, detail="Internal server error")


    """@staticmethod
    async def verify_otp(otp_request: VerifyOTPRequest, response: Response) -> AuthResponse:
        try:
            print(f'Verify OTP request: {otp_request}')
            # Find valid OTP
            query, params = OTPQueries.get_valid_otp_params(otp_request.email, otp_request.code)
            print(f'Verify OTP query: {query}')
            otps = await postgres_client.client.execute_query(query, params)
            print(f'Verify OTP results: {otps}')
            
            if not otps:
                raise HTTPException(status_code=400, detail="Invalid or expired OTP")
            
            otp_record = otps[0]

            if otp_record['code'] != otp_request.code:
                raise HTTPException(status_code=400, detail="Invalid or expired OTP")
            
            # Delete OTP
            query, params = OTPQueries.delete_otp_by_id_params(otp_record['id'])
            await postgres_client.client.execute_update(query, params)
            
            # Check if user exists
            query, params = UserQueries.get_user_by_email_params(otp_request.email)
            user = await postgres_client.client.execute_query(query, params)
            user = user[0] if user else None
            new_user = False

            print(f'User: {user}')
            
            if not user:
                new_user = True
                userId = str(uuid.uuid4())
                
                # Create user with OTP verification
                jwt_token = jwt.encode(
                    {'email': otp_request.email}, 
                    app_config.JWT_SECRET, 
                    algorithm='HS256'
                )
                
                transaction_queries = AuthQueries.create_user_with_otp_verification_transaction(
                    userId, otp_request.email, otp_request.email.split('@')[0], jwt_token
                )
                
                results = await postgres_client.client.execute_transaction(transaction_queries)
                user = results[0][0] if results[0] else None
            
            if not user:
                raise HTTPException(status_code=500, detail="User creation failed")
            
            # Determine role
            role = 'admin' if new_user else await AuthHandler._get_user_role(user['id'])
            
            # Generate JWT token
            token = jwt.encode(
                {
                    'id': str(user['id']),
                    'email': user['email'],
                    'role': role,
                    'name': user['name'],
                    'image': user.get('image'),
                    'exp': datetime.utcnow() + timedelta(days=7)
                },
                app_config.JWT_SECRET,
                algorithm='HS256'
            )
            
            user_data = UserResponse(
                id=str(user['id']),
                email=user['email'],
                name=user['name'],
                image=user.get('image'),
                role=role
            )
            
            # Set cookies
            response.set_cookie(
                key="token", 
                value=token, 
                httponly=True, 
                secure=True, 
                samesite='lax',
                max_age=7 * 24 * 60 * 60
            )
            response.set_cookie(
                key="user", 
                value=user_data.model_dump_json(),
                max_age=7 * 24 * 60 * 60
            )

            # Delete OTP
            query, params = OTPQueries.delete_otp_by_id_params(otp_record['id'])
            await postgres_client.client.execute_update(query, params)
            
            return AuthResponse(
                token=token,
                user=user_data,
                newUser=new_user
            )
            
        except HTTPException:
            raise
        except Exception as error:
            print(f'Verify OTP error: {error}')
            raise HTTPException(status_code=500, detail="Internal server error")"""

    @staticmethod
    async def verify_otp(otp_request: VerifyOTPRequest, response: Response) -> AuthResponse:
        try:
            item = await otp_repository.get_valid_otp(otp_request.email, otp_request.code)
            if not item:
                raise HTTPException(status_code=400, detail="Invalid or expired OTP")

            await otp_repository.delete_otp(otp_request.email)

            query, params = UserQueries.get_user_by_email_params(otp_request.email)
            user = await postgres_client.client.execute_query(query, params)
            user = user[0] if user else None
            new_user = False

            print(f'User: {user}')
            
            if not user:
                new_user = True
                userId = str(uuid.uuid4())

                jwt_token = jwt.encode(
                    {'email': otp_request.email}, 
                    app_config.JWT_SECRET, 
                    algorithm='HS256'
                )
                
                transaction_queries = AuthQueries.create_user_with_otp_verification_transaction(
                    userId, otp_request.email, otp_request.email.split('@')[0], jwt_token
                )
                
                results = await postgres_client.client.execute_transaction(transaction_queries)
                user = results[0][0] if results[0] else None
            
            if not user:
                raise HTTPException(status_code=500, detail="User creation failed")

            role = 'admin' if new_user else await AuthHandler._get_user_role(user['id'])

            token = jwt.encode(
                {
                    'id': str(user['id']),
                    'email': user['email'],
                    'role': role,
                    'name': user['name'],
                    'image': user.get('image'),
                    'exp': datetime.utcnow() + timedelta(days=7)
                },
                app_config.JWT_SECRET,
                algorithm='HS256'
            )
            
            user_data = UserResponse(
                id=str(user['id']),
                email=user['email'],
                name=user['name'],
                image=user.get('image'),
                role=role
            )

            response.set_cookie(
                key="token", 
                value=token, 
                httponly=True, 
                secure=True, 
                samesite='lax',
                max_age=7 * 24 * 60 * 60
            )
            response.set_cookie(
                key="user", 
                value=user_data.model_dump_json(),
                max_age=7 * 24 * 60 * 60
            )
            
            return AuthResponse(
                token=token,
                user=user_data,
                newUser=new_user
            )
            
        except HTTPException:
            raise
        except Exception as error:
            print(f'Verify OTP error: {error}')
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def sign_in(signin_request: SignInRequest, response: Response) -> AuthResponse:
        try:
            query, params = UserQueries.get_user_by_email_params(signin_request.email)
            user = await postgres_client.client.execute_query(query, params)
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            user = user[0]

            if signin_request.code:
                await AuthHandler._verify_otp_for_signin(signin_request.email, signin_request.code)
            elif signin_request.password:
                await AuthHandler._verify_password_for_signin(user, signin_request.password)
            else:
                raise HTTPException(status_code=400, detail="Either password or OTP code is required")

            role = await AuthHandler._get_user_role(user['id'])

            token = jwt.encode(
                {
                    'id': str(user['id']),
                    'email': user['email'],
                    'role': role,
                    'name': user['name'],
                    'image': user.get('image'),
                    'exp': datetime.utcnow() + timedelta(days=7)
                },
                app_config.JWT_SECRET,
                algorithm='HS256'
            )
            
            user_data = UserResponse(
                id=str(user['id']),
                email=user['email'],
                name=user['name'],
                image=user.get('image'),
                role=role
            )

            response.set_cookie(
                key="token", 
                value=token, 
                httponly=True, 
                secure=True, 
                samesite='lax',
                max_age=7 * 24 * 60 * 60
            )
            response.set_cookie(
                key="user", 
                value=user_data.model_dump_json(),
                max_age=7 * 24 * 60 * 60
            )
            
            return AuthResponse(
                token=token,
                user=user_data,
                newUser=False
            )
            
        except HTTPException:
            raise
        except Exception as error:
            print(f'Sign in error: {error}')
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    async def _verify_password_for_signin(user: dict, password: str):
        """Verify password for existing user"""
        # Get user credentials
        user_query = UserQueries.GET_USER_WITH_CREDENTIALS
        user_with_creds = await postgres_client.client.execute_query(user_query, (user['email'],))
        
        if not user_with_creds:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user_creds = user_with_creds[0]
        
        # Verify password
        is_valid_password = bcrypt.checkpw(
            password.encode('utf-8'),
            user_creds['access_token'].encode('utf-8')
        )
        
        if not is_valid_password:
            raise HTTPException(status_code=401, detail="Invalid credentials")

    """@staticmethod
    async def _verify_otp_for_signin(email: str, code: str):
        query, params = OTPQueries.get_valid_otp_params(email, code)
        otps = await postgres_client.client.execute_query(query, params)
        
        if not otps:
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")
        
        otp_record = otps[0]
        
        if otp_record['code'] != code:
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")

        query, params = OTPQueries.delete_otp_by_id_params(otp_record['id'])
        await postgres_client.client.execute_update(query, params)

        @staticmethod
        async def get_profile(userId: str) -> UserResponse:
            try:
                query, params = UserQueries.get_user_by_id_params(userId)
                user = await postgres_client.client.execute_query(query, params)
                
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")
                
                user = user[0]
                role = await AuthHandler._get_user_role(user['id'])
                
                return UserResponse(
                    id=str(user['id']),
                    name=user['name'],
                    email=user['email'],
                    image=user.get('image'),
                    role=role
                )
                
            except HTTPException:
                raise
            except Exception as error:
                print(f'Get profile error: {error}')
                raise HTTPException(status_code=500, detail="Internal server error")"""

    @staticmethod
    async def _verify_otp_for_signin(email: str, code: str):
        item = await otp_repository.get_valid_otp(email, code)
        if not item:
            raise HTTPException(status_code=400, detail="Invalid or expired OTP")
        await otp_repository.delete_otp(email)

        @staticmethod
        async def get_profile(userId: str) -> UserResponse:
            try:
                query, params = UserQueries.get_user_by_id_params(userId)
                user = await postgres_client.client.execute_query(query, params)
                
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")
                
                user = user[0]
                role = await AuthHandler._get_user_role(user['id'])
                
                return UserResponse(
                    id=str(user['id']),
                    name=user['name'],
                    email=user['email'],
                    image=user.get('image'),
                    role=role
                )
                
            except HTTPException:
                raise
            except Exception as error:
                print(f'Get profile error: {error}')
                raise HTTPException(status_code=500, detail="Internal server error")


    @staticmethod
    async def _get_user_role(userId: str) -> str:
        """Helper method to determine user role using query classes"""
        # Check if user owns any companies
        query, params = CompanyQueries.count_companies_by_owner_params(userId)
        company_results = await postgres_client.client.execute_query(query, params)
        
        if company_results and company_results[0]['count'] > 0:
            return 'admin'
        
        # Check company memberships
        query, params = CompanyQueries.get_user_first_membership_params(userId)
        membership_results = await postgres_client.client.execute_query(query, params)
        
        if membership_results:
            return membership_results[0]['role']
        
        return 'member'