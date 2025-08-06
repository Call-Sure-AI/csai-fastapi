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
                # Note: No quotes around activities table name
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
                """
                
                params = [user_id]
                
                if entity_type:
                    query += " AND a.entity_type = $2"
                    params.append(entity_type)
                
                query += " ORDER BY a.created_at DESC"
                
                if entity_type:
                    query += " LIMIT $3 OFFSET $4"
                    params.extend([limit, offset])
                else:
                    query += " LIMIT $2 OFFSET $3"
                    params.extend([limit, offset])
                
                rows = await conn.fetch(query, *params)
                
                activities = []
                for row in rows:
                    activity = dict(row)
                    
                    # Parse metadata if it's JSON
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
                
                logger.info(f"Found {len(activities)} activities for user {user_id}")
                return activities
                
        except Exception as e:
            logger.error(f"Failed to get user activity: {e}", exc_info=True)
            return []