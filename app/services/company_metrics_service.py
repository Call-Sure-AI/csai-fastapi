from datetime import datetime, timedelta
from enum import Enum
from decimal import Decimal
from typing import Dict, Any, List
import logging

from app.db.postgres_client import get_db_connection

logger = logging.getLogger(__name__)


class TimeRange(str, Enum):
    today = "today"
    week = "week"
    month = "month"
    quarter = "quarter"
    year = "year"


def get_start_time(time_range: TimeRange) -> datetime:
    now = datetime.utcnow()

    if time_range == TimeRange.today:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if time_range == TimeRange.week:
        return now - timedelta(days=7)
    if time_range == TimeRange.month:
        return now - timedelta(days=30)
    if time_range == TimeRange.quarter:
        return now - timedelta(days=90)
    if time_range == TimeRange.year:
        return now - timedelta(days=365)

    return now - timedelta(days=30)


def json_safe(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_safe(i) for i in obj]
    return obj


class CompanyMetricsService:

    async def compute_company_metrics(
        self,
        company_id: str,
        time_range: TimeRange
    ) -> Dict[str, Any]:

        start_time = get_start_time(time_range)

        async with await get_db_connection() as conn:

            overall_success_rate = await self._overall_success_rate(
                conn, company_id, start_time
            )

            avg_handle_time = await self._average_handle_time(
                conn, company_id, start_time
            )

            first_call_resolution = await self._first_call_resolution(
                conn, company_id, start_time
            )

            quality_score, qa_scores = await self._quality_score(
                conn, company_id, start_time
            )

            ai_vs_human_rate = await self._ai_vs_human_rate(
                conn, company_id, start_time
            )

            ai_vs_human_count = await self._ai_vs_human_count(
                conn, company_id, start_time
            )

            agent_efficiency = await self._agent_efficiency(
                conn, company_id, start_time
            )

            payload = {
                "overall_success_rate": overall_success_rate,
                "average_handle_time": avg_handle_time,
                "first_call_resolution": first_call_resolution,
                "quality_score": quality_score,
                "ai_vs_human_success_rate": ai_vs_human_rate,
                "ai_vs_human_success_count": ai_vs_human_count,
                "agent_efficiency": agent_efficiency,
                "qa_scores": qa_scores,
            }

            return json_safe(payload)

    async def _overall_success_rate(self, conn, company_id, start_time):
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (
                    WHERE NOT EXISTS (
                        SELECT 1 FROM "Ticket" t
                        WHERE t.meta_data->>'call_sid' = c.call_sid
                    )
                )::float / NULLIF(COUNT(*), 0) * 100 AS rate
            FROM "Call" c
            WHERE c.company_id = $1
            AND c.created_at >= $2
        """, company_id, start_time)

        return row["rate"] or 0.0

    async def _average_handle_time(self, conn, company_id, start_time):
        row = await conn.fetchrow("""
            SELECT AVG(duration) AS avg_time
            FROM "Call"
            WHERE company_id = $1
            AND created_at >= $2
            AND duration IS NOT NULL
        """, company_id, start_time)

        return row["avg_time"] or 0.0

    async def _first_call_resolution(self, conn, company_id, start_time):
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (
                    WHERE NOT EXISTS (
                        SELECT 1 FROM "Ticket" t
                        WHERE t.meta_data->>'call_sid' = c.call_sid
                    )
                )::float / NULLIF(COUNT(*), 0) * 100 AS fcr
            FROM "Call" c
            WHERE c.company_id = $1
            AND c.created_at >= $2
        """, company_id, start_time)

        return row["fcr"] or 0.0

    async def _ai_vs_human_count(self, conn, company_id, start_time):
        rows = await conn.fetch("""
            SELECT
                DATE(c.created_at) AS day,
                COUNT(*) FILTER (
                    WHERE NOT EXISTS (
                        SELECT 1 FROM "Ticket" t
                        WHERE t.meta_data->>'call_sid' = c.call_sid
                    )
                ) AS ai,
                COUNT(*) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM "Ticket" t
                        WHERE t.meta_data->>'call_sid' = c.call_sid
                    )
                ) AS human
            FROM "Call" c
            WHERE c.company_id = $1
            AND c.created_at >= $2
            GROUP BY day
            ORDER BY day
        """, company_id, start_time)

        return [
            {"date": r["day"].isoformat(), "ai": r["ai"], "human": r["human"]}
            for r in rows
        ]

    async def _ai_vs_human_rate(self, conn, company_id, start_time):
        rows = await conn.fetch("""
            SELECT
                DATE(c.created_at) AS day,
                COUNT(*) FILTER (
                    WHERE NOT EXISTS (
                        SELECT 1 FROM "Ticket" t
                        WHERE t.meta_data->>'call_sid' = c.call_sid
                    )
                ) AS ai,
                COUNT(*) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM "Ticket" t
                        WHERE t.meta_data->>'call_sid' = c.call_sid
                    )
                ) AS human
            FROM "Call" c
            WHERE c.company_id = $1
            AND c.created_at >= $2
            GROUP BY day
            ORDER BY day
        """, company_id, start_time)

        result = []
        for r in rows:
            total = r["ai"] + r["human"]
            result.append({
                "date": r["day"].isoformat(),
                "ai": round((r["ai"] / total) * 100, 2) if total else 0,
                "human": round((r["human"] / total) * 100, 2) if total else 0
            })

        return result

    async def _agent_efficiency(self, conn, company_id, start_time):
        rows = await conn.fetch("""
            SELECT
                an.agent_id,
                COUNT(*) AS calls_handled,
                COUNT(*) FILTER (
                    WHERE NOT EXISTS (
                        SELECT 1 FROM "Ticket" t
                        WHERE t.meta_data->>'call_sid' = c.call_sid
                    )
                )::float / COUNT(*) * 100 AS resolution_rate
            FROM "Call" c
            JOIN "AgentNumber" an
              ON an.phone_number = c.from_number
            WHERE c.company_id = $1
            AND c.created_at >= $2
            GROUP BY an.agent_id
        """, company_id, start_time)

        return [
            {
                "agent_id": r["agent_id"],
                "calls_handled": r["calls_handled"],
                "resolution_rate": r["resolution_rate"] or 0.0
            }
            for r in rows
        ]

    async def _quality_score(self, conn, company_id, start_time):
        """
        Deterministic fallback QA scoring:
        - Script adherence: transcript exists
        - Accuracy: duration > 60s
        - Compliance: no ticket
        - Customer satisfaction: booking OR long call
        
        OPTIMIZED: Uses direct call_sid joins
        """

        rows = await conn.fetch("""
            SELECT
                c.call_sid,
                c.duration,
                c.transcription,
                b.id IS NOT NULL AS has_booking,
                t.id IS NOT NULL AS has_ticket
            FROM "Call" c
            LEFT JOIN "Ticket" t 
                ON t.meta_data->>'call_sid' = c.call_sid
            LEFT JOIN booking b 
                ON b.call_sid = c.call_sid
            WHERE c.company_id = $1
            AND c.created_at >= $2
        """, company_id, start_time)

        if not rows:
            return 0.0, {
                "script_adherence": 0.0,
                "accuracy": 0.0,
                "compliance": 0.0,
                "customer_satisfaction": 0.0
            }

        sa = acc = comp = csat = 0

        for r in rows:
            if r["transcription"]:
                sa += 1
            if r["duration"] and r["duration"] > 60:
                acc += 1
            if not r["has_ticket"]:
                comp += 1
            if r["has_booking"] or (r["duration"] and r["duration"] > 90):
                csat += 1

        total = len(rows)

        scores = {
            "script_adherence": round((sa / total) * 100, 2),
            "accuracy": round((acc / total) * 100, 2),
            "compliance": round((comp / total) * 100, 2),
            "customer_satisfaction": round((csat / total) * 100, 2)
        }

        quality_score = round(
            scores["script_adherence"] * 0.25 +
            scores["accuracy"] * 0.24 +
            scores["compliance"] * 0.26 +
            scores["customer_satisfaction"] * 0.24,
            2
        )

        return quality_score, scores


company_metrics_service = CompanyMetricsService()
