"""
Configuration management for Telegram userbot.
Loads settings from environment variables.
"""
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration container for the userbot."""
    
    # Telegram API credentials
    API_ID: int = int(os.getenv("API_ID", "0"))
    API_HASH: str = os.getenv("API_HASH", "")
    PHONE_NUMBER: str = os.getenv("PHONE_NUMBER", "")
    
    # Target user to forward messages to (DEPRECATED: Now loaded from database per request)
    # Can still be used as a fallback
    TARGET_USER_ID: int = int(os.getenv("TARGET_USER_ID", "0"))
    
    # Bot token for sending notifications
    TG_BOT_KEY: str = os.getenv("TG_BOT_KEY", "")
    
    # Keywords to filter messages (DEPRECATED: Now loaded from database per request)
    # Can still be used as a fallback
    KEYWORDS: List[str] = [
        kw.strip().lower() 
        for kw in os.getenv("KEYWORDS", "").split(",") 
        if kw.strip()
    ]
    
    # Session file name (stored in data directory)
    SESSION_NAME: str = os.getenv("SESSION_NAME", "data/userbot_session")
    
    # Polling interval for large groups (in seconds)
    # For large supergroups, Telegram doesn't push updates, so we poll periodically
    POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "30"))
    
    # Hardcoded chat IDs to monitor (DEPRECATED: Now loaded from database per request)
    # Can still be used as a fallback
    CHAT_IDS: List[str] = []
    
    # Database configuration
    # DB_HOST should be:
    #   - "postgres" when running in Docker (connects via Docker network)
    #   - "localhost" when running locally outside Docker
    DB_HOST: str = os.getenv("DB_HOST", "postgres")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "find_brilliant")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    
    @classmethod
    def validate(cls) -> None:
        """Validate that all required configuration is present."""
        errors = []
        
        if not cls.API_ID or cls.API_ID == 0:
            errors.append("API_ID is required")
        
        if not cls.API_HASH:
            errors.append("API_HASH is required")
        
        if not cls.PHONE_NUMBER:
            errors.append("PHONE_NUMBER is required (e.g., +79933707439)")
        
        if not cls.TG_BOT_KEY:
            errors.append("TG_BOT_KEY is required")
        
        # Note: TARGET_USER_ID, KEYWORDS, and CHAT_IDS are now optional
        # They are loaded from the database per search request
        
        # Database validation
        if not cls.DB_HOST:
            errors.append("DB_HOST is required")
        
        if not cls.DB_NAME:
            errors.append("DB_NAME is required")
        
        if not cls.DB_USER:
            errors.append("DB_USER is required")
        
        if not cls.DB_PASSWORD:
            errors.append("DB_PASSWORD is required")
        
        if errors:
            raise ValueError(
                "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )
    
    @classmethod
    def display(cls) -> None:
        """Display current configuration (for debugging)."""
        print("=" * 60)
        print("🤖 Telegram Userbot Configuration")
        print("=" * 60)
        print(f"API_ID: {cls.API_ID}")
        print(f"API_HASH: {'*' * len(cls.API_HASH) if cls.API_HASH else '(not set)'}")
        print(f"PHONE_NUMBER: {cls.PHONE_NUMBER if cls.PHONE_NUMBER else '(not set)'}")
        print(f"TG_BOT_KEY: {'*' * 10 if cls.TG_BOT_KEY else '(not set)'}")
        print(f"SESSION_NAME: {cls.SESSION_NAME}")
        print(f"POLL_INTERVAL: {cls.POLL_INTERVAL}s")
        print("")
        print("📊 Database Configuration:")
        print(f"DB_HOST: {cls.DB_HOST}")
        print(f"DB_PORT: {cls.DB_PORT}")
        print(f"DB_NAME: {cls.DB_NAME}")
        print(f"DB_USER: {cls.DB_USER}")
        print("")
        print("ℹ️  Monitoring configuration loaded from database")
        print("   Use /search command in bot to create search requests")
        print("=" * 60)

