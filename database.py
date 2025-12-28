"""
Database module for PostgreSQL interactions.
Provides functions to manage users, search requests, keywords, and groups.
"""
import os
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool


class Database:
    """Database manager for PostgreSQL operations."""
    
    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        min_connections: int = 1,
        max_connections: int = 10
    ):
        """
        Initialize database connection pool.
        
        Args:
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            user: Database user
            password: Database password
            min_connections: Minimum number of connections in pool
            max_connections: Maximum number of connections in pool
        """
        self.connection_pool = SimpleConnectionPool(
            min_connections,
            max_connections,
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for getting a database connection from the pool.
        
        Yields:
            psycopg2 connection
        """
        conn = self.connection_pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self.connection_pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, cursor_factory=RealDictCursor):
        """
        Context manager for getting a cursor.
        
        Args:
            cursor_factory: Cursor factory class (default: RealDictCursor)
        
        Yields:
            Database cursor
        """
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()
    
    def close(self):
        """Close all connections in the pool."""
        if self.connection_pool:
            self.connection_pool.closeall()
    
    # ========== USER OPERATIONS ==========
    
    def create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> int:
        """
        Create a new user or return existing user ID.
        
        Args:
            telegram_id: Telegram user ID
            username: Telegram username (optional)
            first_name: User's first name (optional)
            last_name: User's last name (optional)
        
        Returns:
            User ID (internal database ID)
        """
        with self.get_cursor() as cursor:
            # Try to insert, on conflict do nothing and return existing ID
            cursor.execute("""
                INSERT INTO users (telegram_id, username, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (telegram_id) DO UPDATE
                SET username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name
                RETURNING id
            """, (telegram_id, username, first_name, last_name))
            result = cursor.fetchone()
            return result['id']
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user by Telegram ID.
        
        Args:
            telegram_id: Telegram user ID
        
        Returns:
            User dictionary or None if not found
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT id, telegram_id, username, first_name, last_name, created_at
                FROM users
                WHERE telegram_id = %s
            """, (telegram_id,))
            return cursor.fetchone()
    
    # ========== SEARCH REQUEST OPERATIONS ==========
    
    def create_search_request(
        self,
        user_id: int,
        title: Optional[str] = None,
        is_active: bool = True
    ) -> int:
        """
        Create a new search request.
        
        Args:
            user_id: Internal user ID
            title: Optional search request title
            is_active: Whether the request is active (default: True)
        
        Returns:
            Search request ID
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO search_requests (user_id, title, is_active)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (user_id, title, is_active))
            result = cursor.fetchone()
            return result['id']
    
    def get_search_request(self, request_id: int) -> Optional[Dict[str, Any]]:
        """
        Get search request by ID.
        
        Args:
            request_id: Search request ID
        
        Returns:
            Search request dictionary or None if not found
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT id, user_id, title, is_active, created_at
                FROM search_requests
                WHERE id = %s
            """, (request_id,))
            return cursor.fetchone()
    
    def get_user_search_requests(
        self,
        user_id: int,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all search requests for a user.
        
        Args:
            user_id: Internal user ID
            active_only: If True, return only active requests
        
        Returns:
            List of search request dictionaries
        """
        with self.get_cursor() as cursor:
            query = """
                SELECT id, user_id, title, is_active, created_at
                FROM search_requests
                WHERE user_id = %s
            """
            params = [user_id]
            
            if active_only:
                query += " AND is_active = true"
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def update_search_request_status(self, request_id: int, is_active: bool) -> bool:
        """
        Update search request active status.
        
        Args:
            request_id: Search request ID
            is_active: New active status
        
        Returns:
            True if updated, False if not found
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE search_requests
                SET is_active = %s
                WHERE id = %s
            """, (is_active, request_id))
            return cursor.rowcount > 0
    
    def delete_search_request(self, request_id: int) -> bool:
        """
        Delete a search request (cascades to keywords and groups).
        
        Args:
            request_id: Search request ID
        
        Returns:
            True if deleted, False if not found
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM search_requests
                WHERE id = %s
            """, (request_id,))
            return cursor.rowcount > 0
    
    # ========== KEYWORD OPERATIONS ==========
    
    def add_keyword(self, search_request_id: int, keyword: str) -> int:
        """
        Add a keyword to a search request.
        
        Args:
            search_request_id: Search request ID
            keyword: Keyword text (will be normalized to lowercase)
        
        Returns:
            Keyword ID
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO search_request_keywords (search_request_id, keyword)
                VALUES (%s, %s)
                RETURNING id
            """, (search_request_id, keyword.lower()))
            result = cursor.fetchone()
            return result['id']
    
    def add_keywords(self, search_request_id: int, keywords: List[str]) -> List[int]:
        """
        Add multiple keywords to a search request.
        
        Args:
            search_request_id: Search request ID
            keywords: List of keyword texts (will be normalized to lowercase)
        
        Returns:
            List of keyword IDs
        """
        keyword_ids = []
        for keyword in keywords:
            keyword_id = self.add_keyword(search_request_id, keyword)
            keyword_ids.append(keyword_id)
        return keyword_ids
    
    def get_keywords(self, search_request_id: int) -> List[Dict[str, Any]]:
        """
        Get all keywords for a search request.
        
        Args:
            search_request_id: Search request ID
        
        Returns:
            List of keyword dictionaries
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT id, search_request_id, keyword
                FROM search_request_keywords
                WHERE search_request_id = %s
            """, (search_request_id,))
            return cursor.fetchall()
    
    def delete_keyword(self, keyword_id: int) -> bool:
        """
        Delete a keyword.
        
        Args:
            keyword_id: Keyword ID
        
        Returns:
            True if deleted, False if not found
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM search_request_keywords
                WHERE id = %s
            """, (keyword_id,))
            return cursor.rowcount > 0
    
    # ========== TELEGRAM GROUPS OPERATIONS ==========
    
    def create_or_update_telegram_group(
        self,
        telegram_group_id: int,
        username: Optional[str] = None,
        title: Optional[str] = None
    ) -> int:
        """
        Create or update a Telegram group in the telegram_groups table.
        Uses INSERT ... ON CONFLICT to upsert.
        
        Args:
            telegram_group_id: Telegram group/channel ID
            username: Group username (optional)
            title: Group title (optional)
        
        Returns:
            Telegram group ID
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO telegram_groups (telegram_group_id, username, title, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (telegram_group_id) DO UPDATE
                SET username = EXCLUDED.username,
                    title = EXCLUDED.title,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING telegram_group_id
            """, (telegram_group_id, username, title))
            result = cursor.fetchone()
            return result['telegram_group_id']
    
    def get_telegram_group(self, telegram_group_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a Telegram group by ID.
        
        Args:
            telegram_group_id: Telegram group/channel ID
        
        Returns:
            Group dictionary or None if not found
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT telegram_group_id, username, title, created_at, updated_at
                FROM telegram_groups
                WHERE telegram_group_id = %s
            """, (telegram_group_id,))
            return cursor.fetchone()
    
    # ========== GROUP OPERATIONS ==========
    
    def add_group(
        self,
        search_request_id: int,
        telegram_group_id: int,
        username: Optional[str] = None,
        title: Optional[str] = None
    ) -> int:
        """
        Add a Telegram group to a search request.
        First ensures the group exists in telegram_groups table,
        then creates the link in search_request_groups.
        
        Args:
            search_request_id: Search request ID
            telegram_group_id: Telegram group/channel ID
            username: Group username (optional)
            title: Group title (optional)
        
        Returns:
            search_request_groups entry ID
        """
        with self.get_cursor() as cursor:
            # First, ensure the group exists in telegram_groups
            self.create_or_update_telegram_group(telegram_group_id, username, title)
            
            # Then create the link in search_request_groups
            cursor.execute("""
                INSERT INTO search_request_groups 
                (search_request_id, telegram_group_id)
                VALUES (%s, %s)
                ON CONFLICT (search_request_id, telegram_group_id) DO NOTHING
                RETURNING id
            """, (search_request_id, telegram_group_id))
            result = cursor.fetchone()
            
            # If ON CONFLICT triggered (duplicate), get the existing ID
            if result is None:
                cursor.execute("""
                    SELECT id FROM search_request_groups
                    WHERE search_request_id = %s AND telegram_group_id = %s
                """, (search_request_id, telegram_group_id))
                result = cursor.fetchone()
            
            return result['id']
    
    def add_groups(
        self,
        search_request_id: int,
        groups: List[Dict[str, Any]]
    ) -> List[int]:
        """
        Add multiple groups to a search request.
        
        Args:
            search_request_id: Search request ID
            groups: List of group dictionaries with keys:
                   - telegram_group_id (required)
                   - username (optional)
                   - title (optional)
        
        Returns:
            List of group IDs
        """
        group_ids = []
        for group in groups:
            group_id = self.add_group(
                search_request_id,
                group['telegram_group_id'],
                group.get('username'),
                group.get('title')
            )
            group_ids.append(group_id)
        return group_ids
    
    def get_groups(self, search_request_id: int) -> List[Dict[str, Any]]:
        """
        Get all groups for a search request.
        Joins with telegram_groups table to get full group info.
        
        Args:
            search_request_id: Search request ID
        
        Returns:
            List of group dictionaries with full info
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    srg.id,
                    srg.search_request_id,
                    tg.telegram_group_id,
                    tg.username,
                    tg.title,
                    tg.created_at as group_created_at,
                    srg.created_at as added_at
                FROM search_request_groups srg
                JOIN telegram_groups tg ON srg.telegram_group_id = tg.telegram_group_id
                WHERE srg.search_request_id = %s
            """, (search_request_id,))
            return cursor.fetchall()
    
    def delete_group(self, group_id: int) -> bool:
        """
        Delete a group from a search request.
        
        Args:
            group_id: Group ID
        
        Returns:
            True if deleted, False if not found
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM search_request_groups
                WHERE id = %s
            """, (group_id,))
            return cursor.rowcount > 0
    
    # ========== COMPLEX QUERIES ==========
    
    def get_all_active_search_requests_with_details(self) -> List[Dict[str, Any]]:
        """
        Get all active search requests with their keywords and groups.
        
        Returns:
            List of dictionaries containing:
            - request info (id, user_id, title)
            - keywords (list)
            - groups (list with full info from telegram_groups)
        """
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    sr.id,
                    sr.user_id,
                    sr.title,
                    sr.created_at,
                    u.telegram_id as user_telegram_id,
                    u.username as user_username,
                    COALESCE(
                        json_agg(
                            DISTINCT jsonb_build_object(
                                'id', k.id,
                                'keyword', k.keyword
                            )
                        ) FILTER (WHERE k.id IS NOT NULL),
                        '[]'
                    ) as keywords,
                    COALESCE(
                        json_agg(
                            DISTINCT jsonb_build_object(
                                'id', srg.id,
                                'telegram_group_id', tg.telegram_group_id,
                                'username', tg.username,
                                'title', tg.title
                            )
                        ) FILTER (WHERE srg.id IS NOT NULL),
                        '[]'
                    ) as groups
                FROM search_requests sr
                JOIN users u ON sr.user_id = u.id
                LEFT JOIN search_request_keywords k ON sr.id = k.search_request_id
                LEFT JOIN search_request_groups srg ON sr.id = srg.search_request_id
                LEFT JOIN telegram_groups tg ON srg.telegram_group_id = tg.telegram_group_id
                WHERE sr.is_active = true
                GROUP BY sr.id, u.telegram_id, u.username
                ORDER BY sr.created_at DESC
            """)
            return cursor.fetchall()


def get_database_from_env() -> Database:
    """
    Create a Database instance from environment variables.
    
    Environment variables:
        - DB_HOST: PostgreSQL host (default: localhost)
        - DB_PORT: PostgreSQL port (default: 5432)
        - DB_NAME: Database name (default: find_brilliant)
        - DB_USER: Database user (default: postgres)
        - DB_PASSWORD: Database password (required)
    
    Returns:
        Database instance
    """
    return Database(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', '5432')),
        database=os.getenv('DB_NAME', 'find_brilliant'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
    )

