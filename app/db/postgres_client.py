import os
import asyncio
from typing import Optional
from app.db.postgres import AsyncPostgresClient
from config import config
import logging

logger = logging.getLogger(__name__)

class DatabaseClient:
    _instance = None
    _client: Optional[AsyncPostgresClient] = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            env = os.getenv('FLASK_ENV', 'development')
            app_config = config.get(env, config['default'])
            
            self._client = AsyncPostgresClient(
                connection_string=app_config.DATABASE_URL,
                pool_min=10,  # Higher min for voice calls
                pool_max=50   # Higher max for concurrent calls
            )
    
    async def initialize(self):
        """Initialize the async connection pool"""
        if not self._initialized:
            await self._client.initialize()
            self._initialized = True
            logger.info("Database client initialized for voice calling system")
    
    @property
    def client(self) -> AsyncPostgresClient:
        if not self._initialized:
            # Log warning but don't raise error during import
            logger.warning("Database accessed before initialization. This is okay during import time.")
        return self._client
    
    async def close(self):
        if self._client and self._initialized:
            await self._client.close()
            self._initialized = False

# Create the singleton instance
postgres_client = DatabaseClient()

# Helper function for backward compatibility
async def get_db_connection():
    """Get a database connection (async context manager)"""
    if not postgres_client._initialized:
        await postgres_client.initialize()
    return postgres_client.client.get_connection()