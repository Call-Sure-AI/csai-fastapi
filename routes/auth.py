from fastapi import APIRouter, Response, Depends, Request, status
from fastapi.responses import JSONResponse
from handlers.auth_handler import AuthHandler
from app.models.schemas import (
    GoogleAuthRequest, EmailCheckRequest, SignUpRequest, SignInRequest,
    GenerateOTPRequest, VerifyOTPRequest, AuthResponse, EmailCheckResponse,
    MessageResponse, UserResponse
)
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/google", response_model=AuthResponse)
async def google_auth(auth_request: GoogleAuthRequest, response: Response):
    return await AuthHandler.google_auth(auth_request, response)

@router.post("/check-email", response_model=EmailCheckResponse)
async def check_email(email_request: EmailCheckRequest):
    return await AuthHandler.check_email(email_request)

@router.post("/signup", response_model=AuthResponse)
async def sign_up(signup_request: SignUpRequest, response: Response):
    return await AuthHandler.sign_up(signup_request, response)

@router.post("/signin", response_model=AuthResponse)
async def sign_in(signin_request: SignInRequest, response: Response):
    return await AuthHandler.sign_in(signin_request, response)

@router.post("/generate-otp", response_model=MessageResponse)
async def generate_otp(otp_request: GenerateOTPRequest):
    return await AuthHandler.generate_otp(otp_request)

@router.post("/verify-otp", response_model=AuthResponse)
async def verify_otp(otp_request: VerifyOTPRequest, response: Response):
    return await AuthHandler.verify_otp(otp_request, response)

@router.get("/profile/{userId}", response_model=UserResponse)
async def get_profile(
    userId: str,
    current_user: UserResponse = Depends(get_current_user)
):
    return await AuthHandler.get_profile(userId) 