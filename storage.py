"""
Storage layer for duplicate message detection.
Keeps track of processed messages to prevent duplicate actions.
"""
import sqlite3
from typing import Set, Tuple
from pathlib import Path


class MessageStorage:
    """
    Storage for tracking processed messages.
    Uses SQLite for persistence across restarts.
    """
    
    def __init__(self, db_path: str = "processed_messages.db"):
        """
        Initialize the storage.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self) -> None:
        """Create the database table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, message_id)
            )
        """)
        
        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_messages 
            ON processed_messages (chat_id, message_id)
        """)
        
        conn.commit()
        conn.close()
    
    def is_processed(self, chat_id: int, message_id: int) -> bool:
        """
        Check if a message has already been processed.
        
        Args:
            chat_id: Telegram chat ID
            message_id: Telegram message ID
            
        Returns:
            True if message was already processed, False otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT 1 FROM processed_messages WHERE chat_id = ? AND message_id = ?",
            (chat_id, message_id)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
    
    def mark_processed(self, chat_id: int, message_id: int) -> None:
        """
        Mark a message as processed.
        
        Args:
            chat_id: Telegram chat ID
            message_id: Telegram message ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO processed_messages (chat_id, message_id) VALUES (?, ?)",
                (chat_id, message_id)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # Already exists, ignore
            pass
        finally:
            conn.close()
    
    def cleanup_old_records(self, days: int = 30) -> int:
        """
        Remove old processed message records to prevent database bloat.
        
        Args:
            days: Remove records older than this many days
            
        Returns:
            Number of records deleted
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            DELETE FROM processed_messages 
            WHERE processed_at < datetime('now', '-' || ? || ' days')
            """,
            (days,)
        )
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted
    
    def get_stats(self) -> dict:
        """
        Get statistics about processed messages.
        
        Returns:
            Dictionary with statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM processed_messages")
        total = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM processed_messages 
            WHERE processed_at > datetime('now', '-1 day')
        """)
        last_24h = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_processed": total,
            "last_24h": last_24h
        }


class InMemoryStorage:
    """
    In-memory storage for tracking processed messages.
    Faster but does not persist across restarts.
    """
    
    def __init__(self):
        """Initialize the in-memory storage."""
        self._processed: Set[Tuple[int, int]] = set()
    
    def is_processed(self, chat_id: int, message_id: int) -> bool:
        """
        Check if a message has already been processed.
        
        Args:
            chat_id: Telegram chat ID
            message_id: Telegram message ID
            
        Returns:
            True if message was already processed, False otherwise
        """
        return (chat_id, message_id) in self._processed
    
    def mark_processed(self, chat_id: int, message_id: int) -> None:
        """
        Mark a message as processed.
        
        Args:
            chat_id: Telegram chat ID
            message_id: Telegram message ID
        """
        self._processed.add((chat_id, message_id))
    
    def get_stats(self) -> dict:
        """
        Get statistics about processed messages.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "total_processed": len(self._processed)
        }


