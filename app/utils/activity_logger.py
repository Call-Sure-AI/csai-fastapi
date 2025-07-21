from typing import Dict, Any
from app.db.postgres_client import get_db_connection
import json
import logging

logger = logging.getLogger(__name__)

class ActivityLogger:
    
    async def log(self, activity_data: Dict[str, Any]):
        try:
            async with get_db_connection() as conn:
                query = """
                    INSERT INTO activities (user_id, action, entity_type, entity_id, metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5, NOW())
                """
                
                await conn.execute(
                    query,
                    activity_data['user_id'],
                    activity_data['action'],
                    activity_data['entity_type'],
                    activity_data['entity_id'],
                    json.dumps(activity_data.get('metadata', {}))
                )
                
        except Exception as error:
            logger.error(f"Failed to log activity: {error}")
