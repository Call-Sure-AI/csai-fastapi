from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Any, List
import statistics

from app.db.postgres_client import get_db_connection
from handlers.s3_handler import S3Handler
import logging

logger = logging.getLogger("services.sentiment_analysis")

s3_handler = S3Handler()
class SentimentAnalysisService:

    async def get_sentiment_dashboard(
        self,
        company_id: str,
        range: str
    ) -> Dict[str, Any]:

        start_time = self._resolve_range(range)

        async with await get_db_connection() as conn:
            calls = await self._fetch_calls(conn, company_id, start_time)

        sentiment_rows = []
        daily_bucket = defaultdict(list)

        for call in calls:
            sentiment_data = await self._extract_sentiment(call)
            if not sentiment_data:
                continue

            sentiment_rows.append(sentiment_data)
            daily_bucket[sentiment_data["date"]].append(sentiment_data)

        return {
            "summary": self._summary(sentiment_rows),
            "trend": self._daily_trend(daily_bucket),
            "recent_calls": sentiment_rows[:10]
        }


    def _resolve_range(self, range: str) -> datetime:
        now = datetime.utcnow()
        mapping = {
            "today": now - timedelta(days=1),
            "week": now - timedelta(days=7),
            "month": now - timedelta(days=30),
            "quarter": now - timedelta(days=90),
            "year": now - timedelta(days=365),
        }
        return mapping.get(range.lower(), mapping["week"])

    async def _fetch_calls(self, conn, company_id: str, start_time: datetime):
        logger.info(f"Fetching calls for sentiment | company_id={company_id}")

        return await conn.fetch("""
            SELECT
                c.call_sid,
                c.created_at,
                c.duration,
                c.transcription,
                an.agent_name
            FROM "Call" c
            LEFT JOIN "AgentNumber" an ON an.agent_id = c.agent_id
            WHERE c.company_id = $1
              AND c.created_at >= $2
            ORDER BY c.created_at DESC
        """, company_id, start_time)

    async def _extract_sentiment(self, call) -> Dict[str, Any] | None:
        if not call["transcription"]:
            return None

        transcript = await s3_handler.fetch_transcript_json(call["transcription"])
        if not transcript or "conversation" not in transcript:
            return None

        sentiments = []
        keywords = set()

        for turn in transcript["conversation"]:
            if turn.get("role") == "user":
                s = turn.get("sentiment")
                if s:
                    sentiments.append(s)
                if "content" in turn:
                    keywords.update(
                        w.lower() for w in turn["content"].split()
                        if len(w) > 5
                    )

        if not sentiments:
            final_sentiment = "Neutral"
            score = 50
        else:
            final_sentiment = max(set(sentiments), key=sentiments.count)
            score = {
                "positive": 85,
                "neutral": 55,
                "negative": 25
            }.get(final_sentiment, 50)

        logger.debug(
            f"Sentiment computed | call_sid={call['call_sid']} "
            f"sentiment={final_sentiment} score={score}"
        )

        return {
            "caller": call["call_sid"],
            "date": call["created_at"].date().isoformat(),
            "datetime": call["created_at"].isoformat(),
            "agent": call["agent_name"] or "AI Agent",
            "duration": int(call["duration"] or 0),
            "sentiment": final_sentiment.capitalize(),
            "score": score,
            "key_phrases": list(keywords)[:5]
        }

    def _summary(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(rows)
        if not total:
            return {
                "total_calls": 0,
                "positive": 0,
                "neutral": 0,
                "negative": 0,
                "average_score": 0
            }

        counts = defaultdict(int)
        scores = []

        for r in rows:
            counts[r["sentiment"].lower()] += 1
            scores.append(r["score"])

        return {
            "total_calls": total,
            "positive": round((counts["positive"] / total) * 100, 2),
            "neutral": round((counts["neutral"] / total) * 100, 2),
            "negative": round((counts["negative"] / total) * 100, 2),
            "average_score": round(statistics.mean(scores), 1)
        }

    # ---------------------------------------------------

    def _daily_trend(self, bucket: Dict[str, List[Dict]]) -> List[Dict[str, Any]]:
        trend = []

        for day, rows in sorted(bucket.items()):
            total = len(rows)
            if not total:
                continue

            counts = defaultdict(int)
            for r in rows:
                counts[r["sentiment"].lower()] += 1

            trend.append({
                "date": day,
                "total_calls": total,
                "positive": round((counts["positive"] / total) * 100, 1),
                "neutral": round((counts["neutral"] / total) * 100, 1),
                "negative": round((counts["negative"] / total) * 100, 1),
            })

        return trend
