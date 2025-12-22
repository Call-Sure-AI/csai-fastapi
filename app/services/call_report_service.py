from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from decimal import Decimal
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import json
from urllib.parse import urlparse
from handlers.s3_handler import S3Handler
from app.db.postgres_client import get_db_connection
from textblob import TextBlob
import logging

sentiment_logger = logging.getLogger("sentiment.pipeline")
sentiment_logger.setLevel(logging.DEBUG)

nltk.download("vader_lexicon")
SIA = SentimentIntensityAnalyzer()

s3_handler = S3Handler()


def extract_s3_key(url: str) -> str:
    """
    Convert full S3 URL → object key
    """
    parsed = urlparse(url)
    return parsed.path.lstrip("/")

def compute_call_sentiment(transcript: dict | None) -> str:
    sentiment_logger.debug("compute_call_sentiment: start")

    if not transcript:
        sentiment_logger.warning("Transcript is None → Neutral")
        return "Neutral"

    conversation = transcript.get("conversation")
    if not conversation:
        sentiment_logger.warning(
            f"Transcript has no conversation | keys={list(transcript.keys())}"
        )
        return "Neutral"

    sentiment_score = {
        "positive": 1,
        "neutral": 0,
        "negative": -1
    }

    total_score = 0.0
    total_weight = 0.0

    for idx, turn in enumerate(conversation):
        role = turn.get("role")
        sentiment = turn.get("sentiment")
        readiness = turn.get("buying_readiness", 50)

        sentiment_logger.debug(
            f"Turn[{idx}] role={role} sentiment={sentiment} readiness={readiness}"
        )

        if role != "user":
            continue

        if sentiment not in sentiment_score:
            sentiment_logger.warning(
                f"Turn[{idx}] sentiment missing/invalid | keys={list(turn.keys())}"
            )
            continue

        weight = readiness / 100.0
        total_score += sentiment_score[sentiment] * weight
        total_weight += weight

    sentiment_logger.debug(
        f"Sentiment aggregation | total_score={total_score} total_weight={total_weight}"
    )

    if total_weight == 0:
        sentiment_logger.warning(
            "No valid sentiment found in conversation → Neutral"
        )
        return "Neutral"

    avg = total_score / total_weight
    sentiment_logger.debug(f"Sentiment average score={avg}")

    if avg >= 0.2:
        final = "Positive"
    elif avg <= -0.2:
        final = "Negative"
    else:
        final = "Neutral"

    sentiment_logger.info(f"Final sentiment decided → {final}")
    return final

"""async def fetch_transcript_text(transcript_url: str) -> str | None:
    if not transcript_url:
        return None

    try:
        key = extract_s3_key(transcript_url)
        result = await s3_handler.download_file(key)
        print(result)
        if not result["success"]:
            return None

        content = result["data"].decode("utf-8")
        data = json.loads(content)

        if isinstance(data, dict):
            if "text" in data:
                return data["text"]

            if "segments" in data and isinstance(data["segments"], list):
                return " ".join(
                    seg.get("text", "")
                    for seg in data["segments"]
                )

        return None

    except Exception as e:
        logger.warning(f"Transcript fetch failed: {e}")
        return None"""

"""def sentiment(text: Optional[str]) -> str:
    if not text:
        return "Neutral"
    score = SIA.polarity_scores(text)["compound"]
    if score >= 0.05:
        return "Positive"
    if score <= -0.05:
        return "Negative"
    return "Neutral"
    """


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


def range_start(range: str) -> datetime:
    now = datetime.utcnow()
    return {
        "today": now - timedelta(days=1),
        "week": now - timedelta(days=7),
        "month": now - timedelta(days=30),
        "quarter": now - timedelta(days=90),
        "year": now - timedelta(days=365),
    }.get(range, now - timedelta(days=7))


class CallReportsService:

    async def get_company_call_reports(
        self,
        company_id: str,
        range: str,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:

        start = range_start(range)

        async with await get_db_connection() as conn:
            summary = await self._summary(conn, company_id, start)
            calls = await self._calls(conn, company_id, start, limit, offset)

        return json_safe({
            "summary": summary,
            "calls": calls
        })

    async def _summary(self, conn, company_id: str, start: datetime) -> Dict[str, Any]:
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) AS total_calls,
                COUNT(*) FILTER (WHERE call_type='incoming') AS inbound,
                COUNT(*) FILTER (WHERE call_type='outgoing') AS outbound,
                AVG(duration) AS avg_duration,
                COUNT(*) FILTER (
                    WHERE NOT EXISTS (
                        SELECT 1 FROM "Ticket" t
                        WHERE t.meta_data->>'call_sid' = c.call_sid
                    )
                )::float / NULLIF(COUNT(*),0) * 100 AS resolution_rate
            FROM "Call" c
            WHERE c.company_id = $1
            AND c.created_at >= $2
        """, company_id, start)

        resolution = round(row["resolution_rate"] or 0, 2)

        return {
            "total_calls": row["total_calls"],
            "inbound": row["inbound"],
            "outbound": row["outbound"],
            "avg_duration": int(row["avg_duration"] or 0),
            "resolution_rate": resolution,
            "first_call_resolution": resolution,
            "sentiment_score": round(min(10, 6 + resolution / 20), 1),
            "customer_satisfaction": round(min(10, 5 + resolution / 25), 1)
        }


    async def _calls(
        self,
        conn,
        company_id: str,
        start: datetime,
        limit: int,
        offset: int
    ) -> list[dict]:

        rows = await conn.fetch("""
            SELECT
                c.created_at,
                c.duration,
                c.call_type,
                c.from_number,
                c.to_number,
                c.call_sid,
                c.transcription,

                an.agent_id,
                an.agent_name,

                EXISTS (
                    SELECT 1
                    FROM "Ticket" t
                    WHERE t.meta_data->>'call_sid' = c.call_sid
                ) AS escalated

            FROM "Call" c
            LEFT JOIN "AgentNumber" an
                ON an.company_id = c.company_id
            AND (
                    (c.call_type = 'outgoing' AND an.phone_number = c.from_number)
                OR (c.call_type = 'incoming' AND an.phone_number = c.to_number)
            )

            WHERE c.company_id = $1
            AND c.created_at >= $2

            ORDER BY c.created_at DESC
            LIMIT $3 OFFSET $4
        """, company_id, start, limit, offset)

        result = []

        for r in rows:
            call_sid = r["call_sid"]
            transcription_url = r["transcription"]

            sentiment_logger.info(
                f"Processing call | call_sid={call_sid} | transcription_url={transcription_url}"
            )

            sentiment = "Neutral"

            if transcription_url:
                try:
                    transcript_json = s3_handler.download_json_via_presigned_url(
                        transcription_url
                    )

                    if not transcript_json:
                        sentiment_logger.warning(
                            f"S3 returned empty JSON | call_sid={call_sid}"
                        )

                    else:
                        sentiment_logger.debug(
                            f"Transcript JSON keys | call_sid={call_sid} | keys={list(transcript_json.keys())}"
                        )

                        # IMPORTANT: your transcripts are already FULL JSON
                        sentiment = compute_call_sentiment(transcript_json)

                except Exception as e:
                    sentiment_logger.error(
                        f"Transcript processing failed | call_sid={call_sid} | error={e}",
                        exc_info=True
                    )
            else:
                sentiment_logger.warning(
                    f"No transcription URL | call_sid={call_sid}"
                )

            result.append({
                "caller_phone": r["to_number"],
                "datetime": r["created_at"],
                "duration": int(r["duration"] or 0),
                "type": "Inbound" if r["call_type"] == "incoming" else "Outbound",
                "agent": r["agent_name"] or "AI Agent",
                "outcome": "Escalated" if r["escalated"] else "Resolved",
                "sentiment": sentiment,
            })

        return result