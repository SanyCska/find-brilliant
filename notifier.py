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
    
    async def _get_message_link(self, message: Message) -> tuple[str, str]:
        """
        Get the chat name and clickable link to the message.
        
        Args:
            message: Telegram message
            
        Returns:
            Tuple of (chat_name, message_link)
        """
        try:
            # Get chat information
            chat = await message.get_chat()
            chat_name = getattr(chat, 'title', None) or getattr(chat, 'first_name', None) or f"Chat {message.chat_id}"
            
            # Try to construct a link to the message
            message_link = None
            
            # Check if the chat has a username (public group/channel)
            username = getattr(chat, 'username', None)
            if username:
                # Public group/channel
                message_link = f"https://t.me/{username}/{message.id}"
            else:
                # Private group - use the chat ID format
                # For private groups, we need to remove the -100 prefix from chat_id
                chat_id_str = str(message.chat_id)
                if chat_id_str.startswith('-100'):
                    chat_id_numeric = chat_id_str[4:]  # Remove -100 prefix
                    message_link = f"https://t.me/c/{chat_id_numeric}/{message.id}"
                else:
                    # Fallback for other formats
                    message_link = f"Chat ID: {message.chat_id}, Message ID: {message.id}"
            
            return chat_name, message_link
            
        except Exception as e:
            logger.error(f"❌ Error getting message link: {e}")
            return f"Chat {message.chat_id}", f"Message ID: {message.id}"
    
    async def forward_message(self, message: Message) -> bool:
        """
        Forward a message to the target user.
        If the message is part of a media group (album), forwards all photos/videos in the group.
        Also sends a message with the source chat name and link.
        
        Args:
            message: Telegram message to forward
            
        Returns:
            True if forwarding succeeded, False otherwise
        """
        try:
            # Ensure the target entity is resolved and cached
            # This fixes the "Could not find the input entity" error
            target_entity = await self.client.get_entity(self.target_user_id)
            
            # Get chat name and message link
            chat_name, message_link = await self._get_message_link(message)
            
            # Send source information first
            source_text = f"📍 **Source:** {chat_name}\n🔗 **Link:** {message_link}"
            await self.client.send_message(
                entity=target_entity,
                message=source_text
            )
            
            # Check if this message is part of a grouped media (album)
            message_ids = [message.id]
            if message.grouped_id:
                logger.info(f"📸 Message is part of media group (grouped_id: {message.grouped_id})")
                # Get all messages in the same group
                # Fetch messages around this one to find all in the group
                messages = await self.client.get_messages(
                    message.peer_id,
                    limit=10,
                    min_id=message.id - 10,
                    max_id=message.id + 10
                )
                
                # Filter messages with the same grouped_id
                grouped_messages = [
                    msg for msg in messages 
                    if msg.grouped_id == message.grouped_id
                ]
                
                if grouped_messages:
                    message_ids = [msg.id for msg in sorted(grouped_messages, key=lambda m: m.id)]
                    logger.info(f"📸 Found {len(message_ids)} messages in media group: {message_ids}")
            
            # Forward the message(s) preserving all original data
            await self.client.forward_messages(
                entity=target_entity,
                messages=message_ids,
                from_peer=message.peer_id
            )
            
            if len(message_ids) > 1:
                logger.info(
                    f"✅ Forwarded {len(message_ids)} messages (media group) from chat {message.chat_id} to user {self.target_user_id}"
                )
            else:
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
                
                # Get chat name and message link
                chat_name, message_link = await self._get_message_link(message)
                
                # Send source information first
                source_text = f"📍 **Source:** {chat_name}\n🔗 **Link:** {message_link}"
                await self.client.send_message(
                    entity=target_entity,
                    message=source_text
                )
                
                # Re-determine message_ids in case of grouped media
                message_ids = [message.id]
                if message.grouped_id:
                    messages = await self.client.get_messages(
                        message.peer_id,
                        limit=10,
                        min_id=message.id - 10,
                        max_id=message.id + 10
                    )
                    grouped_messages = [
                        msg for msg in messages 
                        if msg.grouped_id == message.grouped_id
                    ]
                    if grouped_messages:
                        message_ids = [msg.id for msg in sorted(grouped_messages, key=lambda m: m.id)]
                
                await self.client.forward_messages(
                    entity=target_entity,
                    messages=message_ids,
                    from_peer=message.peer_id
                )
                logger.info(f"✅ Forwarded message(s) after FloodWait")
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


