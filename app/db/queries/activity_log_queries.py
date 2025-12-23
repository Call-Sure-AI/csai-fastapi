from datetime import datetime
from typing import Optional
from asyncpg import Connection


class ActivityLogQueries:

    async def fetch_activity_logs(
        self,
        conn,
        company_id: str,
        limit: int,
        offset: int
    ):
        query = """
            SELECT
                a.action,
                a.entity_type,
                a.created_at,
                u.id AS user_id,
                u.name AS user_name,
                u.email AS user_email
            FROM activities a
            JOIN "User" u ON u.id = a.user_id
            WHERE a.metadata->>'company_id' = $1
            ORDER BY a.created_at DESC
            LIMIT $2 OFFSET $3
        """

        return await conn.fetch(query, company_id, limit, offset)

    async def fetch_total_count(self, conn, company_id: str):
        query = """
            SELECT COUNT(*)
            FROM activities
            WHERE metadata->>'company_id' = $1
        """
        return await conn.fetchval(query, company_id)


    async def fetch_summary(self, conn, company_id: str):
        query = """
            SELECT
                COUNT(*) AS total_events,
                COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE) AS today,
                COUNT(*) FILTER (WHERE action = 'CREATE') AS creates,
                COUNT(*) FILTER (WHERE action = 'UPDATE') AS updates
            FROM activities
            WHERE metadata->>'company_id' = $1
        """
        return await conn.fetchrow(query, company_id)

