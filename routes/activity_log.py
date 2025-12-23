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

        # ---------- QUERY PARAMS ----------
        range_param = websocket.query_params.get("range", "7d")
        limit = int(websocket.query_params.get("limit", 50))
        offset = int(websocket.query_params.get("offset", 0))
        action = websocket.query_params.get("action")  # optional
        search = websocket.query_params.get("search")  # optional

        # ---------- RANGE → DATES ----------
        days = int(range_param.replace("d", ""))
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # ---------- SERVICE CALL (MATCHES SIGNATURE EXACTLY) ----------
        payload = await activity_log_service.get_activity_log(
            company_id=company_id,
            limit=50,
            offset=0
        )


        await websocket.send_json(payload)

        # Keep WS alive
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
