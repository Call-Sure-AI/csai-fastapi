from typing import Dict, Any, Optional, List
from app.db.postgres_client import get_db_connection
from app.db.queries.activity_queries import ActivityQueries
import logging

logger = logging.getLogger(__name__)

class ActivityLogger:
    def __init__(self):
        self.activity_queries = ActivityQueries()
    
    async def log(self, activity_data: Dict[str, Any]):
        """Log an activity to the database"""
        try:
            connection = await get_db_connection()
            async with connection as conn:
                await self.activity_queries.create_activity(
                    conn,
                    user_id=activity_data['user_id'],
                    action=activity_data['action'],
                    entity_type=activity_data['entity_type'],
                    entity_id=activity_data['entity_id'],
                    metadata=activity_data.get('metadata', {})
                )
        except Exception as error:
            logger.error(f"Failed to log activity: {error}")
    
    @staticmethod
    async def get_user_activity(
        user_id: str, 
        limit: int = 50, 
        offset: int = 0, 
        entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get activity log for a user"""
        try:
            connection = await get_db_connection()
            async with connection as conn:
                activity_queries = ActivityQueries()
                return await activity_queries.get_user_activities(
                    conn, user_id, limit, offset, entity_type
                )
        except Exception as e:
            logger.error(f"Failed to get user activity: {e}")
            return []