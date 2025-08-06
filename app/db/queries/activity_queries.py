from typing import List, Dict, Any, Optional
import asyncpg
import json
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

class ActivityQueries:
    
    async def create_activity(
        self, 
        conn: asyncpg.Connection, 
        user_id: str,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new activity log entry"""
        activity_id = str(uuid.uuid4())
        query = """
            INSERT INTO activities (
                id, user_id, action, entity_type, entity_id, metadata, created_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING *
        """
        
        metadata_json = json.dumps(metadata) if metadata else '{}'
        
        try:
            row = await conn.fetchrow(
                query,
                activity_id,
                user_id,
                action,
                entity_type,
                entity_id,
                metadata_json
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Database error in create_activity: {e}", exc_info=True)
            raise
    
    async def get_user_activities(
        self,
        conn: asyncpg.Connection,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get activities for a specific user"""
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
            FROM activities a  -- No quotes around activities
            LEFT JOIN "User" u ON a.user_id = u.id
            WHERE a.user_id = $1
        """
        params = [user_id]
        param_count = 2
        
        if entity_type:
            query += f" AND a.entity_type = ${param_count}"
            params.append(entity_type)
            param_count += 1
        
        query += " ORDER BY a.created_at DESC"
        query += f" LIMIT ${param_count} OFFSET ${param_count + 1}"
        params.extend([limit, offset])
        
        try:
            rows = await conn.fetch(query, *params)
            
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
            
            return activities
            
        except Exception as e:
            logger.error(f"Database error in get_user_activities: {e}", exc_info=True)
            return []
    
    async def get_activity_by_id(
        self,
        conn: asyncpg.Connection,
        activity_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single activity by ID"""
        query = """
            SELECT 
                a.*,
                u.name as user_name,
                u.email as user_email
            FROM activities a
            LEFT JOIN "User" u ON a.user_id = u.id
            WHERE a.id = $1
        """
        
        row = await conn.fetchrow(query, activity_id)
        if row:
            activity = dict(row)
            activity['user'] = {
                'name': activity.pop('user_name', None),
                'email': activity.pop('user_email', None)
            }
            return activity
        return None
    
    async def delete_activity(
        self,
        conn: asyncpg.Connection,
        activity_id: str
    ) -> bool:
        """Delete an activity"""
        query = """
            DELETE FROM activities
            WHERE id = $1
            RETURNING id
        """
        
        row = await conn.fetchrow(query, activity_id)
        return row is not None