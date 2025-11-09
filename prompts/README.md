# LLM System Prompt Customization

This directory contains the system prompt that defines WompBot's personality and behavior.

## How It Works

- **`system_prompt_sample.txt`**: Default sample prompt (tracked in git)
- **`system_prompt.txt`**: Your custom prompt (gitignored, not tracked)

The bot will:
1. Try to load `system_prompt.txt` (your customization)
2. Fall back to built-in default if file doesn't exist

## Setup

**To use the default personality:**
```bash
# No action needed - bot uses built-in default if file doesn't exist
```

**To customize the personality:**
```bash
# Copy sample to create your custom prompt
cp system_prompt_sample.txt system_prompt.txt

# Edit system_prompt.txt with your preferred personality
nano system_prompt.txt  # or use your editor

# Restart the bot to apply changes
docker-compose restart bot
```

## What You Can Customize

The system prompt controls:
- **Personality traits** (formal, casual, sarcastic, helpful, etc.)
- **Response style** (concise, detailed, technical, conversational)
- **Behavior rules** (emoji usage, profanity, tone matching)
- **Knowledge limitations** (what to admit not knowing)
- **Special instructions** (topic avoidance, user handling, etc.)

## Examples

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

1. **Test changes**: Try different prompts to see what works
2. **Be specific**: Clear instructions = consistent behavior
3. **Set boundaries**: Define what bot should/shouldn't do
4. **Balance personality**: Helpful first, personality second
5. **Restart bot**: Changes only apply after restart

## Notes

- `system_prompt.txt` is gitignored - your customizations stay private
- Sample prompt shows the default personality
- Bot falls back to built-in default if file is missing or corrupted
- You can reload by restarting: `docker-compose restart bot`

## Current Default

See `system_prompt_sample.txt` for the default personality:
- Conversational and helpful
- Honest about limitations
- Matches user's energy/tone
- Prioritizes value over style
- No emoji usage
