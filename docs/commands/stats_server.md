# `/stats_server` - Server Statistics & Network Graph

**Usage:** `/stats_server [date_range]`

## Description
Displays server-wide interaction statistics with a visual network graph showing who talks to whom.

## Features
- **Network Graph**: Visual representation of user interactions
- **Most Active Users**: Top 10 users by message count
- **Most Active Channels**: Channels with highest activity
- **Interaction Patterns**: Who replies to whom most often
- **Temporal Analysis**: Activity trends over time

## Parameters
- **date_range** (optional):
  - Days: `30` (last 30 days)
  - Date range: `01/15/2024-02/15/2024`
  - Default: 30 days

## Examples
```
/stats_server
/stats_server 7
/stats_server 90
/stats_server 01/01/2025-01/31/2025
```

## Privacy
- Only includes users who haven't opted out (use `/wompbot_optout` to opt out)
- Displays aggregate data, not individual message content

## Related Commands
- `/stats [@user]` - Individual user statistics
- `/stats_topics [days]` - Trending keywords
- `/stats_primetime [@user] [days]` - Activity heatmap
- `/stats_engagement [@user] [days]` - Engagement metrics

## Technical Details
- Uses NetworkX for graph generation
- Matplotlib for visualization
- Zero LLM cost (pure machine learning)
- Rate limit: Standard Discord rate limits apply
