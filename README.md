# Telegram Marketplace Monitor Userbot

A production-ready Python userbot that monitors Telegram marketplace chats and forwards matching messages to you.

## ✨ Features

- 🔍 **Keyword Filtering** - Case-insensitive keyword matching
- 📨 **Message Forwarding** - Forwards original messages (preserves media, author, etc.)
- 🔒 **Duplicate Protection** - Never processes the same message twice (SQLite storage)
- 💬 **Auto-Reply** - Optional automated replies with random delays (5-15s)
- 🛡️ **Rate-Limit Safety** - Handles FloodWaitError gracefully
- ⚡ **Real-time Only** - Monitors ONLY new messages (no history scanning)
- 📊 **Logging** - Comprehensive logging to file and console

## 🚀 Quick Start

You can run this project either with **Docker** (recommended) or with **Python** directly.

### Option A: Docker (Recommended) 🐳

See [DOCKER.md](DOCKER.md) for detailed Docker setup instructions.

**Quick Docker Start (Local Development):**
```bash
# 1. Configure environment
cp .env.example .env
nano .env  # Add your credentials

# 2. Update config.py with your chat IDs

# 3. Start the bot
docker-compose up -d

# 4. View logs
docker-compose logs -f
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
TARGET_USER_ID=123456789           # Your Telegram user ID (get from @userinfobot)
KEYWORDS=laptop,macbook,iphone     # Comma-separated keywords
```

**Optional settings:**

```bash
AUTO_REPLY_ENABLED=true
AUTO_REPLY_TEXT=Hi! I'm interested in this. Is it still available?
AUTO_REPLY_MIN_DELAY=5
AUTO_REPLY_MAX_DELAY=15
```

#### 5. Configure Monitored Chats

Edit `config.py` and update the `CHAT_IDS` list:

```python
CHAT_IDS: List[str] = [
    "@marketplace_channel",     # Public channel username
    -1001234567890,            # Numeric chat ID
    # Add more chats here
]
```

**How to get chat IDs:**

**Method 1 - Use the helper script (RECOMMENDED):**
```bash
python get_chat_ids.py
```
This will list all your chats with their IDs!

**Method 2 - For public channels:**
- Use `@username` format (e.g., `"@serbska_baraholka"`)

**Method 3 - For private groups:**
- Open chat in Telegram Desktop → Right-click → Copy link
- You'll get: `https://t.me/c/1234567890/123`
- Add `-100` prefix to the number: `-1001234567890`
- Use this in `CHAT_IDS`

**Method 4 - Using @userinfobot:**
- Forward a message from the chat to [@userinfobot](https://t.me/userinfobot)
- It will reply with the chat ID

#### 6. Run the Userbot

```bash
python main.py
```

**First run:**
- You'll be prompted to enter your phone number
- You'll receive a code via Telegram
- Enter the code and your 2FA password (if enabled)
- Session will be saved for future runs

## 📁 Project Structure

```
project/
├── main.py                    # Entry point and event orchestration
├── config.py                  # Configuration management
├── filters.py                 # Keyword filtering logic
├── notifier.py                # Message forwarding logic
├── storage.py                 # Duplicate detection storage
├── requirements.txt           # Python dependencies
│
├── .env.example               # Example configuration
├── .env                       # Your actual configuration (git-ignored)
│
├── Dockerfile                 # Docker image definition
├── docker-compose.yml         # Docker Compose for local dev
├── docker-compose.ci.yml      # Docker Compose for CI/CD (uses secrets)
├── .dockerignore              # Files to exclude from Docker
│
├── .github/workflows/         # GitHub Actions workflows
│   ├── ci.yml                 # CI/CD pipeline
│   ├── deploy.yml             # Deployment workflow
│   ├── manual-tasks.yml       # Manual utility tasks
│   └── setup-secrets.yml      # Server secrets setup
│
├── README.md                  # This file
├── DOCKER.md                  # Docker setup guide
├── GITHUB_ACTIONS.md          # GitHub Actions guide
├── SECRETS_SETUP.md           # GitHub Secrets setup guide
│
├── userbot_session.session    # Telegram session (auto-created)
├── processed_messages.db      # SQLite database (auto-created)
└── userbot.log                # Log file (auto-created)
```

## 🔧 Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_ID` | ✅ | - | Telegram API ID |
| `API_HASH` | ✅ | - | Telegram API hash |
| `TARGET_USER_ID` | ✅ | - | User ID to forward messages to |
| `KEYWORDS` | ✅ | - | Comma-separated keywords |
| `AUTO_REPLY_ENABLED` | ❌ | false | Enable auto-reply |
| `AUTO_REPLY_TEXT` | ❌ | "Interested!" | Auto-reply message |
| `AUTO_REPLY_MIN_DELAY` | ❌ | 5 | Minimum delay (seconds) |
| `AUTO_REPLY_MAX_DELAY` | ❌ | 15 | Maximum delay (seconds) |
| `SESSION_NAME` | ❌ | userbot_session | Session file name |

### Hardcoded Settings (config.py)

- `CHAT_IDS`: List of chats to monitor

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

```bash
# .env
KEYWORDS=laptop,macbook,iphone,ipad,airpods,gaming pc
TARGET_USER_ID=123456789
AUTO_REPLY_ENABLED=true
AUTO_REPLY_TEXT=Hi! Is this still available? What's your best price?
```

```python
# config.py
CHAT_IDS = [
    "@electronics_marketplace",
    "@tech_deals_channel",
]
```

### Example 2: Monitor without auto-reply

```bash
# .env
KEYWORDS=bicycle,bike,mtb,road bike
TARGET_USER_ID=123456789
AUTO_REPLY_ENABLED=false
```

## 🐛 Troubleshooting

### "Configuration validation failed"
- Check that all required variables are set in `.env`
- Ensure `CHAT_IDS` is configured in `config.py`

### "FloodWaitError"
- Telegram is rate-limiting your account
- The bot will automatically wait and retry
- Reduce the frequency of actions if this persists

### "UserIsBlockedError"
- The target user has blocked your account
- Update `TARGET_USER_ID` to a different user

### Messages not being forwarded
- Check that your account is a member of the monitored chats
- Verify keywords are correct (case-insensitive)
- Check `userbot.log` for errors

### Session errors
- Delete the `.session` file and re-authenticate
- Make sure your API credentials are correct

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
- Use GitHub Secrets with `docker-compose.ci.yml`
- See [SECRETS_SETUP.md](SECRETS_SETUP.md)

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

