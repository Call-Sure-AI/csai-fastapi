from app.db.postgres_client import get_db_connection

async def create_agent_number(
    company_id: str,
    agent_id: str,
    agent_name: str,
    phone_number: str,
    service_type: str
):
    query = """
        INSERT INTO "AgentNumber" (
            company_id,
            agent_id,
            agent_name,
            phone_number,
            service_type
        )
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
    """

    async with await get_db_connection() as conn:
        return await conn.fetchrow(
            query,
            company_id,
            agent_id,
            agent_name,
            phone_number,
            service_type
        )
