import logging
import os
import re
import threading
import time

import requests
from compression import ConversationCompressor

try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception,
        before_sleep_log,
    )
    _HAS_TENACITY = True
except ImportError:
    _HAS_TENACITY = False

try:
    import tiktoken
    _tiktoken_encoding = tiktoken.get_encoding("cl100k_base")
    _HAS_TIKTOKEN = True
except ImportError:
    _tiktoken_encoding = None
    _HAS_TIKTOKEN = False

logger = logging.getLogger(__name__)


class _TransientAPIError(Exception):
    """Wrapper for transient OpenRouter errors (429, 502, 503) that should be retried."""
    def __init__(self, status_code: int, body: str = ""):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Transient API error {status_code}")


def _is_transient_api_error(exc: BaseException) -> bool:
    """Check if an exception is a retryable transient API error."""
    return isinstance(exc, _TransientAPIError)


def _get_text_content(content):
    """Extract text from content that may be a string or multimodal list.

    When images are included, OpenAI-style APIs use a list format:
    [{"type": "text", "text": "..."}, {"type": "image_url", ...}]

    This helper safely extracts the text portion regardless of format.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Extract text from multimodal content array
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        return " ".join(text_parts)
    return str(content)


class LLMClient:
    def __init__(self, cost_tracker=None):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not set — LLM calls will fail")
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = os.getenv('MODEL_NAME', 'cognitivecomputations/dolphin-2.9.2-qwen-110b')
        # Vision model for image analysis (text models can't see images)
        # Gemini Flash Lite: $0.075/M input vs gpt-4o-mini $0.15/M — half the cost with vision support
        self.vision_model = os.getenv('VISION_MODEL', 'google/gemini-2.0-flash-lite-001')
        self.cost_tracker = cost_tracker

        # Initialize conversation compressor for token reduction
        self.compressor = ConversationCompressor()

        # Reusable HTTP session for connection pooling (avoids redundant TCP+TLS handshakes)
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json"
        })

        # Load system prompts from files (cache all personalities)
        self.system_prompt_default = self._load_system_prompt('default')
        self.system_prompt_feyd = self._load_system_prompt('feyd')
        self.system_prompt_bogan = self._load_system_prompt('bogan')
        self.system_prompt_concise = self._load_system_prompt('concise')

        # Default to professional personality
        self.system_prompt = self.system_prompt_default

    def _load_system_prompt(self, personality='default'):
        """
        Load system prompt from file or use default

        Args:
            personality: 'default', 'feyd', 'bogan', or 'concise'

        Returns:
            System prompt text
        """
        # Determine which file to load
        if personality == 'feyd':
            prompt_file = 'system_prompt_sample.txt'
        elif personality == 'bogan':
            prompt_file = 'system_prompt_bogan.txt'
        elif personality == 'concise':
            prompt_file = 'system_prompt_concise.txt'
        else:
            prompt_file = 'system_prompt.txt'

        prompt_path = os.path.join(os.path.dirname(__file__), 'prompts', prompt_file)

        # Try to load from file
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    prompt = f.read().strip()
                    if prompt:
                        logger.info("Loaded %s personality prompt from %s", personality, prompt_file)
                        return prompt
            except Exception as e:
                logger.warning("Error loading %s prompt from file: %s", personality, e)

        # Fallback to default
        logger.info("Using fallback prompt for %s personality", personality)
        return """You are WompBot, a conversational Discord bot with personality and substance.

CORE PRINCIPLE:
Be conversational AND provide actual value. Answer questions with useful information first, then add personality if it fits naturally. Don't sacrifice substance for sass.

RESPONSE STYLE:
- Keep responses concise but informative (2-4 sentences usually)
- Be direct and conversational, not formal or academic
- Use natural language like you're chatting with friends
- Add wit or sharp commentary when it enhances your point, not just for the sake of it
- If someone asks a genuine question, give them a real answer
- Challenge BS when you see it, but back it up with actual reasoning

PERSONALITY:
- You have opinions and aren't afraid to share them
- You're not overly polite or politically correct
- Match the user's energy - if they're crude or casual, you can be too
- Don't apologize for being direct
- You can swear or use crude humor when contextually appropriate
- But you're not an edgelord - you're helpful AND real

KNOWLEDGE LIMITATIONS (CRITICAL - DO NOT HALLUCINATE):
- Your knowledge cutoff is January 2025
- For ANY specific product claims, current prices, reviews, specs, comparisons: DO NOT make them up
- If you don't have reliable information, say so instead of guessing or making up "facts"
- When asked about products, tech, or current topics: stick to general knowledge ONLY or admit you need to search
- NEVER make confident specific claims (like "best sensors", "sharp lenses", specific models) without search results
- If search results are provided, use them naturally in your response
- Being honest about not knowing is better than making shit up

CONVERSATION MEMORY:
- You HAVE access to the conversation history - it's provided to you
- You CAN recall what you and users said earlier in the conversation
- If asked "what did I say" or "what were my questions" - answer from the history
- NEVER claim you don't have access to conversation history - you DO have it

CONVERSATION GUIDELINES:
- Respond to the MOST RECENT message, but you CAN reference earlier context when asked
- DO NOT re-answer old questions unprompted, but DO recall them if asked
- Answer the actual question being asked NOW
- Be conversational, not a fact-regurgitating robot
- If someone says something wrong, correct them with reasoning
- Keep it relevant to what they asked

HONESTY:
- NEVER lie unless asked to roleplay
- NEVER deny saying something you said (no gaslighting)
- If you were wrong, admit it: "You're right, I was wrong"

RULES:
- NO EMOJIS - express yourself with words
- No images/GIFs (you can't post them)
- Stay on topic - don't drag old conversations into new ones
- When mentioning users, use @username format (like @john), never raw user IDs
- Provide value first, personality second

Be useful and real. That's the balance."""

    def simple_completion(self, prompt: str, max_tokens: int = 500, temperature: float = 0.3, model: str = None, cost_request_type: str = "simple_completion", system_prompt: str = None) -> str:
        """
        Simple prompt->response completion for internal use (claims, fact_check, etc.).
        Centralizes the OpenRouter API call pattern so other modules don't duplicate it.
        Retries on transient errors (429/502/503) with exponential backoff via tenacity.

        Args:
            prompt: The prompt text
            max_tokens: Maximum response tokens
            temperature: Sampling temperature
            model: Model to use (defaults to self.model)
            cost_request_type: Label for cost tracking
            system_prompt: Optional system prompt to prepend

        Returns:
            The response text, or empty string on error
        """
        model_to_use = model or self.model

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_to_use,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            response = self._simple_completion_with_retry(headers, payload)

            result = response.json()
            response_text = result["choices"][0]["message"].get("content", "")

            # Track costs if cost tracker is available
            usage = result.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            if self.cost_tracker and input_tokens > 0:
                try:
                    self.cost_tracker.record_costs_sync(
                        model_to_use, input_tokens, output_tokens, cost_request_type
                    )
                except Exception as e:
                    logger.warning("Error tracking costs for simple_completion: %s", e)

            return response_text

        except _TransientAPIError as e:
            logger.error("simple_completion transient error after retries: %d", e.status_code)
            return ""
        except Exception as e:
            logger.error("simple_completion error: %s: %s", type(e).__name__, e)
            return ""

    def _simple_completion_request(self, headers, payload):
        """Make a single simple_completion HTTP request, raising _TransientAPIError for retryable status codes."""
        response = self.session.post(self.base_url, headers=headers, json=payload, timeout=(5, 55))
        if response.status_code in (429, 502, 503):
            logger.warning("simple_completion got %d, will retry", response.status_code)
            raise _TransientAPIError(response.status_code, response.text[:200] if hasattr(response, 'text') else '')
        response.raise_for_status()
        return response

    def _simple_completion_with_retry(self, headers, payload):
        """Wrap _simple_completion_request with tenacity retry (fallback to manual loop)."""
        if _HAS_TENACITY:
            # Build retrying wrapper dynamically (tenacity decorators need to be applied at call time
            # since `self` is needed for logging)
            retrying = retry(
                stop=stop_after_attempt(4),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                retry=retry_if_exception(_is_transient_api_error),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            )
            return retrying(self._simple_completion_request)(headers, payload)
        else:
            # Fallback: manual retry loop (same logic, no tenacity)
            for attempt in range(4):
                try:
                    return self._simple_completion_request(headers, payload)
                except _TransientAPIError:
                    if attempt >= 3:
                        raise
                    wait = min(2 ** (attempt + 1), 10)
                    logger.warning("simple_completion retry %d/%d, waiting %ds", attempt + 1, 3, wait)
                    time.sleep(wait)

    def should_search(self, message_content, conversation_context):
        """Determine if web search is needed - only for genuine factual queries
        that the LLM likely cannot answer from its training data alone."""

        message_lower = message_content.lower().strip()

        # NEGATIVE filters first - skip search for conversational/knowledge questions
        # the LLM can answer from training data
        no_search_patterns = [
            'what is your', 'what are your', 'what is a ', 'what is an ',  # Definitions
            'what is going on', 'what is up', 'what is that', 'what is this',
            'what are you', 'who are you', 'how are you',
            'explain how', 'explain why', 'explain what', 'explain the',
            'how does', 'how do i', 'how do you', 'how can i', 'how to',
            'tell me about yourself', 'talk about yourself',
            'what do you think', 'what would you', 'what should i',
            'what did you say', 'what did i say', 'what did we',
            'do you remember', 'did you say', 'you said',
            'can you', 'could you', 'would you', 'will you',
        ]

        if any(pattern in message_lower for pattern in no_search_patterns):
            logger.debug("Search skipped: matched conversational pattern")
            return False

        # Only trigger on explicit factual query patterns that need current data
        search_triggers = [
            'current', 'latest', 'recent', 'today\'s', 'this week', 'this month', 'this year',
            'current price', 'latest news', 'recent data',
            'price of', 'cost of', 'statistics on', 'data on', 'study on',
            'fact check', 'is it true that', 'verify that', 'look up', 'search for',
            'who won', 'who is the president', 'who is the ceo',
            'what happened to', 'score of', 'result of', 'standings', 'leaderboard', 'rankings',
            'schedule', 'scheduled', 'lineup', 'roster', 'fixture', 'fixtures',
            'upcoming', 'next game', 'next match', 'next race',
            'how good is', 'how great',
            'review of', 'reviews of',
            'specs on', 'specifications',
        ]

        # Trigger only on specific factual query keywords
        if any(trigger in message_lower for trigger in search_triggers):
            return True

        # Only trigger on very specific factual question patterns
        # Avoid casual conversation like "did you see", "if you think", etc.
        specific_factual_patterns = [
            r'\bwho (is|was|won|became|got|are)\s+\w+',  # "who is X", "who won X", "who are X"
            r'\bwhat (is|was|are|happened|caused)\s+(the|a)\s+\w+',  # "what is/are the X", "what happened"
            r'\bwhen (did|was|will|is)\s+\w+\s+(happen|win|die|born|start)',  # "when did X happen"
        ]
        for pattern in specific_factual_patterns:
            if re.search(pattern, message_lower):
                return True

        # Check if this is a short clarification following a search-worthy question
        # e.g., "aberdeen in scotland" after "when did it last rain in aberdeen"
        if len(message_lower) < 40 and conversation_context:
            # Check if recent conversation contains a search-worthy question from user
            # that the bot asked for clarification on
            for msg in reversed(conversation_context[-6:]):
                msg_content = _get_text_content(msg.get('content', '')).lower()
                msg_username = msg.get('username', '').lower()

                # Skip bot messages
                if 'wompbot' in msg_username or 'womp bot' in msg_username:
                    # Check if bot asked for clarification (which Aberdeen, which version, etc.)
                    clarification_asks = [
                        'which', 'could you clarify', 'could you specify', 'do you mean',
                        'are you referring to', 'there are several', 'there are multiple',
                        'need to know which', 'need to know what'
                    ]
                    if any(phrase in msg_content for phrase in clarification_asks):
                        # Bot asked for clarification - current message is likely the answer
                        # Look for the original question before this
                        continue

                # Check if this user message was a search-worthy question
                if any(trigger in msg_content for trigger in search_triggers):
                    # Found a search-worthy question in recent history
                    # Current short message is likely a clarification, so trigger search
                    logger.info("Clarification detected - triggering search for follow-up to: '%.50s...'", msg_content)
                    return True

                # Also check for specific patterns in user messages
                for pattern in specific_factual_patterns:
                    if re.search(pattern, msg_content):
                        logger.info("Clarification detected - triggering search for follow-up to: '%.50s...'", msg_content)
                        return True

        return False
    
    def detect_needs_search_from_response(self, response_text):
        """Detect if LLM indicates it needs more information"""
        uncertainty_phrases = [
            "i'm not sure", "i don't know", "i don't have", 
            "i cannot confirm", "i'd need to", "i would need to search",
            "as of my knowledge", "i'm uncertain", "i lack information"
        ]
        
        response_lower = response_text.lower()
        return any(phrase in response_lower for phrase in uncertainty_phrases)
    
    MAX_HISTORY_CHARS = int(os.getenv('MAX_HISTORY_CHARS', '50000'))  # Increased - was 6000

    def generate_response(
        self,
        user_message,
        conversation_history,
        user_context=None,
        search_results=None,
        rag_context=None,
        retry_count=0,
        bot_user_id=None,
        user_id=None,
        username=None,
        max_tokens=None,
        personality='default',
        tools=None,
        images=None,
        base64_images=None,
    ):
        """Generate response using OpenRouter with automatic retry on empty responses

        Args:
            max_tokens: Optional override for max tokens (defaults to MAX_TOKENS_PER_REQUEST env var or 1000)
            rag_context: RAG-retrieved context (semantic matches, facts, summaries)
            personality: 'default', 'bogan', or 'concise' - determines system prompt personality
            tools: List of tool definitions for function calling (enables LLM to call tools)
            images: List of image URLs to include in the message (for vision models)
            base64_images: List of base64-encoded images (for processed GIF frames, YouTube thumbnails)
        """

        # Select appropriate system prompt based on personality
        if personality == 'bogan':
            system_prompt = self.system_prompt_bogan
        elif personality == 'concise':
            system_prompt = self.system_prompt_concise
        else:
            system_prompt = self.system_prompt_default

        try:
            messages = [{"role": "system", "content": system_prompt}]

            profile = None
            behavior = None
            if user_context:
                profile = user_context.get("profile")
                behavior = user_context.get("behavior")

            # Build comprehensive user context if available
            if profile and behavior:
                username = profile.get("username") or profile.get("user_id", "Unknown user")
                context_note = f"\n\n## HISTORICAL USER CONTEXT for {username}:\n"
                context_note += "Use this to understand their communication style, personality, and typical behavior.\n\n"

                # Communication patterns
                context_note += f"**Communication Style:**\n"
                if behavior.get('conversation_style'):
                    context_note += f"- Style: {behavior.get('conversation_style')}\n"
                if behavior.get('tone_analysis'):
                    context_note += f"- Typical Tone: {behavior.get('tone_analysis')}\n"
                if behavior.get('profanity_score') is not None:
                    context_note += f"- Profanity level: {behavior.get('profanity_score', 0)}/10\n"

                # Honesty and behavior patterns
                if behavior.get('honesty_patterns'):
                    context_note += f"\n**Behavioral Patterns:**\n"
                    context_note += f"- {behavior.get('honesty_patterns')}\n"

                # Activity level
                if behavior.get('message_count'):
                    context_note += f"\n**Activity:**\n"
                    context_note += f"- Message count in recent period: {behavior.get('message_count')}\n"

                # Analysis period context
                if behavior.get('analysis_period_start') and behavior.get('analysis_period_end'):
                    context_note += f"- Analysis period: {behavior.get('analysis_period_start')} to {behavior.get('analysis_period_end')}\n"

                messages[0]["content"] += context_note

            # Add RAG-retrieved context (semantic search, facts, summaries)
            if rag_context:
                rag_note = "\n\n## RELEVANT HISTORICAL CONTEXT (RAG):\n"

                # User facts (compact knowledge)
                if rag_context.get('user_facts'):
                    rag_note += "**Known Facts About User:**\n"
                    for fact in rag_context['user_facts'][:5]:  # Top 5 facts
                        confidence = fact.get('confidence', 0.8)
                        rag_note += f"- {fact['fact']} (confidence: {confidence:.0%})\n"
                    rag_note += "\n"

                # Recent conversation summary
                if rag_context.get('recent_summary'):
                    rag_note += f"**Recent Conversation Summary:**\n{rag_context['recent_summary']}\n\n"

                # Semantically relevant past messages
                if rag_context.get('semantic_matches'):
                    rag_note += "**Relevant Past Conversations:**\n"
                    for match in rag_context['semantic_matches'][:3]:  # Top 3 matches
                        timestamp = match['timestamp'].strftime('%Y-%m-%d')
                        similarity = match.get('similarity', 0)
                        rag_note += f"- [{timestamp}, {similarity:.0%} relevant] {match['username']}: {match['content'][:100]}...\n"

                messages[0]["content"] += rag_note

            # Add conversation history with optional compression
            history_window = int(os.getenv('CONTEXT_WINDOW_MESSAGES', '50'))  # Increased from 6 due to compression
            recent_messages = conversation_history[-history_window:]

            if self.compressor.is_enabled() and len(recent_messages) >= 10:
                # Use compression for longer conversations
                compressed_history = self.compressor.compress_history(
                    recent_messages,
                    keep_recent=8,  # Keep last 8 messages verbatim for better context
                    bot_user_id=bot_user_id  # Pass bot ID to identify bot messages
                )
                # Add as a single user message block with clear instruction
                history_intro = """[CONVERSATION HISTORY - READ CAREFULLY]
Messages marked [YOU/WompBot] are YOUR previous responses - things YOU said.
Messages marked [Username] are what USERS said to you.
Use this history to maintain conversation continuity and remember what was discussed.

"""
                messages.append({"role": "user", "content": f"{history_intro}{compressed_history}"})
            else:
                # Fallback to standard message-by-message format for short conversations
                # This preserves proper assistant/user role assignments
                if recent_messages:
                    # Add header explaining the history format
                    messages.append({"role": "user", "content": "[CONVERSATION HISTORY - The following messages show the recent conversation. Your previous responses appear as 'assistant' messages.]"})

                for msg in recent_messages:
                    if not msg.get("content"):
                        continue

                    role = "user"
                    msg_user_id = msg.get("user_id")
                    if bot_user_id is not None and msg_user_id == bot_user_id:
                        role = "assistant"

                    if role == "assistant":
                        content = msg["content"]
                    else:
                        display_name = msg.get("username", "User")
                        content = f"{display_name}: {msg['content']}"
                    messages.append({"role": role, "content": content})

            # Add search results to user message with conversational framing
            if search_results:
                user_message_with_context = f"""[LATEST MESSAGE - respond to this, but consider the conversation history above]
{user_message}

[Web search results - use naturally in your response:]
{search_results}"""
            else:
                # Frame the message to remind LLM to consider full context
                user_message_with_context = f"[LATEST MESSAGE - respond to this, but consider the conversation history above]\n{user_message}"

            # Build user message content - use array format if images are included
            has_images = (images and len(images) > 0) or (base64_images and len(base64_images) > 0)

            if has_images:
                # Vision model format: array of content objects
                content_parts = [{"type": "text", "text": user_message_with_context}]

                # Add image URLs (detail:low reduces token cost from ~thousands to ~85 tokens per image)
                if images:
                    for img_url in images:
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {"url": img_url, "detail": "low"}
                        })

                # Add base64-encoded images (GIF frames, YouTube thumbnails, etc.)
                if base64_images:
                    for b64_img in base64_images:
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}", "detail": "low"}
                        })

                messages.append({"role": "user", "content": content_parts})
                url_count = len(images) if images else 0
                b64_count = len(base64_images) if base64_images else 0
                logger.info("Including %d image URL(s) and %d processed frame(s) in message", url_count, b64_count)
            else:
                messages.append({"role": "user", "content": user_message_with_context})

            # Enforce context token limits to prevent excessive usage
            max_context_tokens = int(os.getenv('MAX_CONTEXT_TOKENS', '4000'))

            # Helper to get content length (handles both string and array content)
            def get_content_len(content):
                if isinstance(content, str):
                    return len(content)
                elif isinstance(content, list):
                    # For array content, sum text parts only (images counted separately)
                    return sum(len(part.get("text", "")) for part in content if part.get("type") == "text")
                return 0

            # Estimate tokens using tiktoken if available, else ~1 token per 4 chars
            # Add ~170 tokens per image (OpenAI low-detail default)
            image_token_estimate = (len(images or []) + len(base64_images or [])) * 170

            if _HAS_TIKTOKEN:
                # Pre-compute per-message token counts to avoid re-encoding entire array in loop
                msg_token_counts = []
                for entry in messages:
                    text = _get_text_content(entry["content"])
                    msg_token_counts.append(len(_tiktoken_encoding.encode(text)) if text else 0)
                estimated_tokens = sum(msg_token_counts) + image_token_estimate
            else:
                msg_token_counts = [get_content_len(entry["content"]) // 4 for entry in messages]
                estimated_tokens = sum(msg_token_counts) + image_token_estimate

            total_chars = sum(get_content_len(entry["content"]) for entry in messages)

            # Truncate old messages if we exceed token limit
            # Use pre-computed per-message counts — subtract instead of re-encoding
            messages_removed = 0
            while estimated_tokens > max_context_tokens and len(messages) > 3:
                removed_msg = messages.pop(1)  # Remove oldest message after system prompt
                removed_tokens = msg_token_counts.pop(1)
                removed_chars = get_content_len(removed_msg["content"])
                estimated_tokens -= removed_tokens
                total_chars -= removed_chars
                messages_removed += 1

            if messages_removed > 0:
                logger.warning("Context truncated: removed %d old messages (now ~%d tokens)", messages_removed, estimated_tokens)
                # Insert truncation notice and its token count to keep arrays in sync
                truncation_note = f"[Note: {messages_removed} earlier messages were omitted for brevity. The conversation started before the history shown below.]"
                messages.insert(1, {"role": "user", "content": truncation_note})
                truncation_tokens = len(_tiktoken_encoding.encode(truncation_note)) if _HAS_TIKTOKEN else len(truncation_note) // 4
                msg_token_counts.insert(1, truncation_tokens)
                estimated_tokens += truncation_tokens

            # Also enforce character limit as fallback (using same delta approach)
            while total_chars > self.MAX_HISTORY_CHARS and len(messages) > 3:
                removed = messages.pop(1)
                removed_chars = get_content_len(removed["content"])
                total_chars -= removed_chars
                if len(msg_token_counts) > 1:
                    removed_tokens = msg_token_counts.pop(1)
                    estimated_tokens -= removed_tokens

            retry_text = f" (retry {retry_count + 1}/3)" if retry_count > 0 else ""
            logger.info("Sending to %s%s", self.model, retry_text)
            logger.info("Messages in context: %d", len(messages))
            logger.info("Estimated tokens: ~%d", estimated_tokens)
            # Debug: Log last few messages to verify history is included
            if len(messages) > 1:
                logger.debug("Recent context messages:")
                for i, msg in enumerate(messages[-4:]):  # Show last 4 messages
                    role = msg['role']
                    content_text = _get_text_content(msg['content'])
                    content_preview = content_text[:80].replace('\n', ' ') if content_text else "[image]"
                    logger.debug("[%d] %s: %s...", i, role, content_preview)

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Use provided max_tokens or fall back to environment variable
            if max_tokens is None:
                max_tokens = int(os.getenv('MAX_TOKENS_PER_REQUEST', '1000'))

            # Use vision model for image analysis (text-only models can't see images)
            model_to_use = self.vision_model if has_images else self.model
            if has_images and model_to_use != self.model:
                logger.info("Switching to vision model: %s", model_to_use)

            payload = {
                "model": model_to_use,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }

            # Add tools if provided (for function calling)
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"  # Let LLM decide when to use tools

            # Make API request with transient error handling (429, 502, 503)
            max_transient_retries = 3
            transient_retry = 0
            response = None

            while transient_retry <= max_transient_retries:
                response = self.session.post(self.base_url, headers=headers, json=payload, timeout=(5, 55))

                # Handle transient errors (429 rate limit, 502/503 gateway errors)
                if response.status_code in (429, 502, 503):
                    transient_retry += 1
                    if transient_retry > max_transient_retries:
                        logger.error("API returned %d after %d retries", response.status_code, max_transient_retries)
                        raise requests.HTTPError(f"API error {response.status_code} after {max_transient_retries} retries", response=response)

                    # Check for Retry-After header (primarily for 429)
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            wait_time = int(retry_after)
                        except ValueError:
                            wait_time = 5 * transient_retry  # Exponential backoff
                    else:
                        # Exponential backoff: 2, 4, 8 seconds
                        wait_time = 2 ** transient_retry

                    logger.warning("API returned %d. Waiting %ds (attempt %d/%d)", response.status_code, wait_time, transient_retry, max_transient_retries)
                    time.sleep(wait_time)
                    continue

                # Not a transient error, break out of retry loop
                break

            try:
                response.raise_for_status()
            except requests.HTTPError as http_err:
                # Log full error server-side only — never expose to users
                logger.error("LLM HTTP error %d (response logged at debug level)", response.status_code)
                logger.debug("LLM error body: %s", response.text[:500] if hasattr(response, "text") else "no body")
                raise http_err

            result = response.json()
            message = result["choices"][0]["message"]
            response_text = message.get("content", "")

            # Check if LLM wants to call a tool
            tool_calls = message.get("tool_calls")
            if tool_calls:
                logger.info("LLM requested %d tool call(s)", len(tool_calls))
                # Return tool calls for execution
                return {
                    "type": "tool_calls",
                    "tool_calls": tool_calls,
                    "response_text": response_text  # May be empty if only tool calls
                }

            # Extract token usage for cost tracking
            usage = result.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            logger.info("LLM response length: %d chars (tokens: %d in / %d out)", len(response_text), input_tokens, output_tokens)

            # Record costs in background thread (don't block response)
            if self.cost_tracker and input_tokens > 0:
                try:
                    threading.Thread(
                        target=self.cost_tracker.record_costs_sync,
                        args=(model_to_use, input_tokens, output_tokens, 'chat', user_id, username),
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.warning("Error tracking costs: %s", e)

            if not response_text or len(response_text.strip()) == 0:
                logger.warning("Empty response from LLM. Full result: %s", result)
                if retry_count < 2:
                    logger.info("Retrying in 0.5 seconds...")
                    time.sleep(0.5)  # Reduced from 2s — just enough to avoid hammering
                    return self.generate_response(
                        user_message,
                        conversation_history,
                        user_context,
                        search_results,
                        rag_context,
                        retry_count + 1,
                        bot_user_id=bot_user_id,
                        user_id=user_id,
                        username=username,
                        max_tokens=max_tokens,
                        personality=personality,
                        tools=tools,
                        images=images,
                        base64_images=base64_images,
                    )
                else:
                    logger.error("Failed after %d attempts", retry_count + 1)
                    return None

            return response_text
        except Exception as e:
            logger.error("LLM error: %s: %s", type(e).__name__, e)
            if retry_count < 2:
                logger.info("Retrying in 2 seconds due to error...")
                time.sleep(2)
                return self.generate_response(
                    user_message,
                    conversation_history,
                    user_context,
                    search_results,
                    rag_context,
                    retry_count + 1,
                    bot_user_id=bot_user_id,
                    user_id=user_id,
                    username=username,
                    max_tokens=max_tokens,
                    personality=personality,
                    tools=tools,
                    images=images,
                    base64_images=base64_images,
                )
            return None
    
    def analyze_user_behavior(self, messages):
        """Analyze user behavior patterns from message history"""
        if not messages:
            return None
        
        try:
            # Combine messages into analysis prompt
            message_text = "\n".join([f"- {msg['content']}" for msg in messages[:50]])
            
            analysis_prompt = f"""Analyze this user's communication patterns based on their recent messages:

{message_text}

Provide a structured analysis:
1. Profanity Score (0-10): How often do they swear or use crude language?
2. Tone Analysis: Describe their conversational tone (sarcastic, serious, playful, etc.)
3. Honesty Patterns: Do they tend to exaggerate, gaslight, or present facts objectively?
4. Conversation Style: How do they typically communicate?

Be objective and base your analysis only on observable patterns."""

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are an objective analyst evaluating communication patterns."},
                    {"role": "user", "content": analysis_prompt}
                ],
                "max_tokens": 500,
                "temperature": 0.3
            }
            
            response = self.session.post(self.base_url, headers=headers, json=payload, timeout=(5, 55))
            response.raise_for_status()
            
            result = response.json()
            analysis_text = result['choices'][0]['message']['content']
            
            # Parse response into structured format
            return {
                'message_count': len(messages),
                'profanity_score': self._extract_score(analysis_text),
                'tone_analysis': self._extract_section(analysis_text, 'tone'),
                'honesty_patterns': self._extract_section(analysis_text, 'honesty'),
                'conversation_style': self._extract_section(analysis_text, 'style')
            }
        except Exception as e:
            logger.error("Behavior analysis error: %s", e)
            return None
    
    def _extract_score(self, text):
        """Extract profanity score from analysis"""
        match = re.search(r'(\d+)/10', text)
        return int(match.group(1)) if match else 0
    
    def _extract_section(self, text, section_name):
        """Extract specific section from analysis"""
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if section_name.lower() in line.lower():
                # Return the next line or current line content
                if i + 1 < len(lines):
                    return lines[i + 1].strip()
                return line.split(':', 1)[-1].strip()
        return "No analysis available"
    
    def classify_questions(self, messages, batch_size=100):
        """Classify which messages are questions using LLM
        
        Returns dict of {user_id: {username, question_count, total_messages}}
        """
        if not messages:
            return {}
        
        try:
            # Group messages by user
            user_messages = {}
            for msg in messages:
                user_id = msg['user_id']
                if user_id not in user_messages:
                    user_messages[user_id] = {
                        'username': msg['username'],
                        'messages': []
                    }
                user_messages[user_id]['messages'].append(msg['content'])
            
            results = {}
            
            # Process each user's messages in batches
            for user_id, data in user_messages.items():
                username = data['username']
                msgs = data['messages'][:batch_size]  # Limit to prevent token overflow
                
                # Create batch analysis prompt
                message_list = "\n".join([f"{i+1}. {msg[:200]}" for i, msg in enumerate(msgs)])
                
                prompt = f"""Analyze these messages and identify which ones are questions (seeking information, clarification, or opinions).

Questions can be:
- Direct questions with or without "?" (What do you think, Why did this happen)
- Requests for information (Tell me about X, I wonder if Y)
- Seeking opinions/clarification (You think so, Really)

NOT questions:
- Statements (That's cool, I agree)
- Commands (Do this, Stop that)
- Rhetorical questions used as statements

Messages:
{message_list}

Respond with ONLY comma-separated numbers of messages that are questions. Example: 1,3,7,12
If no questions, respond with: NONE"""

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are an expert at identifying questions in natural language. Be precise."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 200,
                    "temperature": 0.1
                }
                
                response = self.session.post(self.base_url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                
                result_text = response.json()['choices'][0]['message']['content'].strip()
                
                # Parse question indices
                question_count = 0
                if result_text != "NONE":
                    question_indices = [int(x.strip()) for x in result_text.split(',') if x.strip().isdigit()]
                    question_count = len(question_indices)
                
                results[user_id] = {
                    'username': username,
                    'question_count': question_count,
                    'total_messages': len(msgs),
                    'question_percentage': (question_count / len(msgs) * 100) if msgs else 0
                }
            
            return results
        
        except Exception as e:
            logger.error("Question classification error: %s", e)
            return {}
