"""Database connection module with connection pooling."""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor


class Database:
    """PostgreSQL database connection manager with connection pooling."""
    
    _instance: Database | None = None
    _pool: pool.SimpleConnectionPool | None = None
    
    def __new__(cls) -> Database:
        """Singleton pattern to ensure single connection pool."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if self._pool is None:
            self._init_pool()
    
    def _init_pool(self) -> None:
        """Initialize the connection pool from environment variables."""
        self._pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.getenv("DATABASE_HOST", "localhost"),
            port=int(os.getenv("DATABASE_PORT", "5432")),
            database=os.getenv("DATABASE_NAME", "berkay"),
            user=os.getenv("DATABASE_USER", "berkay"),
            password=os.getenv("DATABASE_PASSWORD", ""),
        )
    
    @contextmanager
    def get_connection(self) -> Generator:
        """Get a connection from the pool with automatic return."""
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, dict_cursor: bool = True) -> Generator:
        """Get a cursor with automatic connection management."""
        with self.get_connection() as conn:
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()
    
    def execute(self, query: str, params: tuple | None = None) -> None:
        """Execute a query without returning results."""
        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(query, params)
    
    def fetchone(self, query: str, params: tuple | None = None) -> dict | None:
        """Execute a query and return a single row as dict."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()
    
    def fetchall(self, query: str, params: tuple | None = None) -> list[dict]:
        """Execute a query and return all rows as list of dicts."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def fetchval(self, query: str, params: tuple | None = None) -> Any:
        """Execute a query and return a single value."""
        with self.get_cursor(dict_cursor=False) as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return row[0] if row else None
    
    def test_connection(self) -> bool:
        """Test if database connection is working."""
        try:
            result = self.fetchval("SELECT 1")
            return result == 1
        except Exception as e:
            print(f"Database connection failed: {e}")
            return False
    
    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
            Database._instance = None
