"""
Message notification and forwarding logic.
Handles forwarding messages to the target user.
"""
import logging
from telethon import TelegramClient
from telethon.tl.types import Message
from telethon.errors import FloodWaitError, UserIsBlockedError, ChatWriteForbiddenError
import asyncio
from telegram import Bot
from telegram.error import TelegramError

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
        Send notification about a message with source chat name and clickable link.
        Does not forward the actual message, only sends the link to it.
        
        Args:
            message: Telegram message to notify about
            
        Returns:
            True if notification succeeded, False otherwise
        """
        try:
            # Ensure the target entity is resolved and cached
            # This fixes the "Could not find the input entity" error
            target_entity = await self.client.get_entity(self.target_user_id)
            
            # Get chat name and message link
            chat_name, message_link = await self._get_message_link(message)
            
            # Send only the source information with link
            source_text = f"📍 **Source:** {chat_name}\n🔗 **Link:** {message_link}"
            await self.client.send_message(
                entity=target_entity,
                message=source_text
            )
            
            logger.info(
                f"✅ Sent notification with link for message {message.id} from chat {message.chat_id} to user {self.target_user_id}"
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
                
                # Send only the source information with link
                source_text = f"📍 **Source:** {chat_name}\n🔗 **Link:** {message_link}"
                await self.client.send_message(
                    entity=target_entity,
                    message=source_text
                )
                
                logger.info(f"✅ Sent notification after FloodWait")
                return True
            except Exception as retry_error:
                logger.error(f"❌ Failed to send notification after FloodWait: {retry_error}")
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


class BotNotifier:
    """Handles sending notifications via Telegram Bot API."""
    
    def __init__(self, bot_token: str, target_user_id: int):
        """
        Initialize the bot notifier.
        
        Args:
            bot_token: Telegram bot token
            target_user_id: Telegram user ID to send messages to
        """
        self.bot = Bot(token=bot_token)
        self.target_user_id = target_user_id
    
    async def _get_message_info(self, message: Message, client: TelegramClient) -> dict:
        """
        Extract message information for notification.
        
        Args:
            message: Telegram message
            client: Telethon client to get additional info
            
        Returns:
            Dictionary with message details
        """
        try:
            # Get chat information
            chat = await message.get_chat()
            chat_name = getattr(chat, 'title', None) or getattr(chat, 'first_name', None) or f"Chat {message.chat_id}"
            
            # Get sender information
            sender_name = "Unknown"
            if message.sender:
                sender_name = getattr(message.sender, 'first_name', None) or getattr(message.sender, 'username', None) or str(message.sender_id)
            
            # Try to construct a link to the message
            message_link = None
            username = getattr(chat, 'username', None)
            if username:
                # Public group/channel
                message_link = f"https://t.me/{username}/{message.id}"
            else:
                # Private group - use the chat ID format
                chat_id_str = str(message.chat_id)
                if chat_id_str.startswith('-100'):
                    chat_id_numeric = chat_id_str[4:]  # Remove -100 prefix
                    message_link = f"https://t.me/c/{chat_id_numeric}/{message.id}"
                else:
                    message_link = f"Chat ID: {message.chat_id}, Message ID: {message.id}"
            
            # Get message text preview
            text_preview = message.text[:200] if message.text else "(no text)"
            
            # Check for media
            media_info = []
            if message.photo:
                media_info.append("📷 Photo")
            if message.video:
                media_info.append("🎥 Video")
            if message.document:
                media_info.append("📎 File")
            
            return {
                'chat_name': chat_name,
                'sender_name': sender_name,
                'message_link': message_link,
                'text_preview': text_preview,
                'media_info': media_info,
                'message_id': message.id,
                'chat_id': message.chat_id
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting message info: {e}")
            return {
                'chat_name': f"Chat {message.chat_id}",
                'sender_name': "Unknown",
                'message_link': f"Message ID: {message.id}",
                'text_preview': message.text[:200] if message.text else "(no text)",
                'media_info': [],
                'message_id': message.id,
                'chat_id': message.chat_id
            }
    
    async def send_notification(self, message: Message, matched_keywords: list, client: TelegramClient) -> bool:
        """
        Send a notification about a matched message via bot.
        
        Args:
            message: Telegram message that matched
            matched_keywords: List of keywords that matched
            client: Telethon client to get message details
            
        Returns:
            True if notification succeeded, False otherwise
        """
        try:
            logger.info(f"📨 Bot notification triggered for message {message.id}")
            logger.info(f"🔑 Matched keywords: {', '.join(matched_keywords)}")
            
            # Get message information
            msg_info = await self._get_message_info(message, client)
            
            # Escape HTML special characters in user-generated content
            def escape_html(text: str) -> str:
                """Escape HTML special characters."""
                return (text
                    .replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                    .replace("'", '&#39;'))
            
            # Build notification message using HTML parse mode
            notification_text = "🔔 <b>New Match Found!</b>\n\n"
            notification_text += f"📍 <b>Chat:</b> {escape_html(msg_info['chat_name'])}\n"
            notification_text += f"👤 <b>Sender:</b> {escape_html(msg_info['sender_name'])}\n"
            notification_text += f"🔑 <b>Keywords:</b> {escape_html(', '.join(matched_keywords))}\n\n"
            
            if msg_info['media_info']:
                notification_text += f"📎 <b>Media:</b> {escape_html(', '.join(msg_info['media_info']))}\n\n"
            
            notification_text += f"💬 <b>Message:</b>\n{escape_html(msg_info['text_preview'])}\n\n"
            notification_text += f"🔗 <b>Link:</b> {msg_info['message_link']}"
            
            # Send via bot using HTML parse mode
            await self.bot.send_message(
                chat_id=self.target_user_id,
                text=notification_text,
                parse_mode='HTML'
            )
            
            logger.info(f"✅ Bot notification sent successfully to user {self.target_user_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"❌ Telegram error sending bot notification: {e}")
            return False
        
        except Exception as e:
            logger.error(f"❌ Error sending bot notification: {e}")
            return False


