from app.db.postgres_client import get_db_connection

async def add_cloned_voice(voice_id: str, name: str, sample_s3_url: str) -> dict:
    """
    Inserts a new cloned voice record into the database.
    Returns the newly created record.
    """
    query = """
        INSERT INTO cloned_voices (voice_id, name, sample_s3_url)
        VALUES ($1, $2, $3)
        RETURNING id, voice_id, name, sample_s3_url;
    """
    # --- FIX: Added 'await' before get_db_connection() ---
    async with await get_db_connection() as conn:
        record = await conn.fetchrow(query, voice_id, name, sample_s3_url)
        return dict(record)

async def add_generated_speech(text: str, s3_url: str, cloned_voice_id: int) -> dict:
    """
    Inserts a new generated speech record into the database.
    Returns the newly created record.
    """
    query = """
        INSERT INTO generated_speech (text_content, s3_url, cloned_voice_id)
        VALUES ($1, $2, $3)
        RETURNING id, s3_url;
    """
    # --- FIX: Added 'await' before get_db_connection() ---
    async with await get_db_connection() as conn:
        record = await conn.fetchrow(query, text, s3_url, cloned_voice_id)
        return dict(record)

async def get_all_cloned_voices() -> list[dict]:
    """
    Retrieves all cloned voice records from the database.
    """
    query = "SELECT id, voice_id, name, sample_s3_url FROM cloned_voices ORDER BY created_at DESC;"
    # --- FIX: Added 'await' before get_db_connection() ---
    async with await get_db_connection() as conn:
        records = await conn.fetch(query)
        return [dict(record) for record in records]

