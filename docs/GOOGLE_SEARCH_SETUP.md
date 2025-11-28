# Google Custom Search API Setup

Google Custom Search API provides higher quality search results than Tavily and has a generous free tier.

## Free Tier
- **100 queries per day** completely free
- After that: $5 per 1000 queries (very affordable)

## Setup Steps

### 1. Get Google Custom Search API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Custom Search API**:
   - Go to "APIs & Services" → "Library"
   - Search for "Custom Search API"
   - Click "Enable"
4. Create API credentials:
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "API Key"
   - Copy your API key
   - **Recommended**: Restrict the API key to only Custom Search API

### 2. Create Custom Search Engine

1. Go to [Programmable Search Engine](https://programmablesearchengine.google.com/)
2. Click "Add" to create a new search engine
3. Configuration:
   - **Sites to search**: Enter `www.google.com` (or leave empty for entire web)
   - **Language**: English (or your preference)
   - **Name**: "WompBot Search" (or whatever you like)
4. After creation, click "Control Panel" for your search engine
5. In "Setup" → "Basics":
   - Enable "Search the entire web"
   - Copy your **Search engine ID (cx)** - you'll need this

### 3. Configure WompBot

Add these to your `.env` file:

```bash
# Switch to Google search
SEARCH_PROVIDER=google

# Google API credentials
GOOGLE_SEARCH_API_KEY=your_api_key_here
GOOGLE_SEARCH_CX=your_search_engine_id_here
```

### 4. Restart Bot

```bash
docker-compose restart bot
```

You should see in the logs:
```
🔍 Search provider: GOOGLE
```

## Comparison: Google vs Tavily

| Feature | Google Custom Search | Tavily |
|---------|---------------------|--------|
| **Quality** | ⭐⭐⭐⭐⭐ Excellent (Google's index) | ⭐⭐⭐⭐ Good |
| **Free Tier** | 100 queries/day | Limited (paid) |
| **Cost** | $5/1000 queries after free tier | Varies |
| **Setup** | Slightly more complex | Very simple |
| **Best For** | Most users, high-quality results | Quick setup, no Google account |

## Monitoring Usage

Check your Google Cloud Console to monitor API usage:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Go to "APIs & Services" → "Dashboard"
4. Click on "Custom Search API" to see usage stats

## Troubleshooting

### "API key not valid" error
- Check that Custom Search API is enabled in your project
- Verify the API key is copied correctly (no extra spaces)
- Check if API key restrictions are blocking requests

### "Invalid search engine ID" error
- Verify the CX value is copied correctly from the search engine control panel
- Make sure "Search the entire web" is enabled in search engine settings

### Bot falls back to Tavily
- If Google credentials are missing/invalid, bot automatically uses Tavily
- Check logs for: `⚠️ Google Search API key or CX not configured, falling back to Tavily`
