from datetime import datetime, timedelta
from app.db.postgres_client import get_db_connection
from app.db.queries.activity_log_queries import ActivityLogQueries


EVENT_LABELS = {
    ("CREATE", "AGENT"): "Project Created",
    ("UPDATE", "COMPANY"): "Settings Updated",
    ("DELETE", "DOCUMENT"): "Document Deleted",
    ("LOGIN", "USER"): "User Login",
    ("INVITE", "USER"): "User Invited",
}


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
            # 🔹 UI-friendly formatted fields
            "event": event_label,
            "details": details,
            "time": created_at.strftime("%I:%M %p"),
            "date": created_at.strftime("%b %d"),

            # 🔹 User display
            "user": {
                "id": row["user_id"],
                "email": row["user_email"],
                "initial": row["user_email"][0].upper()
            },

            # 🔹 Raw DB data (FULL activity row)
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
        limit: int = 50,
        offset: int = 0
    ):
        async with await get_db_connection() as conn:
            rows = await self.queries.fetch_activity_logs(
                conn,
                company_id,
                limit,
                offset
            )

            summary = await self.queries.fetch_summary(conn, company_id)
            total = await self.queries.fetch_total_count(conn, company_id)

        events = [
            {
                "action": r["action"],
                "entity_type": r["entity_type"],
                "created_at": r["created_at"].isoformat(),
                "user": {
                    "id": r["user_id"],
                    "name": r["user_name"],
                    "email": r["user_email"],
                }
            }
            for r in rows
        ]

        return {
            "summary": dict(summary),
            "events": events,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total
            }
        }

