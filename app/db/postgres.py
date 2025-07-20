from typing import List, Tuple, Dict, Optional, Any
from psycopg2 import pool
import json
from datetime import datetime
import uuid

class BasePostgresClient:
    def __init__(self, connection_string: str, pool_limit_min: int, pool_limit_max: int):
        self.connection_string = connection_string
        self.pool = pool.SimpleConnectionPool(
            pool_limit_min,
            pool_limit_max,
            self.connection_string
        )
        if self.pool:
            print("PostgreSQL connection pool created successfully")

    def execute_query(self, query: str, params: Tuple = None) -> List[Dict]:
        conn = None
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute(query, params)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                results = cursor.fetchall()
                return [dict(zip(columns, row)) for row in results]
            conn.commit()
            return []
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.pool.putconn(conn)

    def execute_update(self, query: str, params: Tuple = None) -> int:
        conn = None
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute(query, params)
            affected_rows = cursor.rowcount
            conn.commit()
            return affected_rows
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Database error: {e}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)

    def execute_insert(self, query: str, params: Tuple = None) -> Optional[Dict]:
        """Execute INSERT query and return the inserted record"""
        conn = None
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                result = cursor.fetchone()
                if result:
                    conn.commit()
                    return dict(zip(columns, result))
            
            conn.commit()
            return None
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.pool.putconn(conn)

    def execute_transaction(self, queries: List[Tuple[str, Tuple]]) -> List[Any]:
        """Execute multiple queries in a single transaction"""
        conn = None
        try:
            conn = self.pool.getconn()
            cursor = conn.cursor()
            results = []
            
            for query, params in queries:
                cursor.execute(query, params)
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    result = cursor.fetchall()
                    results.append([dict(zip(columns, row)) for row in result])
                else:
                    results.append(cursor.rowcount)
            
            conn.commit()
            return results
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.pool.putconn(conn)

    def close_all_connections(self):
        """Close all connections in the pool."""
        if self.pool:
            self.pool.closeall()
            print("All PostgreSQL connections closed")