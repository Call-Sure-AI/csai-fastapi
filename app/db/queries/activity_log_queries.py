from datetime import datetime
from typing import Optional
from asyncpg import Connection
import logging

logger = logging.getLogger(__name__)

class ActivityLogQueries:

    async def fetch_activity_logs(
        self,
        conn,
        company_id: str,
        start_date,
        end_date,
        limit: int,
        offset: int
    ):
        logger.info(
            "fetch_activity_logs called | "
            f"company_id={company_id} start_date={start_date} "
            f"end_date={end_date} limit={limit} offset={offset}"
        )

        query = """
            SELECT
                a.id,
                a.user_id,
                a.action,
                a.entity_type,
                a.entity_id,
                a.metadata,
                a.created_at,

                u.name   AS user_name,
                u.email  AS user_email

            FROM activities a
            JOIN "User" u
                ON u.id = a.user_id
            JOIN "Company" c
                ON c.user_id = a.user_id

            WHERE c.id = $1
        """

        params = [company_id]
        param_index = 2

        if start_date:
            query += f" AND a.created_at >= ${param_index}"
            params.append(start_date)
            param_index += 1

        if end_date:
            query += f" AND a.created_at <= ${param_index}"
            params.append(end_date)
            param_index += 1

        query += f"""
            ORDER BY a.created_at DESC
            LIMIT ${param_index} OFFSET ${param_index + 1}
        """

        params.extend([limit, offset])

        logger.info(f"Final SQL:\n{query}")
        logger.info(f"SQL params: {params}")

        rows = await conn.fetch(query, *params)

        logger.info(
            "SQL executed | "
            f"rows_returned={len(rows)}"
        )

        return rows

    async def fetch_total_count(
        self,
        conn,
        company_id: str,
        start_date,
        end_date
    ):
        query = """
            SELECT COUNT(*) 
            FROM activities a
            JOIN "Company" c
                ON c.user_id = a.user_id
            WHERE c.id = $1
            AND a.created_at >= $2
            AND a.created_at <= $3
        """

        return await conn.fetchval(
            query,
            company_id,
            start_date,
            end_date
        )

    async def fetch_summary(
        self,
        conn,
        company_id: str,
        start_date,
        end_date
    ):
        query = """
            SELECT
                COUNT(*)                             AS total_events,
                COUNT(*) FILTER (WHERE a.action = 'CREATE') AS creates,
                COUNT(*) FILTER (WHERE a.action = 'UPDATE') AS updates,
                COUNT(*) FILTER (
                    WHERE a.created_at::date = CURRENT_DATE
                ) AS today
            FROM activities a
            JOIN "Company" c
                ON c.user_id = a.user_id
            WHERE c.id = $1
            AND a.created_at >= $2
            AND a.created_at <= $3
        """

        return await conn.fetchrow(
            query,
            company_id,
            start_date,
            end_date
        )




