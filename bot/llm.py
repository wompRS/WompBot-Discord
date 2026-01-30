import os
import requests
from compression import ConversationCompressor

class LLMClient:
    def __init__(self, cost_tracker=None):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = os.getenv('MODEL_NAME', 'cognitivecomputations/dolphin-2.9.2-qwen-110b')
        self.cost_tracker = cost_tracker

        # Initialize conversation compressor for token reduction
        self.compressor = ConversationCompressor()

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
            personality: 'default', 'bogan', or 'concise'

        Returns:
            System prompt text
        """
        # Determine which file to load
        if personality == 'bogan':
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
                        print(f"✅ Loaded {personality} personality prompt from {prompt_file}")
                        return prompt
            except Exception as e:
                print(f"⚠️  Error loading {personality} prompt from file: {e}")

        # Fallback to default
        print(f"📝 Using fallback prompt for {personality} personality")
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
    
    def should_search(self, message_content, conversation_context):
        """Determine if web search is needed - only for genuine factual queries"""
        # Only trigger on explicit factual question patterns
        search_triggers = [
            'what is', 'what are', 'who is', 'who are', 'when did', 'when was', 'how many', 'how much',
            'current', 'latest', 'recent', 'today\'s', 'this week', 'this month', 'this year',
            'current price', 'latest news', 'recent data',
            'price of', 'cost of', 'statistics on', 'data on', 'study on',
            'fact check', 'is it true that', 'verify that', 'look up', 'search for',
            'who won', 'who is the president', 'who is the ceo',
            'what happened', 'score of', 'result of', 'standings', 'leaderboard', 'rankings',
            'tell me about', 'talk about', 'explain', 'how good is', 'how great',
            'review of', 'reviews of', 'comparison', 'compare', 'vs',
            'specs on', 'specifications'
        ]

        message_lower = message_content.lower()

        # Trigger only on specific factual query keywords
        if any(trigger in message_lower for trigger in search_triggers):
            return True

        # Only trigger on very specific factual question patterns
        # Avoid casual conversation like "did you see", "if you think", etc.
        import re
        specific_factual_patterns = [
            r'\bwho (is|was|won|became|got|are)\s+\w+',  # "who is X", "who won X", "who are X"
            r'\bwhat (is|was|are|happened|caused)\s+(the|a)\s+\w+',  # "what is/are the X", "what happened"
            r'\bwhen (did|was|will|is)\s+\w+\s+(happen|win|die|born|start)',  # "when did X happen"
        ]
        for pattern in specific_factual_patterns:
            if re.search(pattern, message_lower):
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
    
    MAX_HISTORY_CHARS = 6000

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
    ):
        """Generate response using OpenRouter with automatic retry on empty responses

        Args:
            max_tokens: Optional override for max tokens (defaults to MAX_TOKENS_PER_REQUEST env var or 1000)
            rag_context: RAG-retrieved context (semantic matches, facts, summaries)
            personality: 'default', 'bogan', or 'concise' - determines system prompt personality
            tools: List of tool definitions for function calling (enables LLM to call tools)
        """
        import time

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

            if self.compressor.is_enabled() and len(recent_messages) >= 8:
                # Use compression for longer conversations
                compressed_history = self.compressor.compress_history(
                    recent_messages,
                    keep_recent=5,  # Keep last 5 messages verbatim for better context
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
                messages.append({"role": "user", "content": user_message_with_context})
            else:
                # Frame the message to remind LLM to consider full context
                messages.append({"role": "user", "content": f"[LATEST MESSAGE - respond to this, but consider the conversation history above]\n{user_message}"})

            # Enforce context token limits to prevent excessive usage
            max_context_tokens = int(os.getenv('MAX_CONTEXT_TOKENS', '4000'))

            # Estimate tokens (approximately 1 token per 3.5 characters)
            total_chars = sum(len(entry["content"]) for entry in messages)
            estimated_tokens = int(total_chars / 3.5)

            # Truncate old messages if we exceed token limit
            messages_removed = 0
            while estimated_tokens > max_context_tokens and len(messages) > 3:
                removed = messages.pop(1)  # Remove oldest message after system prompt
                total_chars -= len(removed["content"])
                estimated_tokens = int(total_chars / 3.5)
                messages_removed += 1

            if messages_removed > 0:
                print(f"⚠️ Context truncated: removed {messages_removed} old messages (was {estimated_tokens + messages_removed * 100} tokens, now ~{estimated_tokens})")

            # Also enforce character limit as fallback
            while total_chars > self.MAX_HISTORY_CHARS and len(messages) > 3:
                removed = messages.pop(1)
                total_chars -= len(removed["content"])
                estimated_tokens = int(total_chars / 3.5)

            retry_text = f" (retry {retry_count + 1}/3)" if retry_count > 0 else ""
            print(f"🤖 Sending to {self.model}{retry_text}")
            print(f"   📊 Messages in context: {len(messages)}")
            print(f"   📝 Estimated tokens: ~{estimated_tokens}")
            # Debug: Print last few messages to verify history is included
            if len(messages) > 1:
                print(f"   💬 Recent context messages:")
                for i, msg in enumerate(messages[-4:]):  # Show last 4 messages
                    role = msg['role']
                    content_preview = msg['content'][:80].replace('\n', ' ')
                    print(f"      [{i}] {role}: {content_preview}...")

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # Use provided max_tokens or fall back to environment variable
            if max_tokens is None:
                max_tokens = int(os.getenv('MAX_TOKENS_PER_REQUEST', '1000'))

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }

            # Add tools if provided (for function calling)
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"  # Let LLM decide when to use tools

            # Make API request with rate limit handling
            max_rate_limit_retries = 3
            rate_limit_retry = 0
            response = None

            while rate_limit_retry <= max_rate_limit_retries:
                response = requests.post(self.base_url, headers=headers, json=payload, timeout=60)

                # Handle 429 rate limiting specifically
                if response.status_code == 429:
                    rate_limit_retry += 1
                    if rate_limit_retry > max_rate_limit_retries:
                        print(f"❌ Rate limited by API after {max_rate_limit_retries} retries")
                        raise requests.HTTPError(f"Rate limited after {max_rate_limit_retries} retries", response=response)

                    # Check for Retry-After header
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            wait_time = int(retry_after)
                        except ValueError:
                            wait_time = 5 * rate_limit_retry  # Exponential backoff
                    else:
                        # Exponential backoff: 2, 4, 8 seconds
                        wait_time = 2 ** rate_limit_retry

                    print(f"⏱️ Rate limited by API. Waiting {wait_time}s (attempt {rate_limit_retry}/{max_rate_limit_retries})")
                    time.sleep(wait_time)
                    continue

                # Not rate limited, break out of retry loop
                break

            try:
                response.raise_for_status()
            except requests.HTTPError as http_err:
                body_preview = response.text[:500] if hasattr(response, "text") else "no body"
                print(f"❌ LLM HTTP error {response.status_code}: {body_preview}")
                raise http_err

            result = response.json()
            message = result["choices"][0]["message"]
            response_text = message.get("content", "")

            # Check if LLM wants to call a tool
            tool_calls = message.get("tool_calls")
            if tool_calls:
                print(f"🛠️  LLM requested {len(tool_calls)} tool call(s)")
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

            print(f"✅ LLM response length: {len(response_text)} chars (tokens: {input_tokens} in / {output_tokens} out)")

            # Record costs if cost tracker is available
            # This function is called from asyncio.to_thread(), so we're always in a worker thread
            # Use the sync version which logs costs but doesn't send Discord DM alerts
            if self.cost_tracker and input_tokens > 0:
                try:
                    self.cost_tracker.record_costs_sync(
                        self.model, input_tokens, output_tokens, 'chat', user_id, username
                    )
                except Exception as e:
                    print(f"⚠️  Error tracking costs: {e}")

            if not response_text or len(response_text.strip()) == 0:
                print(f"⚠️  WARNING: Empty response from LLM. Full result: {result}")
                if retry_count < 2:
                    print("🔄 Retrying in 2 seconds...")
                    time.sleep(2)
                    return self.generate_response(
                        user_message,
                        conversation_history,
                        user_context,
                        search_results,
                        retry_count + 1,
                        bot_user_id=bot_user_id,
                    )
                else:
                    print(f"❌ Failed after {retry_count + 1} attempts")
                    return None

            return response_text
        except Exception as e:
            print(f"❌ LLM error: {type(e).__name__}: {e}")
            if retry_count < 2:
                print("🔄 Retrying in 2 seconds due to error...")
                time.sleep(2)
                return self.generate_response(
                    user_message,
                    conversation_history,
                    user_context,
                    search_results,
                    retry_count + 1,
                    bot_user_id=bot_user_id,
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
            
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
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
            print(f"❌ Behavior analysis error: {e}")
            return None
    
    def _extract_score(self, text):
        """Extract profanity score from analysis"""
        import re
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
                
                response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
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
            print(f"❌ Question classification error: {e}")
            return {}
