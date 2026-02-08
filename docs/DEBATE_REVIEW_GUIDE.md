# Debate Review Guide

This guide explains how to use the `!debate_review` command to analyze debate transcripts from text files.

## Overview

The `!debate_review` command allows you to:
- Upload a debate transcript as a text file
- Get AI-powered analysis including scores, fallacies, and winner determination
- Review past debates that weren't tracked with `/debate_start` (stays as slash command)
- Analyze debates from external sources (Discord exports, chat logs, etc.)

## Quick Start

1. Create or export a debate transcript in the proper format (see below)
2. Save it as a `.txt`, `.log`, or `.md` file
3. Run `!debate_review` in Discord
4. Upload your file and optionally provide a topic
5. Get detailed analysis with scores and winner

## Transcript Format

The expected format is simple: each message on a new line with the username followed by a colon:

```
Username1: First argument here
Username2: Counter argument
Username1: Response to counter
Username2: Further rebuttal
```

### Requirements

- **Minimum 2 participants** - At least two unique usernames
- **Minimum 5 messages** - At least 5 lines of debate content
- **Username format** - Usernames should be 32 characters or less with no spaces
- **File encoding** - Must be UTF-8 encoded
- **File size** - Maximum 1MB

### Supported File Types

- `.txt` - Plain text files
- `.log` - Log files
- `.md` - Markdown files

## Example Transcript

Here's a sample debate transcript:

```
Alice: I believe artificial intelligence will ultimately benefit humanity more than harm it. AI systems are already helping us solve complex problems in medicine, climate science, and logistics.

Bob: While AI has shown promise, the risks are too great to ignore. We're developing systems we don't fully understand, and the potential for job displacement and autonomous weapons is concerning.

Alice: Job displacement is a valid concern, but historically, technological advances have created more jobs than they've eliminated. We need to focus on retraining programs and ensuring AI augments human capabilities rather than replacing them entirely.

Bob: That's overly optimistic. The speed of AI development is unprecedented. Unlike past technological revolutions that took decades, AI could disrupt entire industries in just a few years, leaving little time for adaptation.

Alice: That's precisely why we need to embrace it now and guide its development responsibly. Countries that resist AI advancement will fall behind economically. The solution isn't to slow down progress but to implement strong ethical guidelines and governance.

Bob: Ethical guidelines mean nothing without enforcement. Look at social media - we had guidelines, but profit motives won. AI companies will prioritize advancement over safety unless we have strict regulations with real consequences.

Alice: I agree regulation is important, but we also need to avoid overregulation that stifles innovation. The key is finding balance - allowing AI research to flourish while maintaining safety standards and transparency requirements.
```

## Using the Command

### Basic Usage

```
!debate_review
- file: [Upload your transcript file]
- topic: (Optional) "AI Ethics Debate"
```

### Parameters

- **file** (required) - The debate transcript file to analyze
  - Must be `.txt`, `.log`, or `.md` format
  - Maximum size: 1MB
  - UTF-8 encoding required

- **topic** (optional) - A title/topic for the debate
  - If not provided, uses the filename (without extension)
  - Displayed in the analysis results

## Analysis Output

The bot will analyze the debate and provide:

### For Each Participant

- **Score** (0-10) - Overall argument quality rating
- **Strengths** - What they did well
- **Weaknesses** - Areas for improvement
- **Fallacies** - Any logical fallacies detected (e.g., ad hominem, strawman, appeal to authority)

### Overall Analysis

- **Winner** - Which participant presented the strongest arguments
- **Winner Reason** - Explanation of why they won
- **Summary** - High-level overview of the debate
- **Metadata** - Participant count and message count

### Example Output

```
📝 Debate Analysis: AI Ethics Debate

Analysis summary: This was a well-structured debate about AI's impact on society...

👤 Alice
Score: 8/10
Strengths: Strong arguments backed by historical precedent, balanced perspective acknowledging concerns
Weaknesses: Could have addressed specific AI safety examples more directly
Fallacies: None detected

👤 Bob
Score: 7/10
Strengths: Raised important concerns about pace of change and regulatory enforcement
Weaknesses: Some arguments relied on speculation rather than evidence
Fallacies: Slippery slope (suggesting inevitable negative outcomes)

🏆 Winner
Alice
Reason: Presented more balanced arguments with historical context while acknowledging valid concerns. Offered constructive solutions rather than just criticism.

2 participants • 7 messages
```

## Tips for Best Results

### 1. Clear Speaker Attribution

Make sure each message clearly shows who's speaking:

✅ **Good:**
```
John: I think climate change requires immediate action.
Sarah: We need to balance environmental concerns with economic realities.
```

❌ **Bad:**
```
I think climate change requires immediate action.
We need to balance environmental concerns with economic realities.
```

### 2. Multi-Line Messages

If a participant's message spans multiple lines, the parser will handle it:

```
Alice: This is a longer argument that spans
multiple lines and continues here.
The parser will treat all of this as Alice's message.

Bob: Until someone else starts speaking with their username.
```

### 3. Formatting

- Remove system messages and timestamps if possible
- Keep the debate content focused on actual arguments
- Don't include "User joined" or other meta messages

### 4. Discord Exports

If exporting from Discord:

1. Use a Discord chat export tool (e.g., DiscordChatExporter)
2. Export as plain text format
3. Clean up any unnecessary metadata
4. Ensure format matches: `Username: message`

### 5. Debate Length

- **Too short** (<5 messages): Won't provide enough data for meaningful analysis
- **Sweet spot** (10-50 messages): Best for detailed analysis
- **Very long** (100+ messages): Still works but may take longer to analyze

## Common Issues

### "Debate needs at least 2 participants"

**Problem:** The parser only detected one username or couldn't parse usernames properly.

**Solutions:**
- Ensure format is `Username: message` with a colon
- Check that usernames don't contain spaces
- Verify at least 2 different people are speaking

### "Debate needs at least 5 messages"

**Problem:** The transcript is too short.

**Solutions:**
- Add more back-and-forth arguments
- Ensure each line is being parsed as a separate message
- Check that messages aren't being skipped due to format issues

### "File must be UTF-8 encoded"

**Problem:** The file encoding isn't UTF-8.

**Solutions:**
- Re-save the file with UTF-8 encoding
- Use a text editor that supports UTF-8 (Notepad++, VS Code, etc.)
- On Windows: Save As → Encoding → UTF-8

### "Invalid file type"

**Problem:** File extension not recognized.

**Solutions:**
- Rename file to end with `.txt`, `.log`, or `.md`
- Don't upload `.doc`, `.docx`, or `.pdf` files
- Convert to plain text first

### Empty or Invalid Analysis

**Problem:** The AI analysis didn't return expected format.

**Solutions:**
- Check the raw error message in the output
- Verify the debate has substantive arguments (not just greetings)
- Ensure messages are in English (or the language the bot supports)
- Try with a different/simpler transcript first

## Comparison with Live Debates

| Feature | Live Debate (`/debate_start`) | File Review (`!debate_review`) |
|---------|-------------------------------|--------------------------------|
| Real-time tracking | ✅ Yes | ❌ No |
| Requires active debate | ✅ Yes | ❌ No |
| Saved to database | ✅ Yes | ❌ No (analysis only) |
| Counts toward stats | ✅ Yes | ❌ No |
| External transcripts | ❌ No | ✅ Yes |
| Flexible format | ❌ No | ✅ Yes |
| Historical analysis | ❌ No | ✅ Yes |

**When to use `!debate_review`:**
- Analyzing past debates that weren't tracked
- Reviewing debates from other platforms
- Testing the analysis system
- One-off analysis without affecting stats

**When to use `/debate_start`:**
- Tracking a debate happening right now
- Want results saved for stats/leaderboard
- Recording debate for future reference
- Official server debates

## Privacy & Data

- `!debate_review` does **NOT** save the debate to the database
- Analysis is temporary and only shown in Discord
- The uploaded file is processed and discarded immediately
- No participant stats are affected
- This is purely for analysis purposes

If you want the debate saved and counted toward stats, use the live tracking commands (`/debate_start` and `!debate_end`) instead.

## Related Commands

- `/debate_start <topic>` - Start tracking a live debate
- `!debate_end` - End live debate and show analysis
- `!debate_stats` - View your debate statistics
- `!debate_lb` - See top debaters

## Examples

### Example 1: Philosophy Debate

**File:** `philosophy_debate.txt`
```
Plato2024: Universal forms exist independently of physical reality. The perfect circle we imagine is more real than any circle we can draw.

Aristotle2024: That's too abstract. Real knowledge comes from observing the physical world. A drawn circle is real and measurable.

Plato2024: But the drawn circle is imperfect. It only approximates the true form of a circle that exists in the realm of ideas.

Aristotle2024: The 'perfect circle' is just a concept derived from observing many real circles. We abstract from reality, not the other way around.

Plato2024: Then how do we recognize imperfect circles as circles at all? We must have innate knowledge of the perfect form to judge copies.

Aristotle2024: We recognize patterns through experience and categorization. No mystical forms required.
```

**Command:** `!debate_review file:philosophy_debate.txt topic:Philosophy - Forms vs Empiricism`

### Example 2: Tech Debate (Markdown Format)

**File:** `vim_vs_emacs.md`
```markdown
# The Great Editor War

DevMike: Vim is objectively superior. Modal editing is more efficient once you learn it, and it's available on every system.

DevSarah: Emacs is more than an editor - it's a platform. You can do email, git, and even browse the web. It's infinitely customizable.

DevMike: That bloat is exactly the problem. An editor should edit text efficiently, not try to be an operating system.

DevSarah: It's not bloat if you use those features. Why switch contexts between applications when you can do everything in one place?

DevMike: Because switching applications is faster than loading Emacs. Vim starts instantly.

DevSarah: Modern computers handle Emacs fine. And once it's loaded, you never close it. The "eight megs and constantly swapping" joke is decades old.
```

**Command:** `!debate_review file:vim_vs_emacs.md`

## Support

If you encounter issues:

1. Check this guide for common problems
2. Verify your file format matches the examples
3. Test with a simple 2-person, 5-message transcript first
4. Check bot logs for detailed error messages
5. Report persistent issues to the bot administrator

## Technical Details

### Parser Logic

The transcript parser:
1. Splits text into lines
2. Looks for pattern `Username: content`
3. Validates username (≤32 chars, no spaces)
4. Groups multi-line messages from same speaker
5. Tracks unique participants
6. Validates minimum requirements

### Analysis Model

The debate is analyzed using the same LLM (configured via MODEL_NAME) as live debates:
- Evaluates argument quality and coherence
- Identifies logical fallacies
- Assesses strengths and weaknesses
- Determines winner based on overall argument strength
- Provides constructive feedback

### Cost Considerations

Each analysis uses the bot's OpenRouter API quota. The cost is typically:
- Small debates (5-20 messages): ~$0.01-0.03
- Medium debates (20-50 messages): ~$0.03-0.10
- Large debates (50-100 messages): ~$0.10-0.25

To prevent abuse, consider:
- Setting rate limits for the command
- Restricting to specific roles if needed
- Monitoring API costs if usage is high
