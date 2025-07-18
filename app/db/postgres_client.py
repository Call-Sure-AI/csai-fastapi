from typing import List, Tuple, Dict
from psycopg3 import pool

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

    def close_all_connections(self):
        """
        Close all connections in the pool.
        """
        if self.pool:
            self.pool.closeall()
            print("All PostgreSQL connections closed")