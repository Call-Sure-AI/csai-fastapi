import logging
from datetime import datetime, timedelta
from collections import defaultdict
from urllib.parse import urlparse

from app.db.postgres_client import get_db_connection
from handlers.s3_handler import S3Handler
from app.services.call_report_service import CallReportsService

logger = logging.getLogger("urgency.pipeline")

HIGH = {"urgent", "immediately", "asap", "emergency", "critical", "escalate", "manager", "now", "deadline"}
MEDIUM = {"soon", "important", "waiting", "follow up", "pending"}
LOW = {"whenever", "no rush", "later", "sometime"}


class UrgencyDetectionService:
    def __init__(self):
        self.s3_handler = S3Handler()

    async def _fetch_transcript_json(self, transcription_url: str):
        if not transcription_url:
            return None

        try:
            parsed = urlparse(transcription_url)
            key = parsed.path.lstrip("/")

            logger.debug(
                f"Transcript fetch | url={transcription_url} | key={key}"
            )

            presigned_url = self.s3_handler.download_json_via_presigned_url(
                transcription_url
            )

            if not presigned_url:
                logger.warning("Presigned URL generation failed")
                return None

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(presigned_url)
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.warning(
                f"Transcript fetch failed | url={transcription_url} | error={e}"
            )
            return None

    async def get_urgency_dashboard(self, company_id: str, range: str):
        logger.info(
            f"Urgency dashboard start | company_id={company_id} | range={range}"
        )

        start_time = self._resolve_range(range)

        async with await get_db_connection() as conn:
            calls = await conn.fetch(
                """
                SELECT 
                    c.call_sid,
                    c.created_at,
                    c.from_number,
                    c.to_number,
                    c.transcription,
                    an.agent_id,
                    an.agent_name
                FROM "Call" c
                LEFT JOIN "AgentNumber" an
                    ON (
                        an.phone_number = c.from_number
                        OR an.phone_number = c.to_number
                    )
                    AND an.company_id = c.company_id
                WHERE c.company_id = $1
                AND c.created_at >= $2
                ORDER BY c.created_at DESC
                """,
                company_id,
                start_time
            )

        summary = {"high": 0, "medium": 0, "low": 0}
        category_map = defaultdict(lambda: {"high": 0, "medium": 0, "low": 0, "total": 0})
        records = []

        for call in calls:
            urgency, phrases, score = await self._compute_urgency(call)

            summary[urgency.lower()] += 1

            category = self._infer_category(phrases)
            category_map[category]["total"] += 1
            category_map[category][urgency.lower()] += 1

            records.append({
                "caller": call["from_number"],
                "datetime": call["created_at"].isoformat(),
                "urgency": urgency,
                "trigger_phrases": phrases,
                "status": "Escalated" if urgency == "High" else "Resolved",
                "agent": call["agent_name"] or "AI Agent",
                "category": category
            })

        logger.info(
            f"Urgency dashboard computed | calls={len(records)}"
        )

        return {
            "summary": summary,
            "categories": self._format_categories(category_map),
            "records": records[:50]
        }

    async def _compute_urgency(self, call: dict):
        call_sid = call.get("call_sid")
        logger.info(f"Urgency processing | call_sid={call_sid}")

        transcript_url = call.get("transcription")

        transcript = await self._fetch_transcript_json(transcript_url)

        if not transcript:
            logger.warning(f"No transcript | call_sid={call_sid}")
            return "Low", [], 0.0

        urgency_score = 0
        trigger_phrases = []

        for turn in transcript.get("conversation", []):
            text = (turn.get("content") or "").lower()

            if any(k in text for k in ["urgent", "emergency", "critical", "immediately", "asap"]):
                urgency_score += 3
                trigger_phrases.append(text)

            elif any(k in text for k in ["important", "soon", "waiting", "delay"]):
                urgency_score += 2
                trigger_phrases.append(text)

            elif any(k in text for k in ["later", "whenever", "no rush"]):
                urgency_score += 1
                trigger_phrases.append(text)

        if urgency_score >= 6:
            level = "High"
        elif urgency_score >= 3:
            level = "Medium"
        else:
            level = "Low"

        logger.info(
            f"Urgency resolved | call_sid={call_sid} | level={level} | score={urgency_score}"
        )

        return level, trigger_phrases[:3], urgency_score

    def _infer_category(self, phrases):
        joined = " ".join(phrases)

        if "billing" in joined:
            return "Billing Questions"
        if "login" in joined or "access" in joined:
            return "Account Access"
        if "error" in joined or "issue" in joined:
            return "Technical Issues"
        if "complaint" in joined or "manager" in joined:
            return "Service Complaints"

        return "General Inquiry"

    def _format_categories(self, category_map):
        output = []
        for cat, data in category_map.items():
            total = data["total"] or 1
            output.append({
                "category": cat,
                "total_calls": total,
                "high": round((data["high"] / total) * 100),
                "medium": round((data["medium"] / total) * 100),
                "low": round((data["low"] / total) * 100)
            })
        return output

    def _resolve_range(self, range):
        now = datetime.utcnow()
        if range == "week":
            return now - timedelta(days=7)
        if range == "month":
            return now - timedelta(days=30)
        return now - timedelta(days=7)
