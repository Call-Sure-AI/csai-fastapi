from datetime import datetime, timedelta
from app.db.postgres_client import get_db_connection
from app.db.queries.activity_log_queries import ActivityLogQueries
import logging

logger = logging.getLogger(__name__)

EVENT_LABELS = {
    ("CREATE", "AGENT"): "Project Created",
    ("UPDATE", "COMPANY"): "Settings Updated",
    ("DELETE", "DOCUMENT"): "Document Deleted",
    ("LOGIN", "USER"): "User Login",
    ("INVITE", "USER"): "User Invited",
}

def parse_date_range(range_str):
    """Parse strings like '7d', '30d', '1y', '6m' into a timedelta"""
    if not range_str:
        return None

    import re
    match = re.match(r'^(\d+)([dwmy])$', range_str.lower())
    if not match:
        return None
    
    value, unit = int(match.group(1)), match.group(2)
    
    if unit == 'd':
        return timedelta(days=value)
    elif unit == 'w':
        return timedelta(weeks=value)
    elif unit == 'm':
        return timedelta(days=value * 30)
    elif unit == 'y':
        return timedelta(days=value * 365)
    
    return None

class ActivityLogService:

    def __init__(self):
        self.queries = ActivityLogQueries()

    def _format_event(self, row):
        metadata = row["metadata"] or {}
        action = row["action"]
        entity_type = row["entity_type"]

        event_label = EVENT_LABELS.get(
            (action, entity_type),
            f"{action.title()} {entity_type.title()}"
        )

        details = "Activity performed"
        if action == "CREATE" and "name" in metadata:
            details = f'Created "{metadata["name"]}"'
        elif action == "UPDATE":
            details = "Updated settings"
        elif action == "INVITE":
            details = f'Invited {metadata.get("email")} as {metadata.get("role")}'

        created_at = row["created_at"]

        return {
            "event": event_label,
            "details": details,
            "time": created_at.strftime("%I:%M %p"),
            "date": created_at.strftime("%b %d"),

            "user": {
                "id": row["user_id"],
                "email": row["user_email"],
                "initial": row["user_email"][0].upper()
            },

            "activity": {
                "id": row["id"],
                "user_id": row["user_id"],
                "action": row["action"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "metadata": metadata,
                "created_at": created_at.isoformat()
            }
        }

    async def get_activity_log(
        self,
        company_id: str,
        range: str = "7d",
        limit: int = 50,
        offset: int = 0
    ):
        logger.info(
            "ActivityLogService.get_activity_log called | "
            f"company_id={company_id} range={range} limit={limit} offset={offset}"
        )

        now = datetime.utcnow()

        delta = parse_date_range(range)
        start_date = (now - delta) if delta else None

        logger.info(
            "Computed date range | "
            f"start_date={start_date} end_date={now}"
        )

        async with await get_db_connection() as conn:
            logger.info("DB connection acquired")

            rows = await self.queries.fetch_activity_logs(
                conn=conn,
                company_id=company_id,
                start_date=start_date,
                end_date=now,
                limit=limit,
                offset=offset
            )

            logger.info(
                "fetch_activity_logs returned | "
                f"row_count={len(rows)}"
            )

            if rows:
                logger.info(f"First row sample: {dict(rows[0])}")
            else:
                logger.warning("fetch_activity_logs returned EMPTY rows")

            summary = await self.queries.fetch_summary(conn, company_id, start_date, now)
            total = await self.queries.fetch_total_count(conn, company_id, start_date, now)

        events = []

        for r in rows:
            try:
                event = {
                    "action": r["action"],
                    "entity_type": r["entity_type"],
                    "entity_id": r["entity_id"],
                    "created_at": r["created_at"].isoformat(),

                    "user": {
                        "id": r["user_id"],
                        "name": r["user_name"],
                        "email": r["user_email"],
                    },

                    "metadata": r["metadata"] or {}
                }
                events.append(event)
            except Exception as e:
                logger.error(
                    "Failed to format activity row | "
                    f"row={dict(r)} error={e}",
                    exc_info=True
                )

        logger.info(
            "Final events constructed | "
            f"event_count={len(events)}"
        )

        return {
            "summary": dict(summary),
            "events": events,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total
            }
        }