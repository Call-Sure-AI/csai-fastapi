import asyncpg
import asyncio
import json
from typing import List, Dict, Any, Optional, Tuple
from contextlib import asynccontextmanager
import logging

logger = logging.getLogger(__name__)

class AsyncPostgresClient:
    def __init__(self, connection_string: str, pool_min: int = 10, pool_max: int = 20):
        self.connection_string = connection_string
        self.pool_min = pool_min
        self.pool_max = pool_max
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialize the connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=self.pool_min,
                max_size=self.pool_max,
                # Optimizations for voice calling
                command_timeout=10,  # 10 second timeout
                server_settings={
                    'application_name': 'voice_calling_system',
                    'jit': 'off'  # Disable JIT for more predictable latency
                },
            )
            logger.info("Async PostgreSQL connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

    async def close(self):
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")

    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool as an async context manager"""
        if not self.pool:
            raise RuntimeError("Connection pool not initialized. Call initialize() first.")
        
        async with self.pool.acquire() as connection:
            yield connection

    async def execute_query(
        self, 
        query: str, 
        params: Optional[Tuple] = None,
        timeout: float = 5.0  # 5 second default timeout for voice calls
    ) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results as list of dicts"""
        try:
            async with self.get_connection() as conn:
                # Set query timeout for voice call latency requirements
                rows = await conn.fetch(query, *(params or []), timeout=timeout)
                return [dict(row) for row in rows] if rows else []
        except asyncio.TimeoutError:
            logger.error(f"Query timeout after {timeout}s: {query[:100]}...")
            raise
        except Exception as e:
            logger.error(f"Query error: {e}")
            raise

    async def execute_query_one(
        self, 
        query: str, 
        params: Optional[Tuple] = None,
        timeout: float = 5.0
    ) -> Optional[Dict[str, Any]]:
        """Execute a query and return single result"""
        try:
            async with self.get_connection() as conn:
                row = await conn.fetchrow(query, *(params or []), timeout=timeout)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Query error: {e}")
            raise

    async def execute_update(
        self, 
        query: str, 
        params: Optional[Tuple] = None,
        timeout: float = 5.0
    ) -> int:
        """Execute an UPDATE/DELETE query and return affected rows"""
        try:
            async with self.get_connection() as conn:
                result = await conn.execute(query, *(params or []), timeout=timeout)
                # Extract affected rows count from result
                return int(result.split()[-1]) if result else 0
        except Exception as e:
            logger.error(f"Update error: {e}")
            raise

    async def execute_insert(
        self, 
        query: str, 
        params: Optional[Tuple] = None,
        timeout: float = 5.0
    ) -> Optional[Dict[str, Any]]:
        """Execute INSERT query and return the inserted record"""
        try:
            async with self.get_connection() as conn:
                # For RETURNING queries
                if "RETURNING" in query.upper():
                    row = await conn.fetchrow(query, *(params or []), timeout=timeout)
                    return dict(row) if row else None
                else:
                    await conn.execute(query, *(params or []), timeout=timeout)
                    return None
        except Exception as e:
            logger.error(f"Insert error: {e}")
            raise

    async def execute_many(
        self, 
        query: str, 
        params_list: List[Tuple],
        timeout: float = 10.0
    ) -> None:
        """Execute multiple queries efficiently (batch insert/update)"""
        try:
            async with self.get_connection() as conn:
                await conn.executemany(query, params_list, timeout=timeout)
        except Exception as e:
            logger.error(f"Batch execution error: {e}")
            raise

    async def execute_transaction(
        self, 
        queries: List[Tuple[str, Optional[Tuple]]],
        timeout: float = 10.0
    ) -> List[Any]:
        """Execute multiple queries in a single transaction"""
        async with self.get_connection() as conn:
            async with conn.transaction():
                results = []
                for query, params in queries:
                    if "SELECT" in query.upper() or "RETURNING" in query.upper():
                        rows = await conn.fetch(query, *(params or []), timeout=timeout)
                        results.append([dict(row) for row in rows])
                    else:
                        result = await conn.execute(query, *(params or []), timeout=timeout)
                        results.append(result)
                return results

    # Voice calling specific optimizations
    async def get_agent_for_call(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Optimized query for getting agent during a call"""
        query = """
            SELECT id, name, prompt, company_id, type, is_active,
                   confidence_threshold, max_response_tokens, temperature
            FROM agents 
            WHERE id = $1 AND is_active = true
        """
        return await self.execute_query_one(query, (agent_id,), timeout=1.0)  # 1s timeout

    async def log_call_interaction(
        self, 
        call_id: str, 
        agent_id: str, 
        customer_input: str, 
        agent_response: str,
        confidence: float
    ) -> None:
        """Fast logging for voice interactions"""
        query = """
            INSERT INTO call_interactions 
            (call_id, agent_id, customer_input, agent_response, confidence_score, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
        """
        # Fire and forget pattern for logging (don't wait for result)
        asyncio.create_task(
            self.execute_insert(
                query, 
                (call_id, agent_id, customer_input, agent_response, confidence),
                timeout=2.0
            )
        )

    async def get_customer_context(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Get customer context quickly for voice calls"""
        query = """
            SELECT c.*, 
                   array_agg(
                       json_build_object(
                           'date', ch.created_at,
                           'summary', ch.summary
                       ) ORDER BY ch.created_at DESC
                   ) FILTER (WHERE ch.id IS NOT NULL) as recent_calls
            FROM customers c
            LEFT JOIN call_history ch ON c.id = ch.customer_id
            WHERE c.phone_number = $1
            GROUP BY c.id
            LIMIT 1
        """
        return await self.execute_query_one(query, (phone_number,), timeout=1.0)

    # Connection pool monitoring for voice system
    async def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        if not self.pool:
            return {"error": "Pool not initialized"}
        
        return {
            "size": self.pool.get_size(),
            "free_connections": self.pool.get_idle_size(),
            "used_connections": self.pool.get_size() - self.pool.get_idle_size(),
            "max_size": self.pool._maxsize,
            "min_size": self.pool._minsize
        }