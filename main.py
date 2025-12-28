"""
Telegram Marketplace Monitor Userbot
Monitors Telegram chats for keyword matches and forwards messages to a target user.
"""
import logging
import asyncio
import random
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.types import Message

from config import Config
from storage import MessageStorage
from filters import KeywordFilter
from notifier import BotNotifier

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
        self.keyword_filter = KeywordFilter(Config.KEYWORDS)
        self.notifier = BotNotifier(Config.TG_BOT_KEY, Config.TARGET_USER_ID)
        
        # Track ongoing auto-reply tasks to prevent duplicates
        self._reply_tasks = set()
    
    async def start(self):
        """Start the userbot."""
        logger.info("🚀 Starting Telegram Marketplace Monitor...")
        
        # Connect and ensure we're authorized
        await self.client.start(phone=Config.PHONE_NUMBER)
        
        me = await self.client.get_me()
        logger.info(f"✅ Logged in as: {me.first_name} ({me.username or 'no username'})")
        logger.info(f"📊 Monitoring {len(Config.CHAT_IDS)} chat(s):")
        for chat_id in Config.CHAT_IDS:
            logger.info(f"   - {chat_id}")
        logger.info(f"🔍 Filtering for {len(Config.KEYWORDS)} keywords:")
        for keyword in Config.KEYWORDS:
            logger.info(f"   - '{keyword}'")
        
        # Show last message from each monitored chat to verify connectivity
        logger.info("")
        logger.info("=" * 80)
        logger.info("📋 Checking last message from each monitored chat...")
        logger.info("=" * 80)
        await self._check_last_messages()
        
        # Get numeric IDs for monitored chats
        monitored_chat_ids = set()
        for chat_id in Config.CHAT_IDS:
            try:
                entity = await self.client.get_entity(chat_id)
                # Get the actual numeric ID
                numeric_id = entity.id
                monitored_chat_ids.add(numeric_id)
                logger.info(f"   Resolved '{chat_id}' -> ID: {numeric_id}")
            except Exception as e:
                logger.error(f"   ❌ Failed to resolve '{chat_id}': {e}")
        
        if not monitored_chat_ids:
            logger.error("❌ No chat IDs could be resolved! Check your CHAT_IDS configuration.")
            return
        
        logger.info(f"   Monitoring numeric IDs: {monitored_chat_ids}")
        
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
        logger.info("⚠️  Press Ctrl+C to stop")
        logger.info("")
        logger.info("🟢 BOT IS ACTIVE - Waiting for messages...")
        logger.info("")
        
        # Start heartbeat task
        asyncio.create_task(self._heartbeat())
        
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
            logger.info(f"   Author: {sender_name} | Msg ID: {message.id}")
            logger.info(f"   Text: {message_preview}{'...' if message.text and len(message.text) > 80 else ''}")
            
            # Skip if already processed (duplicate protection)
            if self.storage.is_processed(message.chat_id, message.id):
                logger.debug(f"⏭️  Skipping already processed message {message.id}")
                return
            
            # Check if message matches keywords
            if not self.keyword_filter.matches(message):
                logger.info(f"   ⏩ No keyword match")
                # Mark as processed even if no match to avoid re-checking
                self.storage.mark_processed(message.chat_id, message.id)
                return
            
            # Get matched keywords for logging
            matched_keywords = self.keyword_filter.get_matched_keywords(message)
            
            logger.info("=" * 80)
            logger.info(f"🎯 MATCH FOUND!")
            logger.info(f"Chat: {chat_name}")
            logger.info(f"Chat ID: {message.chat_id}")
            logger.info(f"Message ID: {message.id}")
            logger.info(f"Matched keywords: {', '.join(matched_keywords)}")
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
            
            # Forward the message to target user
            success = await self.notifier.send_notification(message, matched_keywords, self.client)
            
            if success:
                logger.info("✅ Message forwarded successfully")
                
                # Auto-reply if enabled
                if Config.AUTO_REPLY_ENABLED:
                    await self.schedule_auto_reply(message)
            else:
                logger.error("❌ Failed to forward message")
            
            # Mark as processed
            self.storage.mark_processed(message.chat_id, message.id)
            
        except Exception as e:
            logger.error(f"❌ Error processing message {message.id}: {e}", exc_info=True)
    
    async def schedule_auto_reply(self, message: Message):
        """
        Schedule an auto-reply to a message with random delay.
        
        Args:
            message: Message to reply to
        """
        # Create unique identifier for this reply task
        task_id = (message.chat_id, message.id)
        
        if task_id in self._reply_tasks:
            logger.debug(f"⏭️  Auto-reply already scheduled for message {message.id}")
            return
        
        self._reply_tasks.add(task_id)
        
        # Calculate random delay
        delay = random.randint(
            Config.AUTO_REPLY_MIN_DELAY,
            Config.AUTO_REPLY_MAX_DELAY
        )
        
        logger.info(f"⏰ Scheduling auto-reply in {delay} seconds")
        
        # Schedule the reply
        asyncio.create_task(self._send_auto_reply(message, delay, task_id))
    
    async def _send_auto_reply(self, message: Message, delay: int, task_id: tuple):
        """
        Send an auto-reply after a delay.
        
        Args:
            message: Message to reply to
            delay: Delay in seconds
            task_id: Unique identifier for this task
        """
        try:
            # Wait for the random delay
            await asyncio.sleep(delay)
            
            # Send the reply
            await self.client.send_message(
                entity=message.peer_id,
                message=Config.AUTO_REPLY_TEXT,
                reply_to=message.id
            )
            
            logger.info(f"💬 Auto-reply sent to message {message.id}")
            
        except FloodWaitError as e:
            logger.warning(f"⚠️ FloodWaitError on auto-reply: Need to wait {e.seconds} seconds")
            # Don't retry auto-reply on FloodWait
            
        except Exception as e:
            logger.error(f"❌ Error sending auto-reply: {e}")
            
        finally:
            # Remove from active tasks
            self._reply_tasks.discard(task_id)
    
    async def _check_last_messages(self):
        """Check and display the last message from each monitored chat."""
        for chat_id in Config.CHAT_IDS:
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
    
    async def _poll_large_groups(self, monitored_chat_ids: set):
        """
        Poll large groups for new messages since Telegram doesn't push updates for them.
        This is necessary for supergroups with many members (>5000).
        """
        # Wait a bit before starting to poll
        await asyncio.sleep(30)
        
        # Track last message IDs for each chat
        last_message_ids = {}
        
        logger.info("🔄 Starting polling mode for large groups...")
        logger.info(f"   Checking for new messages every {Config.POLL_INTERVAL} seconds")
        if len(monitored_chat_ids) > 1:
            logger.info(f"   Using random delays (1-5s) between groups")
        
        while True:
            try:
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
    
    async def _heartbeat(self):
        """
        Periodic heartbeat to show the bot is active.
        Logs a status message every 5 minutes.
        """
        await asyncio.sleep(60)  # Wait 1 minute before first heartbeat
        
        while True:
            try:
                stats = self.storage.get_stats()
                logger.info(f"💓 Heartbeat: Bot is active | Processed: {stats.get('total_processed', 0)} messages")
                await asyncio.sleep(300)  # Log every 5 minutes
            except Exception as e:
                logger.error(f"❌ Error in heartbeat: {e}")
                await asyncio.sleep(300)
    
    async def stop(self):
        """Stop the userbot gracefully."""
        logger.info("🛑 Stopping userbot...")
        
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

