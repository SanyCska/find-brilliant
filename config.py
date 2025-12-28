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
    
    # Target user to forward messages to
    TARGET_USER_ID: int = int(os.getenv("TARGET_USER_ID", "0"))
    
    # Bot token for sending notifications
    TG_BOT_KEY: str = os.getenv("TG_BOT_KEY", "")
    
    # Keywords to filter messages (comma-separated)
    KEYWORDS: List[str] = [
        kw.strip().lower() 
        for kw in os.getenv("KEYWORDS", "").split(",") 
        if kw.strip()
    ]
    
    # Auto-reply settings
    AUTO_REPLY_ENABLED: bool = os.getenv("AUTO_REPLY_ENABLED", "false").lower() == "true"
    AUTO_REPLY_TEXT: str = os.getenv("AUTO_REPLY_TEXT", "Interested!")
    AUTO_REPLY_MIN_DELAY: int = int(os.getenv("AUTO_REPLY_MIN_DELAY", "5"))
    AUTO_REPLY_MAX_DELAY: int = int(os.getenv("AUTO_REPLY_MAX_DELAY", "15"))
    
    # Session file name (stored in data directory)
    SESSION_NAME: str = os.getenv("SESSION_NAME", "data/userbot_session")
    
    # Polling interval for large groups (in seconds)
    # For large supergroups, Telegram doesn't push updates, so we poll periodically
    POLL_INTERVAL: int = int(os.getenv("POLL_INTERVAL", "30"))
    
    # Hardcoded chat IDs to monitor (can be usernames like "@channel" or numeric IDs)
    # TODO: Move to environment variable if needed
    CHAT_IDS: List[str] = [
        "@NSbaraholka",
        "@test_brilliant",
        "@serbiasell",
        -1001645328052,
        "@serbska_baraholka",
        "@MagicChestNS",
    ]
    
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
        
        if not cls.TARGET_USER_ID or cls.TARGET_USER_ID == 0:
            errors.append("TARGET_USER_ID is required")
        
        if not cls.TG_BOT_KEY:
            errors.append("TG_BOT_KEY is required")
        
        if not cls.KEYWORDS:
            errors.append("KEYWORDS is required (comma-separated list)")
        
        if cls.AUTO_REPLY_ENABLED and not cls.AUTO_REPLY_TEXT:
            errors.append("AUTO_REPLY_TEXT is required when AUTO_REPLY_ENABLED is true")
        
        if not cls.CHAT_IDS:
            errors.append("CHAT_IDS must be configured in config.py (hardcoded)")
        
        # Check for empty strings in CHAT_IDS
        empty_chats = [i for i, chat in enumerate(cls.CHAT_IDS) if not chat or not str(chat).strip()]
        if empty_chats:
            errors.append(f"CHAT_IDS contains empty values at positions: {empty_chats}")
        
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
        print(f"TARGET_USER_ID: {cls.TARGET_USER_ID}")
        print(f"KEYWORDS: {cls.KEYWORDS}")
        print(f"CHAT_IDS: {cls.CHAT_IDS}")
        print(f"AUTO_REPLY_ENABLED: {cls.AUTO_REPLY_ENABLED}")
        if cls.AUTO_REPLY_ENABLED:
            print(f"AUTO_REPLY_TEXT: {cls.AUTO_REPLY_TEXT}")
            print(f"AUTO_REPLY_DELAY: {cls.AUTO_REPLY_MIN_DELAY}-{cls.AUTO_REPLY_MAX_DELAY}s")
        print(f"SESSION_NAME: {cls.SESSION_NAME}")
        print("=" * 60)

