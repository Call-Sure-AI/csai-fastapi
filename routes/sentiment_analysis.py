from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.sentiment_analysis_service import SentimentAnalysisService
import logging
import asyncio

router = APIRouter()
logger = logging.getLogger("routes.sentiment_analysis")

service = SentimentAnalysisService()

@router.websocket("/ws/{company_id}/{range}")
async def sentiment_analysis_ws(websocket: WebSocket, company_id: str, range: str):
    await websocket.accept()
    logger.info(f"Sentiment WS connected | company_id={company_id} | range={range}")

    try:
        while True:
            payload = await service.get_sentiment_dashboard(
                company_id=company_id,
                range=range
            )

            await websocket.send_json(payload)

            # send update every 30 seconds
            await asyncio.sleep(30)

    except WebSocketDisconnect:
        logger.info(f"Sentiment WS disconnected | company_id={company_id}")

    except Exception as e:
        logger.exception(
            f"Sentiment WS error | company_id={company_id} | error={e}"
        )
        await websocket.close()
