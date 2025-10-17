# Discord Bot - Uncensored Conversational AI

A Discord bot powered by Dolphin Llama 70B with conversation memory, web search, and user behavior analysis.

## Features

- 🤖 Conversational AI with context awareness
- 🔍 Automatic web search integration (Tavily API)
- 📊 User behavior analysis and statistics
- 🗄️ PostgreSQL database for message history
- 🔒 Privacy: Role-based opt-out system
- 🎯 Uncensored political and factual discussions
- 🧠 Learns user patterns over time

## Setup Instructions

### 1. Install Dependencies (WSL2 Debian)

Already done if you followed the setup commands.

### 2. Configure Environment

Edit `.env` file and fill in your API keys:

```bash
nano .env
```

Replace these values:
- `DISCORD_TOKEN`: Your Discord bot token
- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `TAVILY_API_KEY`: Your Tavily API key
- `POSTGRES_PASSWORD`: Choose a secure password

### 3. Start the Bot

```bash
cd /mnt/e/discord-bot
docker-compose up -d
```

### 4. View Logs

```bash
docker-compose logs -f bot
```

### 5. Stop the Bot

```bash
docker-compose down
```

## Commands

- **@mention bot**: Chat with the bot (requires tagging)
- **/stats [@user]**: View user statistics and behavior analysis
- **/search <query>**: Manually search the web
- **/analyze [days]**: (Admin) Analyze user behavior patterns
- **/ping**: Check bot latency
- **/help_bot**: Show available commands

## Privacy Features

Create a Discord role called `NoDataCollection` (or customize in .env).

Users with this role:
- Messages are still logged but flagged as opted-out
- Excluded from behavior analysis
- Not included in conversation context

## Behavior Analysis

Weekly or on-demand analysis tracks:
- Profanity frequency (0-10 scale)
- Conversational tone
- Honesty patterns (fact-based vs exaggeration)
- Communication style

Use `/analyze` command to run analysis.

## Database Schema

**Tables:**
- `messages`: All Discord messages
- `user_profiles`: User metadata and message counts
- `user_behavior`: Analysis results
- `search_logs`: Web search history

## Costs

- **OpenRouter (Dolphin 70B)**: ~$10-15/month for moderate usage
- **Tavily Search**: Free up to 1000 searches/month
- **Server**: Free (local Docker)

## Troubleshooting

### Bot not responding
```bash
docker-compose logs bot
```

### Database connection issues
```bash
docker-compose restart postgres
docker-compose logs postgres
```

### Reset everything
```bash
docker-compose down -v
docker-compose up -d
```

## Model Configuration

Change model in `.env`:
```
MODEL_NAME=cognitivecomputations/dolphin-2.9.2-qwen-110b
```

Available uncensored models on OpenRouter:
- `cognitivecomputations/dolphin-2.9.2-qwen-110b` (70B)
- `cognitivecomputations/dolphin-mixtral-8x7b`
- `mistralai/mixtral-8x22b-instruct`

## Development

Edit bot code:
```bash
nano bot/main.py
```

Restart bot:
```bash
docker-compose restart bot
```

## Support

Check logs for errors:
```bash
docker-compose logs -f
```
