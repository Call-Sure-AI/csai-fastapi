from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging
from decimal import Decimal

from app.db.postgres_client import get_db_connection
from handlers.s3_handler import S3Handler

from app.services.call_report_service import (
    compute_call_sentiment,
    range_start
)

sentiment_logger = logging.getLogger("sentiment.pipeline")
sentiment_logger.setLevel(logging.DEBUG)

s3_handler = S3Handler()


def json_safe(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, list):
        return [json_safe(x) for x in v]
    if isinstance(v, dict):
        return {k: json_safe(x) for k, x in v.items()}
    return v


class SentimentAnalysisService:

    async def get_sentiment_dashboard(
        self,
        company_id: str,
        range: str
    ) -> Dict[str, Any]:

        start_time = range_start(range)

        sentiment_logger.info(
            f"Sentiment dashboard start | company_id={company_id} | range={range}"
        )

        async with await get_db_connection() as conn:
            calls = await self._fetch_calls(conn, company_id, start_time)

        sentiment_buckets = {
            "Positive": 0,
            "Neutral": 0,
            "Negative": 0
        }

        timeline = {}

        recent_calls = []

        for call in calls:
            sentiment = call["sentiment"]
            date_key = call["created_at"].date().isoformat()

            sentiment_buckets[sentiment] += 1

            if date_key not in timeline:
                timeline[date_key] = {
                    "positive": 0,
                    "neutral": 0,
                    "negative": 0,
                    "total": 0
                }

            timeline[date_key][sentiment.lower()] += 1
            timeline[date_key]["total"] += 1

            recent_calls.append({
                "caller": call["caller_phone"],
                "datetime": call["created_at"],
                "agent": call["agent_name"] or "AI Agent",
                "duration": int(call["duration"] or 0),
                "sentiment": sentiment,
                "score": call["sentiment_score"],
                "key_phrases": call["key_phrases"]
            })

        total = sum(sentiment_buckets.values()) or 1

        summary = {
            "positive_pct": round(sentiment_buckets["Positive"] / total * 100, 1),
            "neutral_pct": round(sentiment_buckets["Neutral"] / total * 100, 1),
            "negative_pct": round(sentiment_buckets["Negative"] / total * 100, 1),
            "average_score": round(
                (sentiment_buckets["Positive"] * 8 +
                 sentiment_buckets["Neutral"] * 5 +
                 sentiment_buckets["Negative"] * 2) / total,
                1
            )
        }

        return json_safe({
            "summary": summary,
            "trend": timeline,
            "recent_calls": recent_calls
        })

    async def _fetch_calls(
        self,
        conn,
        company_id: str,
        start_time: datetime
    ) -> List[Dict[str, Any]]:

        rows = await conn.fetch("""
            SELECT
                c.created_at,
                c.duration,
                c.call_sid,
                c.transcription,
                c.from_number,
                c.to_number,

                an.agent_name

            FROM "Call" c
            LEFT JOIN "AgentNumber" an
                ON an.company_id = c.company_id
               AND an.agent_id IS NOT NULL

            WHERE c.company_id = $1
              AND c.created_at >= $2

            ORDER BY c.created_at DESC
        """, company_id, start_time)

        results = []

        for r in rows:
            call_sid = r["call_sid"]
            transcription_url = r["transcription"]

            sentiment_logger.info(
                f"Sentiment processing | call_sid={call_sid} | url={transcription_url}"
            )

            sentiment = "Neutral"
            score = 5
            key_phrases = []

            if transcription_url:
                try:
                    transcript_json = s3_handler.download_json_via_presigned_url(
                        transcription_url
                    )

                    if transcript_json:
                        sentiment = compute_call_sentiment(transcript_json)

                        score = {
                            "Positive": 8,
                            "Neutral": 5,
                            "Negative": 2
                        }[sentiment]

                        # Extract keywords from user turns
                        conversation = transcript_json.get("conversation", [])
                        key_phrases = [
                            turn["content"]
                            for turn in conversation
                            if turn.get("role") == "user"
                        ][:3]

                        sentiment_logger.info(
                            f"Sentiment resolved | call_sid={call_sid} | sentiment={sentiment}"
                        )
                    else:
                        sentiment_logger.warning(
                            f"Empty transcript JSON | call_sid={call_sid}"
                        )

                except Exception as e:
                    sentiment_logger.error(
                        f"Transcript parse failed | call_sid={call_sid} | error={e}",
                        exc_info=True
                    )
            else:
                sentiment_logger.warning(
                    f"No transcription URL | call_sid={call_sid}"
                )

            results.append({
                "caller_phone": r["to_number"],
                "created_at": r["created_at"],
                "duration": r["duration"],
                "agent_name": r["agent_name"],
                "sentiment": sentiment,
                "sentiment_score": score,
                "key_phrases": key_phrases
            })

        return results
