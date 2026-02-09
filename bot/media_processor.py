"""
Media Processing Utilities for Vision Analysis
Transcript-first approach: prioritize audio/text content over frame extraction
"""

import io
import ipaddress
import logging
import os
import re
import base64
import asyncio
import tempfile
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import socket

from PIL import Image
import requests

logger = logging.getLogger(__name__)

# Maximum download sizes (bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024       # 10 MB
MAX_GIF_SIZE = 20 * 1024 * 1024         # 20 MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024      # 100 MB
MAX_FFMPEG_INPUT_SIZE = 200 * 1024 * 1024  # 200 MB — guard before spawning ffmpeg

# RFC 1918, link-local, loopback, and cloud metadata IP ranges to block (SSRF prevention)
_BLOCKED_NETWORKS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),      # Link-local
    ipaddress.ip_network('0.0.0.0/8'),
    ipaddress.ip_network('::1/128'),              # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),             # IPv6 private
    ipaddress.ip_network('fe80::/10'),            # IPv6 link-local
]


def _is_safe_url(url: str) -> bool:
    """Check that a URL does not point to a private/internal IP address (SSRF prevention)."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False

        # Resolve hostname to IP addresses
        addr_infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _type, _proto, _canonname, sockaddr in addr_infos:
            ip = ipaddress.ip_address(sockaddr[0])
            for network in _BLOCKED_NETWORKS:
                if ip in network:
                    logger.warning("SSRF blocked: %s resolved to private IP %s", hostname, ip)
                    return False
        return True
    except (socket.gaierror, ValueError, OSError) as e:
        # DNS failure or invalid URL — fail closed
        logger.warning("SSRF check failed for %s: %s", url, e)
        return False


def _check_content_length(session: requests.Session, url: str, max_bytes: int) -> Optional[int]:
    """Send HEAD request to check Content-Length before downloading.
    Returns content length if available and within limit, or None if HEAD fails.
    Raises ValueError if content exceeds max_bytes."""
    try:
        head = session.head(url, timeout=10, allow_redirects=True)
        cl = head.headers.get('Content-Length')
        if cl is not None:
            size = int(cl)
            if size > max_bytes:
                raise ValueError(f"File too large: {size / 1024 / 1024:.1f}MB exceeds {max_bytes / 1024 / 1024:.0f}MB limit")
            return size
    except (requests.RequestException, ValueError) as e:
        if isinstance(e, ValueError) and "File too large" in str(e):
            raise  # Re-raise size limit errors
        # HEAD failed or no Content-Length — proceed with streaming download and enforce limit there
    return None


def _streaming_download(session: requests.Session, url: str, max_bytes: int, timeout: int = 60) -> bytes:
    """Download URL with streaming size enforcement.
    Raises ValueError if download exceeds max_bytes."""
    response = session.get(url, timeout=timeout, stream=True)
    response.raise_for_status()

    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=8192):
        total += len(chunk)
        if total > max_bytes:
            response.close()
            raise ValueError(f"Download exceeded {max_bytes / 1024 / 1024:.0f}MB limit (aborted at {total / 1024 / 1024:.1f}MB)")
        chunks.append(chunk)

    return b''.join(chunks)


class MediaProcessor:
    """
    Process media files for AI analysis.

    Strategy:
    - YouTube: Transcript first (instant), frames only if needed
    - Videos: Audio transcription via Whisper, frames only if needed
    - GIFs: Frame extraction (no audio)
    """

    YOUTUBE_PATTERNS = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.openai_api_key = os.getenv('OPENAI_API_KEY')

    def extract_youtube_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL"""
        for pattern in self.YOUTUBE_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube video"""
        return self.extract_youtube_id(url) is not None

    async def analyze_youtube_video(self, video_id: str, need_visuals: bool = False) -> Dict[str, Any]:
        """
        Analyze YouTube video - transcript first, visuals only if needed.

        Args:
            video_id: YouTube video ID
            need_visuals: If True, also extract frames for visual analysis

        Returns:
            Dict with transcript, metadata, and optionally frames
        """
        result = {
            "success": False,
            "video_id": video_id,
            "title": None,
            "author": None,
            "duration": None,
            "transcript": None,
            "frames": [],
            "frame_timestamps": [],
        }

        # Step 1: Get video metadata (fast, no download)
        logger.info("Getting YouTube video info: %s", video_id)
        metadata = await self._get_youtube_metadata(video_id)
        if metadata:
            result["title"] = metadata.get("title", "Unknown")
            result["author"] = metadata.get("author", "Unknown")
            result["duration"] = metadata.get("duration", 0)
            logger.info("Video title: %s, duration: %ss", result['title'], result['duration'])

        # Step 2: Get transcript (instant, no download)
        logger.info("Fetching transcript...")
        transcript = await self._get_youtube_transcript(video_id)
        if transcript:
            result["transcript"] = transcript
            result["success"] = True
            logger.info("Got transcript (%d chars)", len(transcript))
        else:
            logger.info("No transcript available")

        # Step 3: Get thumbnail (quick visual reference)
        thumbnail = await self._get_youtube_thumbnail(video_id)
        if thumbnail:
            result["frames"].append(thumbnail)
            result["frame_timestamps"].append("thumbnail")

        # Step 4: Only extract video frames if explicitly needed AND no transcript
        if need_visuals and not transcript:
            logger.info("Extracting video frames (no transcript available)...")
            frames_result = await self._extract_youtube_frames(video_id)
            if frames_result.get("success"):
                result["frames"] = frames_result.get("frames", [])
                result["frame_timestamps"] = frames_result.get("timestamps", [])
                result["success"] = True

        # Success if we have transcript OR frames
        if result["transcript"] or result["frames"]:
            result["success"] = True

        return result

    async def _get_youtube_metadata(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video metadata via oEmbed (no download needed)"""
        try:
            def fetch():
                url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
                resp = self.session.get(url, timeout=10)
                return resp

            response = await asyncio.to_thread(fetch)
            if response.status_code == 200:
                data = response.json()
                return {
                    "title": data.get("title"),
                    "author": data.get("author_name"),
                }
        except Exception as e:
            logger.warning("Metadata fetch error: %s", e)

        # Fallback: try yt-dlp for more info
        try:
            import yt_dlp

            def get_info():
                ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                    return {
                        "title": info.get("title"),
                        "author": info.get("uploader"),
                        "duration": info.get("duration", 0),
                    }

            return await asyncio.to_thread(get_info)
        except Exception:
            pass

        return None

    async def _get_youtube_transcript(self, video_id: str) -> Optional[str]:
        """Get YouTube transcript via API (instant, no download)"""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

            def fetch():
                try:
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

                    # Try English first
                    try:
                        transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
                    except Exception:
                        # Try auto-generated
                        try:
                            transcript = transcript_list.find_generated_transcript(['en'])
                        except Exception:
                            # Get any available and translate
                            for t in transcript_list:
                                transcript = t.translate('en')
                                break

                    data = transcript.fetch()

                    # Format with timestamps
                    lines = []
                    for entry in data:
                        mins = int(entry['start']) // 60
                        secs = int(entry['start']) % 60
                        text = entry['text'].replace('\n', ' ').strip()
                        if text:
                            lines.append(f"[{mins}:{secs:02d}] {text}")

                    return '\n'.join(lines)

                except (NoTranscriptFound, TranscriptsDisabled):
                    return None

            return await asyncio.to_thread(fetch)

        except ImportError:
            return None
        except Exception as e:
            logger.warning("Transcript error: %s", e)
            return None

    async def _get_youtube_thumbnail(self, video_id: str) -> Optional[str]:
        """Get high-quality thumbnail as base64"""
        urls = [
            f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
            f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        ]

        for url in urls:
            try:
                def fetch():
                    return self.session.get(url, timeout=10)

                resp = await asyncio.to_thread(fetch)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    return base64.b64encode(resp.content).decode('utf-8')
            except Exception:
                continue
        return None

    async def download_and_resize_image(self, url: str, max_size: int = 768) -> Optional[str]:
        """Download an image URL and resize to reduce vision API token cost.

        Returns base64-encoded JPEG string, or None on failure.
        Images are resized so the longest dimension is at most max_size pixels.
        Includes SSRF protection and download size cap.
        """
        # SSRF check — block private/internal IPs
        if not _is_safe_url(url):
            logger.warning("Image download blocked (SSRF): %s", url[:80])
            return None

        try:
            # HEAD preflight to check size
            _check_content_length(self.session, url, MAX_IMAGE_SIZE)

            def _download_and_process():
                data = _streaming_download(self.session, url, MAX_IMAGE_SIZE, timeout=15)
                if len(data) < 500:
                    return None

                img = Image.open(io.BytesIO(data))
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Resize if larger than max_size
                if max(img.size) > max_size:
                    ratio = max_size / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)

                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=80)
                return base64.b64encode(buf.getvalue()).decode('utf-8')

            return await asyncio.to_thread(_download_and_process)
        except ValueError as e:
            logger.warning("Image download rejected: %s — %s", url[:80], e)
            return None
        except Exception as e:
            logger.warning("Failed to download/resize image %s: %s", url[:80], e)
            return None

    async def _extract_youtube_frames(self, video_id: str, num_frames: int = 6) -> Dict[str, Any]:
        """Download and extract frames (only used as fallback)"""
        try:
            import yt_dlp
        except ImportError:
            return {"success": False, "error": "yt-dlp not installed"}

        temp_dir = None
        try:
            temp_dir = tempfile.mkdtemp(prefix="yt_")
            video_path = os.path.join(temp_dir, "video.mp4")

            # Download at low quality to save time
            ydl_opts = {
                'format': 'worst[ext=mp4]/worst',
                'outtmpl': video_path,
                'quiet': True,
                'socket_timeout': 30,
            }

            def download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
                    return info.get('duration', 60)

            duration = await asyncio.to_thread(download)

            frames, timestamps = await self._extract_frames_ffmpeg(video_path, duration, num_frames)

            return {
                "success": bool(frames),
                "frames": frames,
                "timestamps": timestamps,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if temp_dir:
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                except OSError as e:
                    logger.warning("Failed to clean up temp dir %s: %s", temp_dir, e)

    async def analyze_video_file(self, url: str, need_visuals: bool = False) -> Dict[str, Any]:
        """
        Analyze video file (Discord attachment, etc.)

        Uses Whisper for audio transcription, frames only if needed.
        Includes SSRF protection, download size cap, and FFmpeg file size guard.
        """
        result = {
            "success": False,
            "transcript": None,
            "frames": [],
            "frame_timestamps": [],
            "duration": 0,
        }

        # SSRF check — block private/internal IPs
        if not _is_safe_url(url):
            logger.warning("Video download blocked (SSRF): %s", url[:80])
            return {"success": False, "error": "URL blocked by security policy"}

        temp_dir = None
        try:
            # HEAD preflight for size check
            _check_content_length(self.session, url, MAX_VIDEO_SIZE)

            # Download video with streaming size enforcement
            logger.info("Downloading video...")

            def download_and_save(path):
                data = _streaming_download(self.session, url, MAX_VIDEO_SIZE, timeout=60)
                with open(path, 'wb') as f:
                    f.write(data)
                return len(data)

            temp_dir = tempfile.mkdtemp(prefix="video_")
            video_path = os.path.join(temp_dir, "video.mp4")
            audio_path = os.path.join(temp_dir, "audio.mp3")

            file_size = await asyncio.to_thread(download_and_save, video_path)

            # FFmpeg file size guard — refuse to process files over limit
            if file_size > MAX_FFMPEG_INPUT_SIZE:
                logger.warning("Video too large for FFmpeg processing: %dMB", file_size // (1024 * 1024))
                return {"success": False, "error": f"Video too large ({file_size // (1024 * 1024)}MB)"}

            # Get duration
            duration = await self._get_video_duration(video_path)
            result["duration"] = duration
            logger.info("Video duration: %.1fs", duration)

            # Extract audio and transcribe with Whisper
            logger.info("Extracting and transcribing audio...")
            transcript = await self._transcribe_video_audio(video_path, audio_path)
            if transcript:
                result["transcript"] = transcript
                result["success"] = True
                logger.info("Got transcription (%d chars)", len(transcript))

            # Extract frames only if needed
            if need_visuals or not transcript:
                logger.info("Extracting frames...")
                frames, timestamps = await self._extract_frames_ffmpeg(video_path, duration, 6)
                if frames:
                    result["frames"] = frames
                    result["frame_timestamps"] = timestamps
                    result["success"] = True

            return result

        except ValueError as e:
            logger.warning("Video download rejected: %s — %s", url[:80], e)
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error("Video analysis error: %s", e, exc_info=True)
            return {"success": False, "error": "Video analysis failed"}
        finally:
            if temp_dir:
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                except OSError as e:
                    logger.warning("Failed to clean up temp dir %s: %s", temp_dir, e)

    async def _transcribe_video_audio(self, video_path: str, audio_path: str) -> Optional[str]:
        """Extract audio and transcribe with Whisper API"""
        if not self.openai_api_key:
            logger.warning("No OpenAI API key for Whisper transcription")
            return None

        try:
            # Extract audio with ffmpeg
            def extract_audio():
                cmd = [
                    'ffmpeg', '-i', video_path,
                    '-vn',  # No video
                    '-acodec', 'libmp3lame',
                    '-ar', '16000',  # 16kHz for Whisper
                    '-ac', '1',  # Mono
                    '-b:a', '64k',  # Low bitrate
                    '-y', audio_path
                ]
                result = subprocess.run(cmd, capture_output=True, timeout=60)
                return result.returncode == 0 and os.path.exists(audio_path)

            success = await asyncio.to_thread(extract_audio)
            if not success:
                return None

            # Check file size (Whisper has 25MB limit)
            file_size = os.path.getsize(audio_path)
            if file_size > 25 * 1024 * 1024:
                logger.warning("Audio too large for Whisper (%dMB)", file_size // 1024 // 1024)
                return None

            # Transcribe with Whisper API
            def transcribe():
                with open(audio_path, 'rb') as audio_file:
                    response = requests.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {self.openai_api_key}"},
                        files={"file": audio_file},
                        data={
                            "model": "whisper-1",
                            "response_format": "verbose_json",
                            "timestamp_granularities[]": "segment"
                        },
                        timeout=120
                    )
                    return response

            response = await asyncio.to_thread(transcribe)

            if response.status_code == 200:
                data = response.json()

                # Format with timestamps
                segments = data.get("segments", [])
                if segments:
                    lines = []
                    for seg in segments:
                        start = int(seg.get("start", 0))
                        mins, secs = start // 60, start % 60
                        text = seg.get("text", "").strip()
                        if text:
                            lines.append(f"[{mins}:{secs:02d}] {text}")
                    return '\n'.join(lines)
                else:
                    return data.get("text", "")
            else:
                logger.warning("Whisper API error: %d", response.status_code)
                return None

        except Exception as e:
            logger.warning("Transcription error: %s", e)
            return None

    async def _get_video_duration(self, video_path: str) -> float:
        """Get video duration using ffprobe"""
        def probe():
            cmd = [
                'ffprobe', '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            try:
                return float(result.stdout.strip())
            except (ValueError, AttributeError):
                return 30.0

        return await asyncio.to_thread(probe)

    async def _extract_frames_ffmpeg(
        self,
        video_path: str,
        duration: float,
        num_frames: int
    ) -> Tuple[List[str], List[str]]:
        """Extract evenly-spaced frames from video"""
        frames = []
        timestamps = []

        if duration <= 0:
            duration = 30

        # Calculate timestamps (skip first/last 5%)
        start = max(1, duration * 0.05)
        end = duration - max(1, duration * 0.05)
        interval = (end - start) / (num_frames - 1) if num_frames > 1 else 0

        for i in range(num_frames):
            ts = start + (i * interval)
            mins, secs = int(ts) // 60, int(ts) % 60
            ts_str = f"{mins}:{secs:02d}"

            try:
                def extract():
                    cmd = [
                        'ffmpeg', '-ss', str(ts), '-i', video_path,
                        '-vframes', '1', '-f', 'image2pipe',
                        '-vcodec', 'mjpeg', '-q:v', '3',
                        '-vf', 'scale=960:-1', '-'
                    ]
                    result = subprocess.run(cmd, capture_output=True, timeout=15)
                    return result.stdout if result.returncode == 0 else None

                frame_data = await asyncio.to_thread(extract)
                if frame_data:
                    frames.append(base64.b64encode(frame_data).decode('utf-8'))
                    timestamps.append(ts_str)
            except Exception:
                continue

        return frames, timestamps

    async def extract_gif_frames(self, url: str, max_frames: int = 6) -> Dict[str, Any]:
        """Extract frames from animated GIF. Includes SSRF protection and size cap."""
        # SSRF check
        if not _is_safe_url(url):
            logger.warning("GIF download blocked (SSRF): %s", url[:80])
            return {"success": False, "error": "URL blocked by security policy"}

        try:
            # HEAD preflight for size check
            _check_content_length(self.session, url, MAX_GIF_SIZE)

            def download():
                return _streaming_download(self.session, url, MAX_GIF_SIZE, timeout=30)

            data = await asyncio.to_thread(download)
            img = Image.open(io.BytesIO(data))

            total_frames = getattr(img, 'n_frames', 1)
            is_animated = total_frames > 1

            if not is_animated:
                # Static image
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                buf = io.BytesIO()
                img.save(buf, format='JPEG', quality=85)
                return {
                    "success": True,
                    "is_animated": False,
                    "frames": [base64.b64encode(buf.getvalue()).decode('utf-8')],
                    "total_frames": 1,
                }

            # Extract evenly-spaced frames
            indices = [int(i * total_frames / max_frames) for i in range(max_frames)]
            frames = []

            for idx in indices:
                try:
                    img.seek(idx)
                    frame = img.copy()
                    if frame.mode != 'RGB':
                        frame = frame.convert('RGB')

                    # Resize if needed
                    if max(frame.size) > 800:
                        ratio = 800 / max(frame.size)
                        frame = frame.resize(
                            (int(frame.size[0] * ratio), int(frame.size[1] * ratio)),
                            Image.Resampling.LANCZOS
                        )

                    buf = io.BytesIO()
                    frame.save(buf, format='JPEG', quality=85)
                    frames.append(base64.b64encode(buf.getvalue()).decode('utf-8'))
                except Exception:
                    continue

            return {
                "success": bool(frames),
                "is_animated": True,
                "frames": frames,
                "total_frames": total_frames,
            }

        except ValueError as e:
            logger.warning("GIF download rejected: %s — %s", url[:80], e)
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Global instance
_media_processor = None

def get_media_processor() -> MediaProcessor:
    global _media_processor
    if _media_processor is None:
        _media_processor = MediaProcessor()
    return _media_processor
