from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class QueryHelpers:
    """Helper functions for query operations"""
    
    @staticmethod
    def generate_uuid() -> str:
        """Generate UUID string"""
        return str(uuid.uuid4())
    
    @staticmethod
    def format_datetime(dt: datetime = None) -> datetime:
        """Format datetime for database"""
        return dt or datetime.utcnow()
    
    @staticmethod
    def prepare_user_data(email: str, name: str, image: str = None) -> Dict[str, Any]:
        """Prepare user data for database insertion"""
        return {
            'id': QueryHelpers.generate_uuid(),
            'email': email,
            'name': name,
            'image': image,
            'created_at': QueryHelpers.format_datetime(),
            'updated_at': QueryHelpers.format_datetime()
        }
    
    @staticmethod
    def prepare_account_data(
        userId: str, 
        account_type: str, 
        provider: str, 
        provider_account_id: str,
        access_token: str = None
    ) -> Dict[str, Any]:
        """Prepare account data for database insertion"""
        return {
            'id': QueryHelpers.generate_uuid(),
            'userId': userId,
            'type': account_type,
            'provider': provider,
            'provider_account_id': provider_account_id,
            'access_token': access_token,
            'created_at': QueryHelpers.format_datetime()
        }
    
    @staticmethod
    def validate_query_result(result: List[Dict], expected_count: int = 1) -> bool:
        """Validate query result"""
        return len(result) == expected_count if expected_count > 0 else len(result) > 0
    
    @staticmethod
    def safe_get_first(result: List[Dict]) -> Optional[Dict]:
        """Safely get first result from query"""
        return result[0] if result else None
    
    @staticmethod
    def extract_ids(results: List[Dict], id_field: str = 'id') -> List[str]:
        """Extract IDs from query results"""
        return [str(item[id_field]) for item in results if id_field in item]