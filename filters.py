"""
Message filtering logic for keyword matching.
"""
from typing import List, Optional
from telethon.tl.types import Message


class KeywordFilter:
    """Filter messages based on keyword matching."""
    
    def __init__(self, keywords: List[str]):
        """
        Initialize the keyword filter.
        
        Args:
            keywords: List of keywords to match (case-insensitive)
        """
        self.keywords = [kw.lower() for kw in keywords]
    
    def matches(self, message: Message) -> bool:
        """
        Check if message contains any of the keywords.
        
        Args:
            message: Telegram message object
            
        Returns:
            True if any keyword matches, False otherwise
        """
        if not message.text:
            return False
        
        text_lower = message.text.lower()
        
        for keyword in self.keywords:
            if keyword in text_lower:
                return True
        
        return False
    
    def get_matched_keywords(self, message: Message) -> List[str]:
        """
        Get list of keywords that matched in the message.
        
        Args:
            message: Telegram message object
            
        Returns:
            List of matched keywords
        """
        if not message.text:
            return []
        
        text_lower = message.text.lower()
        matched = []
        
        for keyword in self.keywords:
            if keyword in text_lower:
                matched.append(keyword)
        
        return matched
    
    def update_keywords(self, keywords: List[str]) -> None:
        """
        Update the keywords list.
        
        Args:
            keywords: New list of keywords
        """
        self.keywords = [kw.lower() for kw in keywords]


