import os
from app.db.postgres import BasePostgresClient
from config import config

class DatabaseClient:
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            env = os.getenv('FLASK_ENV', 'development')
            app_config = config.get(env, config['default'])
            
            self._client = BasePostgresClient(
                connection_string=app_config.DATABASE_URL,
                pool_limit_min=5,
                pool_limit_max=20
            )
    
    @property
    def client(self) -> BasePostgresClient:
        return self._client
    
    def close(self):
        if self._client:
            self._client.close_all_connections()

postgres_client = DatabaseClient()

# Add this function that your handler is trying to import
async def get_db_connection():
    """Return a database connection from the pool"""
    return await postgres_client.client.get_connection()