# `/iracing_link` - Link iRacing Account

**Usage:** `/iracing_link <customer_id>`

## Description
Links your Discord account to your iRacing customer ID, enabling access to iRacing statistics and leaderboards.

## Why Link Your Account?
- View your iRacing stats directly in Discord (`/iracing_stats`)
- Appear on server iRacing leaderboards (`/iracing_leaderboard`)
- Track your progress over time
- Compare stats with other server members
- Automatic updates of your latest race data

## How to Find Your Customer ID
1. Log in to iRacing.com
2. Go to your profile page
3. Look for "Customer ID" or check the URL (it's the number in your profile URL)
4. Example: If your profile is `https://members.iracing.com/membersite/member/CareerStats.do?custid=12345`, your Customer ID is `12345`

## Examples
```
/iracing_link 12345
/iracing_link 678901
```

## Privacy & Data
- Only your Customer ID is stored (public iRacing data)
- No login credentials are ever requested or stored
- Data is fetched from public iRacing endpoints
- You can unlink anytime (contact admin)
- Subject to opt-out: `/wompbot_optout` stops all data collection

## Related Commands
- `/iracing_stats [@user]` - View iRacing statistics
- `/iracing_leaderboard` - Server iRacing leaderboard
- `/iracing_team_create` - Create/manage iRacing teams
- `/my_privacy_status` - Check your data collection status

## Rate Limits
- iRacing API calls are rate-limited to prevent abuse
- Background jobs update stats periodically (not real-time)
- Manual stat requests have standard cooldowns

## Troubleshooting
- **Invalid Customer ID**: Double-check the number from your iRacing profile
- **Not Found**: Ensure your iRacing profile is public
- **Already Linked**: Each Discord account can only link one iRacing account
- **API Errors**: iRacing API may be temporarily unavailable

## Legal
By linking your iRacing account, you consent to WompBot fetching your public racing data from iRacing.com.
