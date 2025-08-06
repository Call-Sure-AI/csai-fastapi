from typing import Dict, Any, Optional, List
from app.db.postgres_client import get_db_connection
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class ActivityLogger:
    def __init__(self):
        pass  # Remove the activity_queries initialization here
    
    async def log(self, activity_data: Dict[str, Any]):
        """Log an activity to the database"""
        try:
            connection = await get_db_connection()
            async with connection as conn:
                from app.db.queries.activity_queries import ActivityQueries
                activity_queries = ActivityQueries()
                
                result = await activity_queries.create_activity(
                    conn,
                    user_id=activity_data['user_id'],
                    action=activity_data['action'],
                    entity_type=activity_data['entity_type'],
                    entity_id=activity_data['entity_id'],
                    metadata=activity_data.get('metadata', {})
                )
                logger.info(f"Activity logged: {result}")
                return result
        except Exception as error:
            logger.error(f"Failed to log activity: {error}", exc_info=True)
            return None
    
    @staticmethod
    async def get_user_activity(
        user_id: str, 
        limit: int = 50, 
        offset: int = 0, 
        entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get activity log for a user"""
        try:
            logger.info(f"ActivityLogger.get_user_activity called for user: {user_id}")
            
            connection = await get_db_connection()
            async with connection as conn:
                # Simple direct query that we know works
                query = """
                    SELECT 
                        a.id,
                        a.user_id,
                        a.action,
                        a.entity_type,
                        a.entity_id,
                        a.metadata,
                        a.created_at,
                        u.name as user_name,
                        u.email as user_email
                    FROM activities a
                    LEFT JOIN "User" u ON a.user_id = u.id
                    WHERE a.user_id = $1
                    ORDER BY a.created_at DESC
                    LIMIT $2 OFFSET $3
                """
                
                logger.info(f"Executing query with user_id={user_id}, limit={limit}, offset={offset}")
                rows = await conn.fetch(query, user_id, limit, offset)
                logger.info(f"Query returned {len(rows)} rows")
                
                activities = []
                for row in rows:
                    activity = dict(row)
                    
                    # Parse metadata if it's a JSON string
                    if activity.get('metadata'):
                        if isinstance(activity['metadata'], str):
                            try:
                                activity['metadata'] = json.loads(activity['metadata'])
                            except json.JSONDecodeError:
                                activity['metadata'] = {}
                    
                    # Format user info
                    activity['user'] = {
                        'name': activity.pop('user_name', None),
                        'email': activity.pop('user_email', None)
                    }
                    
                    # Convert datetime to ISO format
                    if activity.get('created_at'):
                        activity['created_at'] = activity['created_at'].isoformat()
                    
                    activities.append(activity)
                
                logger.info(f"Returning {len(activities)} formatted activities")
                return activities
                
        except Exception as e:
            logger.error(f"Failed to get user activity: {e}", exc_info=True)
            return []