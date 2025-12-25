"""
Message notification and forwarding logic.
Handles forwarding messages to the target user.
"""
import logging
from telethon import TelegramClient
from telethon.tl.types import Message
from telethon.errors import FloodWaitError, UserIsBlockedError, ChatWriteForbiddenError
import asyncio

logger = logging.getLogger(__name__)


class MessageNotifier:
    """Handles forwarding messages to the target user."""
    
    def __init__(self, client: TelegramClient, target_user_id: int):
        """
        Initialize the notifier.
        
        Args:
            client: Telethon client instance
            target_user_id: Telegram user ID to forward messages to
        """
        self.client = client
        self.target_user_id = target_user_id
    
    async def forward_message(self, message: Message) -> bool:
        """
        Forward a message to the target user.
        
        Args:
            message: Telegram message to forward
            
        Returns:
            True if forwarding succeeded, False otherwise
        """
        try:
            # Ensure the target entity is resolved and cached
            # This fixes the "Could not find the input entity" error
            target_entity = await self.client.get_entity(self.target_user_id)
            
            # Forward the message preserving all original data
            await self.client.forward_messages(
                entity=target_entity,
                messages=message.id,
                from_peer=message.peer_id
            )
            
            logger.info(
                f"✅ Forwarded message {message.id} from chat {message.chat_id} to user {self.target_user_id}"
            )
            return True
            
        except FloodWaitError as e:
            logger.warning(f"⚠️ FloodWaitError: Need to wait {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            # Retry once after waiting
            try:
                target_entity = await self.client.get_entity(self.target_user_id)
                await self.client.forward_messages(
                    entity=target_entity,
                    messages=message.id,
                    from_peer=message.peer_id
                )
                logger.info(f"✅ Forwarded message {message.id} after FloodWait")
                return True
            except Exception as retry_error:
                logger.error(f"❌ Failed to forward after FloodWait: {retry_error}")
                return False
        
        except UserIsBlockedError:
            logger.error(f"❌ Target user {self.target_user_id} has blocked the bot")
            return False
        
        except ChatWriteForbiddenError:
            logger.error(f"❌ Cannot send messages to user {self.target_user_id}")
            return False
        
        except Exception as e:
            logger.error(f"❌ Error forwarding message: {e}")
            return False
    
    async def send_notification(self, message: Message, matched_keywords: list) -> bool:
        """
        Send a notification about a matched message.
        This is a wrapper that calls forward_message.
        
        Args:
            message: Telegram message that matched
            matched_keywords: List of keywords that matched
            
        Returns:
            True if notification succeeded, False otherwise
        """
        logger.info(f"📨 Notification triggered for message {message.id}")
        logger.info(f"🔑 Matched keywords: {', '.join(matched_keywords)}")
        
        return await self.forward_message(message)


