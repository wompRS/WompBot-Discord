"""
Conversation history compression using LLMLingua

Reduces token usage by 50-80% by removing less important tokens
while preserving semantic meaning.
"""

import logging
import os
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ConversationCompressor:
    """Compresses conversation history to reduce token usage"""

    def __init__(self):
        """Initialize the compression model (lazy-loaded)"""
        self._compressor = None
        self._enabled = os.getenv('ENABLE_COMPRESSION', 'true').lower() == 'true'
        self._compression_rate = float(os.getenv('COMPRESSION_RATE', '0.5'))  # 50% default
        self._min_messages_to_compress = int(os.getenv('MIN_MESSAGES_TO_COMPRESS', '8'))

        logger.info("Compression initialized (enabled: %s, rate: %s)", self._enabled, self._compression_rate)

    def _get_compressor(self):
        """Lazy-load the compression model"""
        if self._compressor is None and self._enabled:
            try:
                from llmlingua import PromptCompressor

                # Use a smaller model for CPU efficiency
                # llmlingua-2-bert-base is faster than xlm-roberta-large
                model_name = os.getenv(
                    'COMPRESSION_MODEL',
                    'microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank'
                )

                self._compressor = PromptCompressor(
                    model_name=model_name,
                    device_map="cpu",  # Use CPU to avoid GPU memory issues
                    use_llmlingua2=True,  # Enable LLMLingua-2 mode
                )
                logger.info("Compression model loaded: %s", model_name)
            except Exception as e:
                logger.warning("Failed to load compression model: %s", e)
                logger.warning("Compression will be disabled")
                self._enabled = False

        return self._compressor

    def compress_history(
        self,
        conversation_history: List[Dict],
        keep_recent: int = 8,
        bot_user_id: int = None
    ) -> str:
        """
        Compress conversation history to reduce token usage

        Args:
            conversation_history: List of message dicts with 'username', 'content', and 'user_id'
            keep_recent: Number of recent messages to keep verbatim (not compress)
            bot_user_id: The bot's user ID to identify bot messages

        Returns:
            Compressed conversation history as string
        """
        if not self._enabled:
            # Fallback: Just format messages normally
            return self._format_uncompressed(conversation_history, bot_user_id)

        # Don't compress if too few messages
        if len(conversation_history) < self._min_messages_to_compress:
            return self._format_uncompressed(conversation_history, bot_user_id)

        # Split into messages to compress and recent messages to keep
        messages_to_compress = conversation_history[:-keep_recent] if keep_recent > 0 else conversation_history
        recent_messages = conversation_history[-keep_recent:] if keep_recent > 0 else []

        # Format messages for compression with clear bot/user distinction
        history_lines = []
        for msg in messages_to_compress:
            if not msg.get('content'):
                continue
            msg_user_id = msg.get('user_id')
            is_bot = bot_user_id is not None and msg_user_id == bot_user_id
            if is_bot:
                # Mark bot messages clearly so LLM knows these are its own words
                history_lines.append(f"[YOU/WompBot]: {msg.get('content', '')}")
            else:
                history_lines.append(f"[{msg.get('username', 'User')}]: {msg.get('content', '')}")

        history_text = "\n".join(history_lines)

        if not history_text.strip():
            return self._format_uncompressed(recent_messages, bot_user_id)

        try:
            compressor = self._get_compressor()
            if compressor is None:
                return self._format_uncompressed(conversation_history, bot_user_id)

            # Compress the older messages
            compressed = compressor.compress_prompt(
                history_text,
                rate=self._compression_rate,
                force_tokens=['\n', ':', '?', '!', '.', '[', ']', 'YOU', 'WompBot'],  # Preserve structure and bot markers
            )

            compressed_text = compressed['compressed_prompt']

            # Calculate savings
            original_tokens = len(history_text.split())
            compressed_tokens = len(compressed_text.split())
            savings = (1 - compressed_tokens / original_tokens) * 100 if original_tokens > 0 else 0

            logger.info("Compressed %d messages: %d -> %d tokens (%.0f%% savings)", len(messages_to_compress), original_tokens, compressed_tokens, savings)

            # Combine compressed older messages with recent verbatim messages
            result = f"[Earlier conversation (compressed) - [YOU/WompBot] = your previous responses]:\n{compressed_text}\n\n[Recent messages (verbatim)]:\n"
            result += self._format_uncompressed(recent_messages, bot_user_id)

            return result

        except Exception as e:
            logger.warning("Compression failed: %s", e)
            logger.warning("Falling back to uncompressed")
            return self._format_uncompressed(conversation_history, bot_user_id)

    def _format_uncompressed(self, conversation_history: List[Dict], bot_user_id: int = None) -> str:
        """Format messages without compression (fallback)"""
        lines = []
        for msg in conversation_history:
            if not msg.get('content'):
                continue
            msg_user_id = msg.get('user_id')
            is_bot = bot_user_id is not None and msg_user_id == bot_user_id
            if is_bot:
                lines.append(f"[YOU/WompBot]: {msg.get('content', '')}")
            else:
                lines.append(f"[{msg.get('username', 'User')}]: {msg.get('content', '')}")
        return "\n".join(lines)

    def is_enabled(self) -> bool:
        """Check if compression is enabled"""
        return self._enabled

    def get_stats(self) -> Dict:
        """Get compression statistics"""
        return {
            'enabled': self._enabled,
            'compression_rate': self._compression_rate,
            'min_messages': self._min_messages_to_compress,
            'model_loaded': self._compressor is not None
        }
