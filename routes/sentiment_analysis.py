from fastapi import APIRouter, WebSocket
from app.services.sentiment_analysis_service import SentimentAnalysisService
import logging

router = APIRouter()
logger = logging.getLogger("routes.sentiment_analysis")


@router.websocket("/ws/{company_id}/{range}")
async def sentiment_analysis_ws(
    websocket: WebSocket,
    company_id: str,
    range: str
):
    await websocket.accept()
    logger.info(f"Sentiment WS connected | company_id={company_id} | range={range}")

    try:
        service = SentimentAnalysisService()
        payload = await service.get_sentiment_dashboard(
            company_id=company_id,
            range=range
        )

        logger.info(
            "Sentiment dashboard computed | "
            f"total_calls={payload['summary']['total_calls']}"
        )

        await websocket.send_json(payload)

    except Exception as e:
        logger.error(
            f"Sentiment WS error | company_id={company_id} | error={str(e)}",
            exc_info=True
        )
        await websocket.send_json({
            "success": False,
            "error": "Failed to compute sentiment analysis"
        })
