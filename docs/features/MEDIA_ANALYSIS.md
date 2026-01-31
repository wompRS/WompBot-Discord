# Media Analysis

WompBot can analyze images, GIFs, YouTube videos, and video attachments using vision AI and audio transcription.

## Overview

When you share media with WompBot, it automatically processes the content to understand and describe what's happening. The bot uses a **transcript-first approach** for videos - prioritizing audio/text content over visual analysis for faster, more accurate results.

## Supported Media Types

### Images
- **Formats:** PNG, JPG, JPEG, WebP
- **Analysis:** Full vision AI analysis - describes content, reads text, identifies objects, scenes, and memes
- **Processing:** Direct URL passed to vision model (instant)

### Animated GIFs
- **Formats:** GIF (animated or static)
- **Analysis:** Extracts 6 frames spread across the animation to capture the full motion
- **Processing:** Frames extracted and encoded for vision analysis
- **Output:** Describes the action/motion across all frames

### YouTube Videos
- **Detection:** Automatically detects YouTube links (youtube.com, youtu.be, shorts)
- **Transcript-First:** Fetches captions/transcript instantly via YouTube API (no download required)
- **Visual Reference:** Gets video thumbnail for context
- **Fallback:** If no transcript available, extracts frames from the video
- **Metadata:** Includes title, author, and duration

### Video Attachments
- **Formats:** MP4, WebM, MOV, MPEG, AVI, MKV
- **Transcription:** Extracts audio and transcribes using OpenAI Whisper API
- **Timestamps:** Transcript includes timestamps for each segment
- **Fallback:** If transcription fails, extracts visual frames
- **Processing:** Downloads video, extracts audio, sends to Whisper

## How It Works

### Transcript-First Strategy

For videos, WompBot prioritizes audio content because:
1. **Speed:** YouTube transcripts are fetched instantly (no video download)
2. **Accuracy:** Dialogue and narration provide better context than visual frames
3. **Efficiency:** Less bandwidth and processing than downloading full videos

### Processing Flow

**YouTube Videos:**
1. Detect YouTube URL in message
2. Fetch video metadata (title, author, duration)
3. Attempt to get transcript via YouTube API
4. Get thumbnail for visual reference
5. If no transcript: extract frames from video (fallback)

**Video Attachments:**
1. Download video file
2. Extract audio track
3. Send to Whisper API for transcription
4. Include timestamps in transcript
5. If transcription fails: extract frames (fallback)

**GIFs:**
1. Download GIF file
2. Check if animated (multiple frames)
3. Extract 6 evenly-spaced frames
4. Encode as base64 for vision analysis

**Images:**
1. Pass URL directly to vision model
2. No preprocessing required

## Usage Examples

### Asking About Media

Simply mention WompBot with media attached or linked:

```
@WompBot what's happening in this video?
[YouTube link or video attachment]
```

```
@WompBot describe this meme
[Image attachment]
```

```
@WompBot what's this GIF showing?
[GIF attachment]
```

### Media-Only Messages

If you share media with WompBot without text, it will automatically ask "What's in this?" and describe the content.

## Technical Details

### Dependencies

- **youtube-transcript-api:** Fetches YouTube captions (instant, no download)
- **yt-dlp:** Downloads YouTube videos (only used as fallback)
- **ffmpeg:** Extracts audio and video frames
- **OpenAI Whisper API:** Transcribes audio to text with timestamps
- **Pillow:** Processes GIF frames

### Environment Requirements

```env
OPENAI_API_KEY=your_openai_key  # Required for Whisper transcription
```

### Rate Limits

- YouTube transcript fetch: No limit (instant API call)
- Whisper transcription: Subject to OpenAI API limits
- Video file size: 25MB limit for Whisper audio

### Processing Messages

Users see status messages during processing:
- "Getting video transcript..." - YouTube videos
- "Transcribing video audio..." - Video attachments
- Messages are deleted after processing completes

## Configuration

No additional configuration required. Media analysis is automatically enabled when:
1. Vision-capable model is configured (Claude 3.7 Sonnet supports vision)
2. OpenAI API key is set (for Whisper transcription)
3. ffmpeg is installed (included in Docker image)

## Costs

| Media Type | Cost |
|------------|------|
| Images | Vision model tokens only |
| GIFs | Vision model tokens only |
| YouTube (with transcript) | Vision model tokens only |
| YouTube (no transcript) | Vision + video download bandwidth |
| Video attachments | Whisper API (~$0.006/minute of audio) + vision tokens |

## Limitations

- **YouTube age-restricted videos:** May not have accessible transcripts
- **Private/unlisted videos:** Transcript access depends on video settings
- **Long videos:** Transcripts truncated to 4,000 characters
- **Audio quality:** Whisper accuracy depends on audio clarity
- **Video size:** Large attachments may timeout during download

## Files

- `bot/media_processor.py` - Core media processing logic
- `bot/handlers/conversations.py` - Integration with message handling
- `bot/prompts/system_prompt.txt` - Instructions for media analysis

## Future Enhancements

- Voice message transcription (Discord voice messages)
- Auto-translate video transcripts
- Summary mode for long videos
- Frame extraction on-demand for visual analysis
