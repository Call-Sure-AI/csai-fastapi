import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
from app.services.urgency_detection_service import UrgencyDetectionService

logger = logging.getLogger("routes.urgency_detection")

router = APIRouter()

service = UrgencyDetectionService()
@router.websocket("/ws/{company_id}/{range}")
async def urgency_ws(websocket: WebSocket, company_id: str, range: str):
    await websocket.accept()
    logger.info(
        "Urgency WS connected | company_id=%s | range=%s",
        company_id, range
    )

    try:
        while True:
            payload = await service.get_urgency_dashboard(company_id, range)

            await websocket.send_json(payload)

            await asyncio.sleep(10)

    except WebSocketDisconnect:
        logger.info(
            "Urgency WS disconnected | company_id=%s | range=%s",
            company_id, range
        )

    except Exception as e:
        logger.exception(
            "Urgency WS fatal error | company_id=%s | error=%s",
            company_id, str(e)
        )
        await websocket.close()

