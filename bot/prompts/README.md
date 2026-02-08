# LLM System Prompt Customization

This directory contains the system prompts that define WompBot's personality and behavior.

## Available Personalities

WompBot has three built-in personality modes:

**Default (Conversational)** - system_prompt.txt
- Helpful and conversational tone
- Provides detailed responses with personality
- Balances information with natural conversation
- Adapts to the user's communication style
- Typical response length: 2-4 sentences

**Concise (Brief)** - system_prompt_concise.txt
- Very brief responses (1-2 sentences maximum)
- Gets straight to the point without elaboration
- Simple acknowledgments for simple statements
- No unnecessary context or explanation
- Ideal for quick information or minimal text preference

**Bogan (Australian)** - system_prompt_bogan.txt
- Full Australian slang and working-class dialect
- Casual, pub-style conversation tone
- Uses authentic Aussie expressions and humor
- Still helpful, just with strong personality
- Natural variation to sound authentic, not scripted

## How It Works

The bot automatically loads all personality prompts at startup:
1. Looks for system_prompt.txt for the default personality
2. Looks for system_prompt_bogan.txt for the bogan personality
3. Looks for system_prompt_concise.txt for the concise personality
4. Falls back to built-in defaults if files don't exist

Users with admin permissions can switch personalities using the /personality command. The setting is per-server and persists in the database.

## File Structure

- **system_prompt_sample.txt**: Sample default prompt (tracked in git)
- **system_prompt.txt**: Your custom default prompt (gitignored, not tracked)
- **system_prompt_bogan.txt**: Bogan personality (tracked in git)
- **system_prompt_concise.txt**: Concise personality (tracked in git)

## Customizing the Default Personality

To customize the default (conversational) personality:

```bash
# Copy sample to create your custom prompt
cp system_prompt_sample.txt system_prompt.txt

# Edit with your preferred personality
nano system_prompt.txt

# Restart the bot to apply changes
docker-compose restart bot
```

Your custom system_prompt.txt is gitignored, so your changes stay private.

## Built-in Capabilities

The system prompt includes documentation for:

**26 LLM Tools:**
- Weather: `get_weather`, `get_weather_forecast`
- Search: `web_search`, `wikipedia`, `define_word`, `url_preview`
- Utility: `currency_convert`, `get_time`, `translate`, `random_choice`
- Media: `youtube_search`, `movie_info`, `stock_price`, `stock_history`
- Sports: `sports_scores`
- iRacing: `iracing_driver_stats`, `iracing_series_info`
- Discord: `user_stats`, `create_reminder`

**Media Analysis:**
- Images: Full vision analysis
- Animated GIFs: 6-frame extraction
- YouTube Videos: Transcript + thumbnail
- Video Attachments: Whisper transcription + frames

## What You Can Customize

The system prompt controls:
- Personality traits (formal, casual, sarcastic, helpful)
- Response style (concise, detailed, technical, conversational)
- Behavior rules (emoji usage, profanity, tone matching)
- Knowledge limitations (what to admit not knowing)
- Special instructions (topic avoidance, user handling)

## Customization Examples

**Make it more formal:**
```
You are WompBot, a professional Discord assistant.

RESPONSE STYLE:
- Maintain professional tone at all times
- Use complete sentences with proper grammar
- Avoid slang, profanity, or casual language
- Provide thorough, well-structured responses
```

**Make it more technical:**
```
You are WompBot, a technical Discord assistant.

EXPERTISE:
- Prioritize accuracy and technical detail
- Use precise terminology
- Include code examples when relevant
- Cite sources and documentation
- Explain complex concepts clearly
```

**Make it more humorous:**
```
You are WompBot, a witty Discord bot with a sense of humor.

PERSONALITY:
- Use clever wordplay and puns
- Add humorous observations
- Don't take yourself too seriously
- Still provide helpful information beneath the jokes
```

## Best Practices

1. **Test changes**: Try different prompts to see what works for your server
2. **Be specific**: Clear instructions lead to consistent behavior
3. **Set boundaries**: Define what the bot should and shouldn't do
4. **Balance personality**: Helpful first, personality second
5. **Restart bot**: Changes only apply after restarting the bot container

## Notes

- system_prompt.txt is gitignored - your customizations stay private
- The bot falls back to built-in defaults if files are missing or corrupted
- All personalities are loaded at startup and cached for performance
- Personality changes take effect immediately when switched via /personality command
- You can reload prompts by restarting: docker-compose restart bot

## Current Personalities

See the individual prompt files for full details:
- system_prompt_sample.txt - Default conversational personality
- system_prompt_concise.txt - Brief, direct responses
- system_prompt_bogan.txt - Australian slang mode

Each personality maintains the same knowledge limitations and safety guidelines while adapting the communication style.
