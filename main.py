"""
Telegram Marketplace Monitor Userbot
Monitors Telegram chats for keyword matches and forwards messages to a target user.
"""
import logging
import asyncio
import random
from typing import List, Set
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.types import Message

from config import Config
from storage import MessageStorage
from filters import KeywordFilter
from notifier import BotNotifier
from bot_handler import BotCommandHandler
from monitoring_manager import MonitoringManager
from database import get_database_from_env

# Configure logging
import os
os.makedirs('data', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/userbot.log'),
        logging.StreamHandler()
    ]
)

# Silence httpx INFO logs (HTTP requests)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class TelegramMarketplaceBot:
    """Main userbot class for monitoring marketplace chats."""
    
    def __init__(self):
        """Initialize the userbot with configuration."""
        # Validate configuration
        Config.validate()
        Config.display()
        
        # Initialize components
        self.client = TelegramClient(
            Config.SESSION_NAME,
            Config.API_ID,
            Config.API_HASH
        )
        
        self.storage = MessageStorage('data/processed_messages.db')
        
        # Initialize database and monitoring manager
        self.db = get_database_from_env()
        self.monitoring_manager = MonitoringManager(self.db)
        
        # Keep legacy filter and notifier for backward compatibility (optional)
        # These will be replaced by monitoring_manager functionality
        self.keyword_filter = KeywordFilter(Config.KEYWORDS if hasattr(Config, 'KEYWORDS') else [])
        self.notifier = BotNotifier(Config.TG_BOT_KEY, Config.TARGET_USER_ID if hasattr(Config, 'TARGET_USER_ID') else 0)
        
        # Bot command handler for managing search requests
        self.bot_handler = None
    
    async def start(self):
        """Start the userbot."""
        logger.info("🚀 Starting Telegram Marketplace Monitor...")
        
        # Connect and ensure we're authorized
        await self.client.start(phone=Config.PHONE_NUMBER)
        
        me = await self.client.get_me()
        logger.info(f"✅ Logged in as: {me.first_name} ({me.username or 'no username'})")
        
        # Load monitoring data from database
        logger.info("📊 Loading monitoring configuration from database...")
        self.monitoring_manager.load_monitoring_data()
        
        # Display monitoring stats
        stats = self.monitoring_manager.get_stats()
        logger.info(f"📊 Monitoring Configuration:")
        logger.info(f"   Active search requests: {stats['active_requests']}")
        logger.info(f"   Unique groups: {stats['monitored_groups']}")
        logger.info(f"   Total monitors: {stats['total_monitors']}")
        
        # Get monitored group IDs from monitoring manager
        monitored_chat_ids = self.monitoring_manager.get_monitored_groups()
        
        if not monitored_chat_ids:
            logger.warning("⚠️  No groups to monitor! Waiting for search requests to be created...")
            logger.info("   Send /search to the bot to create your first search request")
            # Initialize empty set for now
            monitored_chat_ids = set()
        else:
            # Show last message from each monitored chat to verify connectivity
            logger.info("")
            logger.info("=" * 80)
            logger.info("📋 Checking last message from each monitored chat...")
            logger.info("=" * 80)
            await self._check_last_messages_by_ids(monitored_chat_ids)
            logger.info(f"   Monitoring {len(monitored_chat_ids)} group(s): {monitored_chat_ids}")
        
        # Register event handler for ALL messages, then filter manually
        # This is more reliable than using chats= parameter
        @self.client.on(events.NewMessage())
        async def handle_new_message(event: events.NewMessage.Event):
            """Handle new messages - filter for monitored chats."""
            # Check if this message is from a monitored chat
            if event.chat_id in monitored_chat_ids:
                await self.process_message(event.message)
        
        logger.info("✅ Event handlers registered")
        logger.info("👀 Now monitoring for new messages...")
        
        # Start bot command handler
        try:
            self.bot_handler = BotCommandHandler(Config.TG_BOT_KEY, self.client)
            await self.bot_handler.start_bot()
            logger.info("✅ Bot command handler started")
            logger.info("   Send /start to the bot to begin!")
        except Exception as e:
            logger.error(f"❌ Failed to start bot command handler: {e}")
            logger.info("   Continuing without bot commands...")
        
        logger.info("⚠️  Press Ctrl+C to stop")
        logger.info("")
        logger.info("🟢 BOT IS ACTIVE - Waiting for messages...")
        logger.info("")
        
        # Start heartbeat task
        asyncio.create_task(self._heartbeat())
        
        # Start monitoring refresh task
        asyncio.create_task(self._refresh_monitoring_data())
        
        # Start polling task for large groups
        asyncio.create_task(self._poll_large_groups(monitored_chat_ids))
        
        # Keep the client running
        await self.client.run_until_disconnected()
    
    async def process_message(self, message: Message):
        """
        Process a new message from a monitored chat.
        
        Args:
            message: Telegram message object
        """
        try:
            # Get chat info for logging
            chat = await message.get_chat()
            chat_name = getattr(chat, 'title', None) or getattr(chat, 'username', None) or f"Chat {message.chat_id}"
            
            # Get message author if available
            sender_name = "Unknown"
            if message.sender:
                sender_name = getattr(message.sender, 'first_name', None) or getattr(message.sender, 'username', None) or str(message.sender_id)
            
            # Log every new message received with more detail
            message_preview = message.text[:80] if message.text else "(no text)"
            media_info = ""
            if message.photo:
                media_info += " [📷 photo]"
            if message.video:
                media_info += " [🎥 video]"
            if message.document:
                media_info += " [📎 file]"
            
            logger.info(f"📩 New message from '{chat_name}'{media_info}")
            logger.info(f"   Text: {message_preview}{'...' if message.text and len(message.text) > 80 else ''}")
            
            # Skip if already processed (duplicate protection)
            if self.storage.is_processed(message.chat_id, message.id):
                logger.debug(f"⏭️  Skipping already processed message {message.id}")
                return
            
            # Check if message matches any keywords for this group
            matches = self.monitoring_manager.check_message(message.chat_id, message.text)
            
            if not matches:
                # Mark as processed even if no match to avoid re-checking
                self.storage.mark_processed(message.chat_id, message.id)
                return
            
            # Process each matching search request
            logger.info("=" * 80)
            logger.info(f"🎯 MATCH FOUND! ({len(matches)} search request(s) matched)")
            logger.info(f"Chat: {chat_name}")
            logger.info(f"Chat ID: {message.chat_id}")
            logger.info(f"Message ID: {message.id}")
            logger.info("-" * 80)
            logger.info(f"📝 FULL MESSAGE TEXT:")
            logger.info("-" * 80)
            if message.text:
                # Log the full message text with proper formatting
                for line in message.text.split('\n'):
                    logger.info(f"  {line}")
            else:
                logger.info("  (no text - media only)")
            logger.info("-" * 80)
            if message.photo:
                logger.info(f"📷 Contains photo")
            if message.video:
                logger.info(f"🎥 Contains video")
            if message.document:
                logger.info(f"📎 Contains document")
            logger.info("=" * 80)
            
            # Send notification to each user whose request matched
            for user_telegram_id, matched_keywords, request_id in matches:
                logger.info(f"📤 Sending notification to user {user_telegram_id}")
                logger.info(f"   Request ID: {request_id}")
                logger.info(f"   Matched keywords: {', '.join(matched_keywords)}")
                
                # Send notification to this specific user
                success = await self._send_notification_to_user(
                    message,
                    matched_keywords,
                    user_telegram_id,
                    request_id
                )
                
                if success:
                    logger.info(f"✅ Notification sent to user {user_telegram_id}")
                else:
                    logger.error(f"❌ Failed to send notification to user {user_telegram_id}")
            
            # Mark as processed
            self.storage.mark_processed(message.chat_id, message.id)
            
        except Exception as e:
            logger.error(f"❌ Error processing message {message.id}: {e}", exc_info=True)
    
    async def _send_notification_to_user(
        self,
        message: Message,
        matched_keywords: List[str],
        user_telegram_id: int,
        request_id: int
    ) -> bool:
        """
        Send notification to a specific user about a matched message.
        
        Args:
            message: Telegram message that matched
            matched_keywords: List of keywords that matched
            user_telegram_id: Telegram ID of the user to notify
            request_id: ID of the search request that matched
            
        Returns:
            True if notification succeeded, False otherwise
        """
        try:
            # Create a bot instance for this notification
            from telegram import Bot
            bot = Bot(token=Config.TG_BOT_KEY)
            
            # Get message information
            chat = await message.get_chat()
            chat_name = getattr(chat, 'title', None) or getattr(chat, 'username', None) or f"Chat {message.chat_id}"
            
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
            text_preview = message.text[:300] if message.text else "(no text)"
            
            # Check for media
            media_info = []
            if message.photo:
                media_info.append("📷 Photo")
            if message.video:
                media_info.append("🎥 Video")
            if message.document:
                media_info.append("📎 File")
            
            # Escape HTML special characters
            def escape_html(text: str) -> str:
                return (text
                    .replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                    .replace("'", '&#39;'))
            
            # Build notification message
            notification_text = "🔔 <b>New Match Found!</b>\n\n"
            notification_text += f"📍 <b>Chat:</b> {escape_html(chat_name)}\n"
            notification_text += f"👤 <b>Sender:</b> {escape_html(sender_name)}\n"
            notification_text += f"🔑 <b>Keywords:</b> {escape_html(', '.join(matched_keywords))}\n"
            notification_text += f"🆔 <b>Request ID:</b> {request_id}\n\n"
            
            if media_info:
                notification_text += f"📎 <b>Media:</b> {escape_html(', '.join(media_info))}\n\n"
            
            notification_text += f"💬 <b>Message:</b>\n{escape_html(text_preview)}\n\n"
            notification_text += f"🔗 <b>Link:</b> {message_link}"
            
            # Send via bot
            await bot.send_message(
                chat_id=user_telegram_id,
                text=notification_text,
                parse_mode='HTML'
            )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending notification to user {user_telegram_id}: {e}", exc_info=True)
            return False
    
    async def _check_last_messages_by_ids(self, group_ids: Set[int]):
        """
        Check and display the last message from each monitored group by ID.
        
        Args:
            group_ids: Set of Telegram group IDs to check
        """
        for chat_id in group_ids:
            try:
                # Get the chat entity
                chat = await self.client.get_entity(chat_id)
                chat_name = getattr(chat, 'title', None) or getattr(chat, 'username', None) or str(chat_id)
                
                # Get the last message
                messages = await self.client.get_messages(chat, limit=1)
                
                if not messages:
                    logger.warning(f"⚠️  Chat '{chat_name}': No messages found or no access")
                    continue
                
                last_msg = messages[0]
                
                # Format the date
                msg_date = last_msg.date.strftime("%Y-%m-%d %H:%M:%S") if last_msg.date else "Unknown"
                
                # Get sender info
                sender_name = "Unknown"
                if last_msg.sender:
                    sender_name = getattr(last_msg.sender, 'first_name', None) or getattr(last_msg.sender, 'username', None) or str(last_msg.sender_id)
                
                # Get message preview
                text_preview = ""
                if last_msg.text:
                    text_preview = last_msg.text[:100].replace('\n', ' ')
                    if len(last_msg.text) > 100:
                        text_preview += "..."
                else:
                    text_preview = "(no text)"
                
                # Media info
                media_info = []
                if last_msg.photo:
                    media_info.append("📷 photo")
                if last_msg.video:
                    media_info.append("🎥 video")
                if last_msg.document:
                    media_info.append("📎 document")
                
                media_str = f" [{', '.join(media_info)}]" if media_info else ""
                
                logger.info("")
                logger.info(f"💬 Chat: '{chat_name}' (ID: {chat_id})")
                logger.info(f"   Last message ID: {last_msg.id}")
                logger.info(f"   Date: {msg_date}")
                logger.info(f"   From: {sender_name}")
                logger.info(f"   Text: {text_preview}{media_str}")
                
                # Check if it matches any keywords
                matches = self.monitoring_manager.check_message(chat_id, last_msg.text)
                if matches:
                    for user_id, keywords, req_id in matches:
                        logger.info(f"   🎯 MATCHES Request {req_id}: {', '.join(keywords)}")
                else:
                    logger.info(f"   ⏩ No keyword match")
                    
            except ValueError as e:
                logger.error(f"❌ Cannot access chat ID '{chat_id}': {e}")
            except Exception as e:
                logger.error(f"❌ Error checking chat ID '{chat_id}': {e}")
        
        logger.info("=" * 80)
        logger.info("")
    
    async def _check_last_messages(self):
        """Check and display the last message from each monitored chat (legacy method)."""
        for chat_id in Config.CHAT_IDS if hasattr(Config, 'CHAT_IDS') else []:
            try:
                # Get the chat entity
                chat = await self.client.get_entity(chat_id)
                chat_name = getattr(chat, 'title', None) or getattr(chat, 'username', None) or str(chat_id)
                
                # Get the last message
                messages = await self.client.get_messages(chat, limit=1)
                
                if not messages:
                    logger.warning(f"⚠️  Chat '{chat_name}': No messages found or no access")
                    continue
                
                last_msg = messages[0]
                
                # Format the date
                msg_date = last_msg.date.strftime("%Y-%m-%d %H:%M:%S") if last_msg.date else "Unknown"
                
                # Get sender info
                sender_name = "Unknown"
                if last_msg.sender:
                    sender_name = getattr(last_msg.sender, 'first_name', None) or getattr(last_msg.sender, 'username', None) or str(last_msg.sender_id)
                
                # Get message preview
                text_preview = ""
                if last_msg.text:
                    text_preview = last_msg.text[:100].replace('\n', ' ')
                    if len(last_msg.text) > 100:
                        text_preview += "..."
                else:
                    text_preview = "(no text)"
                
                # Media info
                media_info = []
                if last_msg.photo:
                    media_info.append("📷 photo")
                if last_msg.video:
                    media_info.append("🎥 video")
                if last_msg.document:
                    media_info.append("📎 document")
                
                media_str = f" [{', '.join(media_info)}]" if media_info else ""
                
                logger.info("")
                logger.info(f"💬 Chat: '{chat_name}'")
                logger.info(f"   Last message ID: {last_msg.id}")
                logger.info(f"   Date: {msg_date}")
                logger.info(f"   From: {sender_name}")
                logger.info(f"   Text: {text_preview}{media_str}")
                
                # Check if it matches keywords
                if last_msg.text and self.keyword_filter.matches(last_msg):
                    matched = self.keyword_filter.get_matched_keywords(last_msg)
                    logger.info(f"   🎯 MATCHES keywords: {', '.join(matched)}")
                else:
                    logger.info(f"   ⏩ No keyword match")
                    
            except ValueError as e:
                logger.error(f"❌ Cannot access chat '{chat_id}': {e}")
            except Exception as e:
                logger.error(f"❌ Error checking chat '{chat_id}': {e}")
        
        logger.info("=" * 80)
        logger.info("")
    
    async def _poll_large_groups(self, initial_chat_ids: set):
        """
        Poll large groups for new messages since Telegram doesn't push updates for them.
        This is necessary for supergroups with many members (>5000).
        Dynamically updates the list of monitored groups.
        
        Args:
            initial_chat_ids: Initial set of chat IDs (may be empty)
        """
        # Wait a bit before starting to poll
        await asyncio.sleep(30)
        
        # Track last message IDs for each chat
        last_message_ids = {}
        
        logger.info("🔄 Starting polling mode for large groups...")
        logger.info(f"   Checking for new messages every {Config.POLL_INTERVAL} seconds")
        logger.info(f"   Monitoring list will update dynamically from database")
        
        while True:
            try:
                # Get current list of monitored groups from monitoring manager
                monitored_chat_ids = self.monitoring_manager.get_monitored_groups()
                
                if not monitored_chat_ids:
                    # No groups to monitor yet, wait and try again
                    await asyncio.sleep(Config.POLL_INTERVAL)
                    continue
                
                for i, chat_id in enumerate(monitored_chat_ids):
                    try:
                        # Add random delay between groups (not for the first one in each cycle)
                        if i > 0:
                            delay = random.randint(1, 5)
                            logger.debug(f"   ⏳ Waiting {delay}s before checking next group...")
                            await asyncio.sleep(delay)
                        
                        # Get chat name for better logging
                        try:
                            chat = await self.client.get_entity(chat_id)
                            chat_name = getattr(chat, 'title', None) or getattr(chat, 'username', None) or str(chat_id)
                        except:
                            chat_name = str(chat_id)
                        
                        # Get recent messages (last 10)
                        messages = await self.client.get_messages(chat_id, limit=10)
                        
                        if not messages:
                            continue
                        
                        # Initialize last_message_id if first time
                        if chat_id not in last_message_ids:
                            last_message_ids[chat_id] = messages[0].id
                            logger.info(f"📌 Initialized polling for '{chat_name}' (ID: {chat_id})")
                            logger.info(f"   Last message ID: {messages[0].id}")
                            continue
                        
                        # Check for new messages
                        new_messages = []
                        for msg in messages:
                            if msg.id > last_message_ids[chat_id]:
                                new_messages.append(msg)
                        
                        # Process new messages (oldest first)
                        if new_messages:
                            logger.info(f"🔄 Found {len(new_messages)} new message(s) via polling in '{chat_name}'")
                        
                        new_messages.reverse()
                        for msg in new_messages:
                            await self.process_message(msg)
                        
                        # Update last seen message ID
                        if messages:
                            last_message_ids[chat_id] = messages[0].id
                            
                    except Exception as e:
                        logger.error(f"❌ Error polling chat {chat_id}: {e}")
                
                # Wait before next poll
                await asyncio.sleep(Config.POLL_INTERVAL)
                
            except Exception as e:
                logger.error(f"❌ Error in polling loop: {e}")
                await asyncio.sleep(Config.POLL_INTERVAL)
    
    async def _refresh_monitoring_data(self):
        """
        Periodically refresh monitoring data from database.
        Checks for new search requests, keywords, and groups.
        """
        # Wait 2 minutes before first refresh
        await asyncio.sleep(120)
        
        while True:
            try:
                logger.info("🔄 Refreshing monitoring data from database...")
                self.monitoring_manager.load_monitoring_data()
                
                stats = self.monitoring_manager.get_stats()
                logger.info(f"✅ Monitoring data refreshed:")
                logger.info(f"   Active requests: {stats['active_requests']}")
                logger.info(f"   Monitored groups: {stats['monitored_groups']}")
                logger.info(f"   Total monitors: {stats['total_monitors']}")
                
                # Wait 5 minutes before next refresh
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"❌ Error refreshing monitoring data: {e}")
                # Wait 5 minutes before retry
                await asyncio.sleep(300)
    
    async def _heartbeat(self):
        """
        Periodic heartbeat to show the bot is active.
        Logs a status message every 5 minutes.
        """
        await asyncio.sleep(60)  # Wait 1 minute before first heartbeat
        
        while True:
            try:
                stats = self.storage.get_stats()
                monitor_stats = self.monitoring_manager.get_stats()
                logger.info(
                    f"💓 Heartbeat: Bot is active | "
                    f"Processed: {stats.get('total_processed', 0)} messages | "
                    f"Active requests: {monitor_stats['active_requests']}"
                )
                await asyncio.sleep(300)  # Log every 5 minutes
            except Exception as e:
                logger.error(f"❌ Error in heartbeat: {e}")
                await asyncio.sleep(300)
    
    async def stop(self):
        """Stop the userbot gracefully."""
        logger.info("🛑 Stopping userbot...")
        
        # Stop bot command handler
        if self.bot_handler:
            try:
                await self.bot_handler.stop_bot()
            except Exception as e:
                logger.error(f"❌ Error stopping bot handler: {e}")
        
        # Show statistics
        stats = self.storage.get_stats()
        logger.info(f"📊 Statistics:")
        logger.info(f"   Total messages processed: {stats.get('total_processed', 0)}")
        if 'last_24h' in stats:
            logger.info(f"   Processed in last 24h: {stats['last_24h']}")
        
        await self.client.disconnect()
        logger.info("✅ Userbot stopped")


async def main():
    """Main entry point."""
    bot = TelegramMarketplaceBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Received interrupt signal")
        await bot.stop()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        await bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

