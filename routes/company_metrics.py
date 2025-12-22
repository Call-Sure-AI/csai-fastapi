from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

from app.services.company_metrics_service import CompanyMetricsService, TimeRange

logger = logging.getLogger(__name__)

router = APIRouter()

service = CompanyMetricsService()


@router.websocket("/ws/{company_id}/{time_range}")
async def company_metrics_ws(
    websocket: WebSocket,
    company_id: str,
    time_range: TimeRange
):
    await websocket.accept()

    try:
        data = await service.compute_company_metrics(company_id, time_range)
        await websocket.send_json(data)

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info("Company metrics WS disconnected")
    except Exception as e:
        logger.error(f"Company metrics WS error: {e}", exc_info=True)
    finally:
        await websocket.close()
