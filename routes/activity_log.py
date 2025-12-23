from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import datetime, timedelta
from app.services.activity_log_service import ActivityLogService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
activity_log_service = ActivityLogService()


@router.websocket("/ws/{company_id}")
async def activity_log_ws(
    websocket: WebSocket,
    company_id: str,
):
    try:
        await websocket.accept()

        logger.info(
            f"Activity Log WS connected | company_id={company_id}"
        )

        range_param = websocket.query_params.get("range", "7d")
        limit = int(websocket.query_params.get("limit", 50))
        offset = int(websocket.query_params.get("offset", 0))

        logger.info(
            f"Calling ActivityLogService | company_id={company_id} "
            f"range={range_param}"
        )

        payload = await activity_log_service.get_activity_log(
            company_id=company_id,
            range=range_param,
            limit=50,
            offset=0
        )

        await websocket.send_json(payload)

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info("Activity Log WS disconnected")

    except Exception as e:
        logger.error(
            f"Activity Log WS error | company_id={company_id} | error={e}",
            exc_info=True
        )
        await websocket.close(code=1008)
