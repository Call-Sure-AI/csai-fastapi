from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

from app.services.call_report_service import CallReportsService

logger = logging.getLogger(__name__)

router = APIRouter()

service = CallReportsService()


@router.websocket("/ws/{company_id}/{range}")
async def call_reports_ws(
    websocket: WebSocket,
    company_id: str,
    range: str
):
    await websocket.accept()

    try:
        payload = await service.get_company_call_reports(
            company_id=company_id,
            range=range
        )
        await websocket.send_json(payload)

        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
            elif msg == "refresh":
                payload = await service.get_company_call_reports_ws(
                    company_id=company_id,
                    range=range
                )
                await websocket.send_json(payload)

    except WebSocketDisconnect:
        logger.info(f"Call Reports WS disconnected: {company_id}")
    except Exception as e:
        logger.error(f"Call Reports WS error: {e}", exc_info=True)
        await websocket.close()
