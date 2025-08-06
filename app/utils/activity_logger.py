from typing import Dict, Any, Optional, List
from app.db.postgres_client import get_db_connection
import json
import logging

logger = logging.getLogger(__name__)

class ActivityLogger:
    
    async def log(self, activity_data: Dict[str, Any]):
        """Log an activity to the database"""
        try:
            connection = await get_db_connection()  # Get connection first
            async with connection as conn:  # Then use it as context manager
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
    
    @staticmethod
    async def get_user_activity(
        user_id: str, 
        limit: int = 50, 
        offset: int = 0, 
        entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get activity log for a user"""
        try:
            connection = await get_db_connection()  # Get connection first
            async with connection as conn:  # Then use it as context manager
                # Base query
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
                
                # Add entity_type filter if provided
                if entity_type:
                    query += " AND a.entity_type = $2"
                    params.append(entity_type)
                
                # Add ordering and pagination
                query += " ORDER BY a.created_at DESC"
                
                # Add limit and offset as parameters
                if entity_type:
                    query += f" LIMIT $3 OFFSET $4"
                    params.extend([limit, offset])
                else:
                    query += f" LIMIT $2 OFFSET $3"
                    params.extend([limit, offset])
                
                # Execute query
                rows = await conn.fetch(query, *params)
                
                # Format the response
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
                    
                    # Format the user info similar to Node.js version
                    activity['user'] = {
                        'name': activity.pop('user_name', None),
                        'email': activity.pop('user_email', None)
                    }
                    
                    # Convert datetime to ISO format string if needed
                    if activity.get('created_at'):
                        activity['created_at'] = activity['created_at'].isoformat()
                    
                    activities.append(activity)
                
                return activities
                
        except Exception as e:
            logger.error(f"Failed to get user activity: {e}")
            return []  # Return empty list on error instead of raising