import asyncio
from datetime import datetime
from app.db.postgres_client import get_db_connection

async def list_campaign_ids() -> None:
    query = """
        SELECT id, campaign_name, created_at
        FROM   Campaign
        ORDER  BY created_at DESC
    """

    async with await get_db_connection() as conn:
        rows = await conn.fetch(query)

    if not rows:
        print("⚠️  No campaigns found.")
        return

    print(f"{'Created (UTC)':19} | {'ID':<18} | Campaign Name")
    print("-" * 70)
    for r in rows:
        when = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
        print(f"{when} | {r['id']:<18} | {r['campaign_name']}")

if __name__ == "__main__":
    asyncio.run(list_campaign_ids())