"""
Helper script to get chat IDs from your Telegram account.
Run this once to discover the numeric IDs of your chats.
"""
import asyncio
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat
from config import Config


async def main():
    """List all chats/channels the user is a member of."""
    print("🔍 Fetching your chats...\n")
    
    # Create client
    client = TelegramClient(
        Config.SESSION_NAME,
        Config.API_ID,
        Config.API_HASH
    )
    
    await client.start()
    
    print("=" * 80)
    print("Your Chats and Channels:")
    print("=" * 80)
    
    # Get all dialogs (chats)
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        
        # Only show groups and channels
        if isinstance(entity, (Channel, Chat)):
            chat_type = "Channel" if entity.broadcast else "Group"
            username = f"@{entity.username}" if entity.username else "(private)"
            
            print(f"\n📁 {entity.title}")
            print(f"   Type: {chat_type}")
            print(f"   ID: {entity.id}")
            print(f"   Username: {username}")
            
            # Show the proper format for config.py
            if entity.username:
                print(f"   ✅ Add to config.py: '@{entity.username}'")
            else:
                print(f"   ✅ Add to config.py: {entity.id}")
    
    print("\n" + "=" * 80)
    print("\n💡 Copy the ID or username to config.py CHAT_IDS list")
    
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())


