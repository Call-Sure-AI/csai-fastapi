from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres_client import get_db_connection
from handlers.whatsapp_handler import WhatsAppHandler
from app.models.schemas import WhatsAppOnboardRequest, SendMessageRequest, SendMessageResponse
from middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
handler = WhatsAppHandler()
WhatsAppOnboardRequest, SendMessageRequest, SendMessageResponse
@router.post("/onboard")
async def onboard_whatsapp(
    data: WhatsAppOnboardRequest,
    db: AsyncSession = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    result = await handler.onboard(db, data)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result)
    return result

@router.post("/send-message", response_model=SendMessageResponse)
async def send_message(
    payload: SendMessageRequest,
    db: AsyncSession = Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    result = await handler.send_message(db, payload.business_id, payload.to, payload.message)
    return result
