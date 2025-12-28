# Telegram Marketplace Monitor Userbot

A production-ready Python userbot that monitors Telegram marketplace chats and forwards matching messages to you.

## ✨ Features

- 🔍 **Keyword Filtering** - Case-insensitive keyword matching
- 📨 **Targeted Notifications** - Each user receives notifications for their own search requests
- 🔒 **Duplicate Protection** - Never processes the same message twice (SQLite storage)
- 🛡️ **Rate-Limit Safety** - Handles FloodWaitError gracefully
- ⚡ **Real-time Only** - Monitors ONLY new messages (no history scanning)
- 📊 **Logging** - Comprehensive logging to file and console
- 🗄️ **PostgreSQL Database** - Store search requests, keywords, and groups per user
- 🤖 **Bot Commands** - Manage searches via Telegram bot interface (`/search`, `/list`)
- 🔄 **Dynamic Monitoring** - Automatically updates monitored groups and keywords from database
- 👥 **Multi-User Support** - Multiple users can create independent search requests

## 🚀 Quick Start

You can run this project either with **Docker** (recommended) or with **Python** directly.

### Option A: Docker (Recommended) 🐳

See [DOCKER.md](DOCKER.md) for detailed Docker setup instructions.

**Quick Docker Start (Local Development):**
```bash
# 1. Configure environment
cp env.example .env
nano .env  # Add your credentials (including DB_PASSWORD)

# 2. Start the bot (PostgreSQL + Userbot)
docker-compose up -d

# 3. View logs
docker-compose logs -f

# 4. Create your first search request via Telegram
#    Send /start to your bot, then use /search

# 5. Test database connection (optional)
docker-compose exec telegram-userbot python db_utils.py test
```

**For Production/CI-CD with GitHub Secrets:**
- See [SECRETS_SETUP.md](SECRETS_SETUP.md) for GitHub Secrets configuration
- See [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md) for automated deployment

### Option B: Python Setup

#### 1. Prerequisites

- Python 3.8 or higher
- Telegram account (NOT a bot account)
- Telegram API credentials (API_ID and API_HASH)

#### 2. Get Telegram API Credentials

1. Go to https://my.telegram.org/apps
2. Log in with your phone number
3. Create a new application
4. Note down your `api_id` and `api_hash`

#### 3. Installation

```bash
# Clone or download this repository
cd find-brilliant

# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL (local installation or Docker)
# For Docker:
docker run -d \
  --name postgres \
  -e POSTGRES_DB=find_brilliant \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=your_password \
  -p 5432:5432 \
  -v $(pwd)/init_db.sql:/docker-entrypoint-initdb.d/init_db.sql \
  postgres:16-alpine
```

#### 4. Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

**Required settings in `.env`:**

```bash
API_ID=12345678                    # Your Telegram API ID
API_HASH=your_api_hash_here        # Your Telegram API hash
TG_BOT_KEY=your_bot_token          # Your Telegram bot token (from @BotFather)

# Database configuration
DB_HOST=localhost                  # postgres (for Docker), localhost (for external tools)
DB_PORT=5433                       # External port (5433, localhost only)
DB_NAME=find_brilliant             # Database name
DB_USER=postgres                   # Database user
DB_PASSWORD=your_secure_password   # Database password (REQUIRED)
```

**Note:** `TARGET_USER_ID`, `KEYWORDS`, and `CHAT_IDS` are no longer needed in configuration. These are now managed via the bot interface (`/search` command).

#### 5. Run the Userbot

```bash
python main.py
```

**First run:**
- You'll be prompted to enter your phone number
- You'll receive a code via Telegram
- Enter the code and your 2FA password (if enabled)
- Session will be saved for future runs

#### 6. Use the Bot Interface

Once the bot is running, you can manage search requests via Telegram:

```
1. Open Telegram and find your bot (the one with TG_BOT_KEY token)
2. Send /start to begin
3. Use /search to create a new search request
   - Enter keywords (comma-separated)
   - Enter group usernames (with @ prefix)
   - Bot will verify groups and activate monitoring
4. Use /list to view your active searches
```

**Bot Commands:**
- `/start` - Welcome message and help
- `/search` - Create a new search request (interactive)
- `/list` - View all your active searches
- `/help` - Show available commands

**How to add groups to monitor:**

When using `/search`, provide group usernames with @ prefix:
- For public channels: `@marketplace_channel`, `@deals_group`
- Make sure you (the userbot account) are a member of these groups
- The bot will verify access and fetch group information automatically

## 🤖 Bot Commands

The bot provides an interactive interface for managing search requests:

### `/search` - Create Search Request

Interactive conversation to create a new search:

```
1. Send /search to the bot
2. Enter keywords (comma-separated): "iphone, macbook, laptop"
3. Enter group usernames (with @): "@marketplace, @deals_channel"
4. Bot fetches group info and saves to database
5. Search is now active!
```

**Example conversation:**
```
You: /search
Bot: Let's set up a new search! Enter keywords...

You: iphone, iphone 15, macbook
Bot: ✅ Keywords saved. Now enter group usernames...

You: @NSbaraholka, @serbiasell
Bot: ⏳ Fetching group information...
     ✅ Search Request Created!
     Keywords: iphone, iphone 15, macbook
     Groups: NSbaraholka, serbiasell
```

### `/list` - View Searches

Display all your active search requests:

```
You: /list
Bot: 📋 Your Active Searches (2):
     
     🆔 ID: 1
     📝 Title: Search: iphone, iphone 15, macbook
     🔑 Keywords (3): iphone, iphone 15, macbook
     📢 Groups (2): @NSbaraholka, @serbiasell
```

### Other Commands

- `/start` - Welcome message and introduction
- `/help` - Show available commands and usage
- `/cancel` - Cancel current operation (during /search)

## 📁 Project Structure

```
project/
├── main.py                    # Entry point and event orchestration
├── config.py                  # Configuration management
├── monitoring_manager.py      # Dynamic monitoring system (groups/keywords from DB)
├── filters.py                 # Keyword filtering logic (legacy)
├── notifier.py                # Message notification logic
├── bot_handler.py             # Bot command handlers (/search, /list)
├── storage.py                 # Duplicate detection storage
├── database.py                # PostgreSQL database module
├── db_utils.py                # Database utilities and management
├── init_db.sql                # Database initialization script
├── requirements.txt           # Python dependencies
│
├── env.example                # Example configuration
├── .env                       # Your actual configuration (git-ignored)
│
├── Dockerfile                 # Docker image definition
├── docker-compose.yml         # Docker Compose (works for local & CI/CD)
├── .dockerignore              # Files to exclude from Docker
│
├── .github/workflows/         # GitHub Actions workflows
│   └── deploy.yml             # Deployment workflow
│
├── README.md                  # This file
│
├── data/                      # Data directory (auto-created)
│   ├── userbot_session.session    # Telegram session
│   ├── processed_messages.db      # SQLite database (legacy)
│   └── userbot.log                # Log file
└── postgres_data/             # PostgreSQL data volume (Docker)
```

## 🔧 Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_ID` | ✅ | - | Telegram API ID |
| `API_HASH` | ✅ | - | Telegram API hash |
| `PHONE_NUMBER` | ✅ | - | Telegram phone number |
| `TG_BOT_KEY` | ✅ | - | Telegram bot token (from @BotFather) |
| `SESSION_NAME` | ❌ | data/userbot_session | Session file name |
| `POLL_INTERVAL` | ❌ | 30 | Polling interval for large groups (seconds) |
| `DB_HOST` | ✅ | postgres | PostgreSQL host |
| `DB_PORT` | ❌ | 5432 | PostgreSQL port |
| `DB_NAME` | ❌ | find_brilliant | Database name |
| `DB_USER` | ❌ | postgres | Database user |
| `DB_PASSWORD` | ✅ | - | Database password |

### Deprecated Variables (Now from Database)

These are no longer required in configuration and are managed via the bot interface:

- `TARGET_USER_ID` - Each user receives their own notifications
- `KEYWORDS` - Configured per search request via `/search`
- `CHAT_IDS` - Groups are added per search request via `/search`

## 🔒 Security Best Practices

1. **Never commit `.env` or session files**
   - Already included in `.gitignore`
   - Session files contain authentication data

2. **Keep your API credentials secret**
   - Don't share `API_ID` or `API_HASH`
   - Don't share session files

3. **Use strong 2FA**
   - Enable two-factor authentication on your Telegram account

4. **Monitor for unusual activity**
   - Check `userbot.log` regularly
   - Watch for FloodWaitError warnings

## 📊 Usage Examples

### Example 1: Monitor marketplace for electronics

```
1. Start the bot
2. Send /search to your Telegram bot
3. Enter keywords: laptop,macbook,iphone,ipad,airpods
4. Enter groups: @electronics_marketplace, @tech_deals_channel
5. Bot confirms setup and starts monitoring
6. You'll receive notifications when matches are found
```

### Example 2: Multiple users with different interests

**User A:**
- Keywords: bicycle, bike, mtb, road bike
- Groups: @bikes_marketplace, @cycling_deals

**User B:**
- Keywords: iphone, samsung, smartphone
- Groups: @phones_marketplace, @tech_deals

Both users receive only notifications for their own keywords!

## 🗄️ Database Management

### Database Schema

The PostgreSQL database consists of 5 tables:

1. **users** - Stores Telegram users
   - `id` (primary key), `telegram_id`, `username`, `first_name`, `last_name`, `created_at`

2. **telegram_groups** - Stores unique Telegram groups (shared)
   - `telegram_group_id` (primary key), `username`, `title`, `created_at`, `updated_at`

3. **search_requests** - Main search request entity
   - `id` (primary key), `user_id`, `title`, `is_active`, `created_at`

4. **search_request_keywords** - Keywords for each request
   - `id` (primary key), `search_request_id`, `keyword`

5. **search_request_groups** - Links requests to groups (many-to-many)
   - `id` (primary key), `search_request_id`, `telegram_group_id` (FK), `created_at`

### Database Utilities

The `db_utils.py` script provides database management commands:

```bash
# Test database connection
python db_utils.py test

# Create sample data for testing
python db_utils.py sample

# List all active search requests
python db_utils.py list

# Display all unique Telegram groups
python db_utils.py groups

# Show database initialization info
python db_utils.py init
```

### Using the Database Module

You can manage searches programmatically:

```python
from database import get_database_from_env

# Connect to database
db = get_database_from_env()

# Create a user
user_id = db.create_user(
    telegram_id=123456789,
    username="john_doe",
    first_name="John",
    last_name="Doe"
)

# Create a search request
request_id = db.create_search_request(
    user_id=user_id,
    title="iPhone Search",
    is_active=True
)

# Add keywords
db.add_keywords(request_id, ["iphone", "iphone 15"])

# Add groups
db.add_groups(request_id, [
    {"telegram_group_id": -1001234567890, "username": "marketplace"}
])

# Get all active requests with details
requests = db.get_all_active_search_requests_with_details()
for req in requests:
    print(f"Request: {req['title']}")
    print(f"Keywords: {[k['keyword'] for k in req['keywords']]}")
    print(f"Groups: {[g['username'] for g in req['groups']]}")

# Close connection
db.close()
```

**Or use the bot interface:**

Simply send `/search` to your bot and follow the interactive prompts!

### Database Reset

To completely reset the database:

```bash
# Stop containers
docker-compose down

# Remove PostgreSQL volume
docker volume rm find-brilliant_postgres_data

# Start again (will run init_db.sql)
docker-compose up -d
```

## 🐛 Troubleshooting

### "Configuration validation failed"
- Check that all required variables are set in `.env`
- Required: `API_ID`, `API_HASH`, `PHONE_NUMBER`, `TG_BOT_KEY`, `DB_PASSWORD`

### "No groups to monitor"
- No active search requests in database yet
- Use `/search` command in your bot to create a search request
- Check database with: `python db_utils.py list`

### "FloodWaitError"
- Telegram is rate-limiting your account
- The bot will automatically wait and retry
- Reduce the frequency of actions if this persists

### Messages not being delivered
- Check that your userbot account is a member of the monitored groups
- Verify keywords are correct (case-insensitive)
- Check `userbot.log` for errors
- Make sure the search request is active: use `/list` to verify

### Session errors
- Delete the `.session` file and re-authenticate
- Make sure your API credentials are correct

### Database connection errors
- Ensure PostgreSQL container is running: `docker-compose ps`
- Check database credentials in `.env`
- Test connection: `python db_utils.py test`
- View PostgreSQL logs: `docker-compose logs postgres`

## 📝 Logging

Logs are written to both console and `userbot.log`:

```
2024-01-01 12:00:00 - __main__ - INFO - 🎯 MATCH FOUND!
2024-01-01 12:00:00 - __main__ - INFO - Chat ID: -1001234567890
2024-01-01 12:00:00 - __main__ - INFO - Matched keywords: laptop, macbook
2024-01-01 12:00:01 - notifier - INFO - ✅ Forwarded message 12345
```

## 🚀 Deployment Options

### Local Development
- Use `.env` file with `docker-compose.yml`
- See [DOCKER.md](DOCKER.md)

### Production Server
- Use GitHub Secrets with `docker-compose.yml`
- Configure secrets in GitHub repository settings

### CI/CD with GitHub Actions
- Automated testing, building, and deployment
- See [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md)

## ⚠️ Important Notes

1. **Only monitors NEW messages** - Does not scan chat history
2. **Forwards original messages** - Preserves media, author, etc.
3. **Duplicate protection** - Each message processed only once
4. **Your account must be a member** - Bot doesn't auto-join chats
5. **Respect Telegram's limits** - Avoid excessive actions
6. **Use GitHub Secrets for production** - Never commit .env files

## 🤝 Contributing

This is a production-ready template. Feel free to customize for your needs:

- Add more sophisticated filtering (regex, price extraction, etc.)
- Implement web dashboard for configuration
- Add database cleanup scheduler
- Integrate with external services (Discord, Slack, etc.)

## 📄 License

MIT License - Use freely for personal or commercial projects.

## ⚡ Support

For issues or questions:
1. Check `userbot.log` for detailed error messages
2. Review the Troubleshooting section
3. Consult Telethon documentation: https://docs.telethon.dev/

---

**Made with ❤️ for Telegram marketplace monitoring**

