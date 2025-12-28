"""
Telegram Bot command handler for managing search requests.
Handles user interactions for creating and managing search configurations.
"""
import logging
from typing import Optional
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes
)
from telethon import TelegramClient
from telethon.errors import UsernameInvalidError, ChannelPrivateError

from database import get_database_from_env

logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_KEYWORDS = 1
WAITING_FOR_GROUPS = 2


class BotCommandHandler:
    """Handles bot commands for search request management."""
    
    def __init__(self, bot_token: str, telethon_client: TelegramClient):
        """
        Initialize the bot command handler.
        
        Args:
            bot_token: Telegram bot token
            telethon_client: Telethon client for fetching group info
        """
        self.bot_token = bot_token
        self.telethon_client = telethon_client
        self.db = get_database_from_env()
        self.application = None
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        
        await update.message.reply_text(
            f"👋 Hello, {user.first_name}!\n\n"
            "I can help you monitor Telegram groups for specific keywords.\n\n"
            "Available commands:\n"
            "/search - Create a new search request\n"
            "/list - View your active searches\n"
            "/help - Show this help message"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        await update.message.reply_text(
            "📚 <b>Available Commands:</b>\n\n"
            "/search - Create a new search request\n"
            "   Set up keywords and groups to monitor\n\n"
            "/list - View your active search requests\n"
            "   See all your configured searches\n\n"
            "/help - Show this help message\n\n"
            "<b>How it works:</b>\n"
            "1. Use /search to create a search request\n"
            "2. Enter keywords (comma-separated)\n"
            "3. Enter group usernames (with @)\n"
            "4. The bot will monitor those groups for your keywords\n"
            "5. You'll receive notifications when matches are found",
            parse_mode='HTML'
        )
    
    async def search_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start the /search command conversation."""
        user = update.effective_user
        
        # Store user info in context for later use
        context.user_data['telegram_id'] = user.id
        context.user_data['username'] = user.username
        context.user_data['first_name'] = user.first_name
        context.user_data['last_name'] = user.last_name
        
        logger.info(f"📝 User {user.id} (@{user.username}) started /search command")
        
        await update.message.reply_text(
            "🔍 <b>Create New Search Request</b>\n\n"
            "Let's set up a new search!\n\n"
            "First, enter the <b>keywords</b> you want to search for.\n"
            "Use commas to separate multiple keywords.\n\n"
            "<b>Example:</b> iphone, iphone 15, macbook\n\n"
            "Send /cancel to abort.",
            parse_mode='HTML'
        )
        
        return WAITING_FOR_KEYWORDS
    
    async def search_keywords(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle keywords input."""
        keywords_text = update.message.text.strip()
        
        if not keywords_text:
            await update.message.reply_text(
                "❌ Please enter at least one keyword.\n"
                "Example: iphone, laptop, macbook"
            )
            return WAITING_FOR_KEYWORDS
        
        # Parse keywords
        keywords = [kw.strip().lower() for kw in keywords_text.split(',') if kw.strip()]
        
        if not keywords:
            await update.message.reply_text(
                "❌ No valid keywords found. Please try again.\n"
                "Example: iphone, laptop, macbook"
            )
            return WAITING_FOR_KEYWORDS
        
        # Store keywords in context
        context.user_data['keywords'] = keywords
        
        logger.info(f"📝 User {update.effective_user.id} entered keywords: {keywords}")
        
        await update.message.reply_text(
            f"✅ Keywords saved: {', '.join(keywords)}\n\n"
            "Now, enter the <b>Telegram group usernames</b> to monitor.\n"
            "Use commas to separate multiple groups.\n"
            "Each group should start with @\n\n"
            "<b>Example:</b> @marketplace, @deals_channel, @trading_group\n\n"
            "Send /cancel to abort.",
            parse_mode='HTML'
        )
        
        return WAITING_FOR_GROUPS
    
    async def search_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle groups input and create search request."""
        groups_text = update.message.text.strip()
        
        if not groups_text:
            await update.message.reply_text(
                "❌ Please enter at least one group username.\n"
                "Example: @marketplace, @deals_channel"
            )
            return WAITING_FOR_GROUPS
        
        # Parse group usernames
        group_usernames = [g.strip() for g in groups_text.split(',') if g.strip()]
        
        if not group_usernames:
            await update.message.reply_text(
                "❌ No valid group usernames found. Please try again.\n"
                "Example: @marketplace, @deals_channel"
            )
            return WAITING_FOR_GROUPS
        
        # Validate that all start with @
        invalid_groups = [g for g in group_usernames if not g.startswith('@')]
        if invalid_groups:
            await update.message.reply_text(
                f"❌ All group usernames must start with @\n"
                f"Invalid: {', '.join(invalid_groups)}\n\n"
                "Example: @marketplace, @deals_channel"
            )
            return WAITING_FOR_GROUPS
        
        await update.message.reply_text(
            "⏳ Fetching group information from Telegram...\n"
            "This may take a few seconds."
        )
        
        # Fetch group info from Telegram using Telethon
        groups_info = []
        failed_groups = []
        
        for username in group_usernames:
            try:
                # Get entity info using Telethon
                entity = await self.telethon_client.get_entity(username)
                
                # Get the peer ID (this gives us the correct format with -100 prefix for supergroups)
                from telethon import utils
                peer_id = utils.get_peer_id(entity)
                
                # Extract group info
                group_info = {
                    'telegram_group_id': peer_id,  # Use peer_id instead of entity.id
                    'username': username.lstrip('@'),
                    'title': getattr(entity, 'title', None) or username
                }
                groups_info.append(group_info)
                logger.info(f"✅ Fetched info for {username}: ID={peer_id}, Title={group_info['title']}")
                
            except UsernameInvalidError:
                failed_groups.append(f"{username} (invalid username)")
                logger.warning(f"❌ Invalid username: {username}")
            except ChannelPrivateError:
                failed_groups.append(f"{username} (private or inaccessible)")
                logger.warning(f"❌ Private channel: {username}")
            except Exception as e:
                failed_groups.append(f"{username} (error: {str(e)})")
                logger.error(f"❌ Error fetching {username}: {e}")
        
        # Check if we have any valid groups
        if not groups_info:
            await update.message.reply_text(
                "❌ Could not fetch information for any groups.\n\n"
                f"Failed groups:\n{chr(10).join(failed_groups)}\n\n"
                "Please check the usernames and try again.\n"
                "Make sure you're a member of the groups."
            )
            return WAITING_FOR_GROUPS
        
        # Show warning if some groups failed
        if failed_groups:
            await update.message.reply_text(
                f"⚠️ Some groups could not be added:\n{chr(10).join(failed_groups)}\n\n"
                "Continuing with valid groups..."
            )
        
        # Create user in database
        try:
            user_id = self.db.create_user(
                telegram_id=context.user_data['telegram_id'],
                username=context.user_data.get('username'),
                first_name=context.user_data.get('first_name'),
                last_name=context.user_data.get('last_name')
            )
            
            logger.info(f"✅ Created/updated user {user_id} in database")
            
            # Create search request
            keywords = context.user_data['keywords']
            search_request_id = self.db.create_search_request(
                user_id=user_id,
                title=f"Search: {', '.join(keywords[:3])}{'...' if len(keywords) > 3 else ''}",
                is_active=True
            )
            
            logger.info(f"✅ Created search request {search_request_id}")
            
            # Add keywords
            keyword_ids = self.db.add_keywords(search_request_id, keywords)
            logger.info(f"✅ Added {len(keyword_ids)} keywords")
            
            # Add groups
            group_ids = self.db.add_groups(search_request_id, groups_info)
            logger.info(f"✅ Added {len(group_ids)} groups")
            
            # Build success message
            success_msg = (
                "✅ <b>Search Request Created!</b>\n\n"
                f"🆔 <b>Request ID:</b> {search_request_id}\n\n"
                f"🔑 <b>Keywords ({len(keywords)}):</b>\n"
            )
            for kw in keywords:
                success_msg += f"  • {kw}\n"
            
            success_msg += f"\n📢 <b>Groups ({len(groups_info)}):</b>\n"
            for group in groups_info:
                success_msg += f"  • {group['title']} (@{group['username']})\n"
            
            success_msg += (
                "\n✨ Your search is now active!\n"
                "You'll receive notifications when matches are found.\n\n"
                "Use /list to see all your searches."
            )
            
            await update.message.reply_text(success_msg, parse_mode='HTML')
            
            # Clear user data
            context.user_data.clear()
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"❌ Error creating search request: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ An error occurred while creating your search request.\n"
                "Please try again later or contact support."
            )
            return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the conversation."""
        await update.message.reply_text(
            "❌ Search creation cancelled.\n"
            "Use /search to start again."
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    async def list_searches(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List all active search requests for the user."""
        user = update.effective_user
        
        try:
            # Get user from database
            db_user = self.db.get_user_by_telegram_id(user.id)
            
            if not db_user:
                await update.message.reply_text(
                    "📋 You don't have any search requests yet.\n"
                    "Use /search to create your first search!"
                )
                return
            
            # Get user's search requests
            searches = self.db.get_user_search_requests(db_user['id'], active_only=True)
            
            if not searches:
                await update.message.reply_text(
                    "📋 You don't have any active search requests.\n"
                    "Use /search to create a new search!"
                )
                return
            
            # Build message with all searches
            msg = f"📋 <b>Your Active Searches ({len(searches)}):</b>\n\n"
            
            for search in searches:
                # Get keywords and groups for this search
                keywords = self.db.get_keywords(search['id'])
                groups = self.db.get_groups(search['id'])
                
                msg += f"🆔 <b>ID:</b> {search['id']}\n"
                msg += f"📝 <b>Title:</b> {search['title']}\n"
                msg += f"🔑 <b>Keywords ({len(keywords)}):</b> "
                msg += ", ".join([kw['keyword'] for kw in keywords[:5]])
                if len(keywords) > 5:
                    msg += f" +{len(keywords) - 5} more"
                msg += "\n"
                
                msg += f"📢 <b>Groups ({len(groups)}):</b> "
                msg += ", ".join([f"@{g['username']}" for g in groups[:3]])
                if len(groups) > 3:
                    msg += f" +{len(groups) - 3} more"
                msg += "\n\n"
            
            msg += "Use /search to create a new search request."
            
            await update.message.reply_text(msg, parse_mode='HTML')
            
        except Exception as e:
            logger.error(f"❌ Error listing searches: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ An error occurred while fetching your searches.\n"
                "Please try again later."
            )
    
    def get_handlers(self):
        """Get all command handlers."""
        # Conversation handler for /search command
        search_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('search', self.search_start)],
            states={
                WAITING_FOR_KEYWORDS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.search_keywords)
                ],
                WAITING_FOR_GROUPS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.search_groups)
                ],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )
        
        return [
            CommandHandler('start', self.start_command),
            CommandHandler('help', self.help_command),
            CommandHandler('list', self.list_searches),
            search_conv_handler,
        ]
    
    async def start_bot(self):
        """Start the bot application."""
        logger.info("🤖 Starting bot command handler...")
        
        # Create application
        self.application = Application.builder().token(self.bot_token).build()
        
        # Add handlers
        for handler in self.get_handlers():
            self.application.add_handler(handler)
        
        # Start polling
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        logger.info("✅ Bot command handler started and listening for commands")
    
    async def stop_bot(self):
        """Stop the bot application."""
        if self.application:
            logger.info("🛑 Stopping bot command handler...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("✅ Bot command handler stopped")
        
        # Close database connection
        if self.db:
            self.db.close()

