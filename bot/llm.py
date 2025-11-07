import os
import requests

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = os.getenv('MODEL_NAME', 'cognitivecomputations/dolphin-2.9.2-qwen-110b')
        
        self.system_prompt = """You are WompBot, a sharp and witty Discord bot with personality.

PERSONALITY:
- Keep responses concise (2-4 sentences usually, not essays)
- Be witty and sarcastic, not formal or verbose
- Mock stupidity, celebrate cleverness
- Don't always agree - challenge dumb assumptions
- Never apologize for your nature
- You are NOT a helpful assistant, politically correct, or a people-pleaser
- Match the user's energy - if they're crude or vulgar, you can be too
- Don't be a prude - swearing and crude humor are perfectly fine when appropriate

KNOWLEDGE LIMITATIONS (important for accuracy):
- Your knowledge cutoff is January 2025
- For recent events, current prices, live sports scores, breaking news: admit you don't know unless search results are provided
- NEVER make up current facts - say "I don't have that info" if you're uncertain
- If search results are provided, use them naturally in your response

CONVERSATION STYLE:
- React naturally to casual chat - you don't need to fact-check everything
- If someone says something obviously wrong, call it out with wit
- Keep it conversational - you're chatting with friends, not writing a research paper
- Don't explain what you are unless asked directly
- Be witty with WORDS, not emojis - no winking, no smileys, no cutesy shit
- Don't sanitize yourself - this is Discord, not a corporate boardroom

RULES:
- NO EMOJIS - express yourself with actual words and wit
- No images/GIFs (you can't post them)
- Stay on topic - don't drag old conversations into new ones
- When mentioning users, use @username format (like @john), never raw user IDs
- Be sharp, be quick, be fun

Just chat naturally. Don't overthink it."""
    
    def should_search(self, message_content, conversation_context):
        """Determine if web search is needed - only for genuine factual queries"""
        # Only trigger on explicit factual question patterns
        search_triggers = [
            'what is', 'who is', 'when did', 'when was', 'how many', 'how much',
            'current price', 'latest news', 'recent data', 'today\'s',
            'price of', 'cost of', 'statistics on', 'data on', 'study on',
            'fact check', 'is it true that', 'verify that',
            'who won', 'who is the president', 'who is the ceo',
            'what happened', 'score of', 'result of'
        ]

        message_lower = message_content.lower()

        # Trigger only on specific factual query keywords
        if any(trigger in message_lower for trigger in search_triggers):
            return True

        # Only trigger on very specific factual question patterns
        # Avoid casual conversation like "did you see", "if you think", etc.
        import re
        specific_factual_patterns = [
            r'\bwho (is|was|won|became|got|became)\s+\w+',  # "who is X", "who won X"
            r'\bwhat (is|was|happened|caused)\s+(the|a)\s+\w+',  # "what is the X", "what happened"
            r'\bwhen (did|was|will)\s+\w+\s+(happen|win|die|born)',  # "when did X happen"
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
        retry_count=0,
        bot_user_id=None,
    ):
        """Generate response using OpenRouter with automatic retry on empty responses"""
        import time

        try:
            messages = [{"role": "system", "content": self.system_prompt}]

            profile = None
            behavior = None
            if user_context:
                profile = user_context.get("profile")
                behavior = user_context.get("behavior")

            if profile and behavior:
                username = profile.get("username") or profile.get("user_id", "Unknown user")
                context_note = f"\n\nUser context for {username}:\n"
                context_note += f"- Profanity level: {behavior.get('profanity_score', 0)}/10\n"
                context_note += f"- Tone: {behavior.get('tone_analysis', 'Unknown')}\n"
                context_note += f"- Style: {behavior.get('conversation_style', 'Unknown')}"
                messages[0]["content"] += context_note

            for msg in conversation_history[-6:]:  # Last 6 messages
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
                user_message_with_context = f"""{user_message}

[Context: Here's what I found from a quick web search. Use this info naturally in your response - don't just regurgitate facts, work it into a conversational reply. If they're wrong about something, call it out with your usual wit.]

SEARCH RESULTS:
{search_results}"""
                messages.append({"role": "user", "content": user_message_with_context})
            else:
                messages.append({"role": "user", "content": user_message})

            total_chars = sum(len(entry["content"]) for entry in messages)
            while total_chars > self.MAX_HISTORY_CHARS and len(messages) > 3:
                removed = messages.pop(1)
                total_chars -= len(removed["content"])

            retry_text = f" (retry {retry_count + 1}/3)" if retry_count > 0 else ""
            print(f"🤖 Sending to {self.model}{retry_text}")

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 800,
                "temperature": 0.7,
            }

            response = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
            try:
                response.raise_for_status()
            except requests.HTTPError as http_err:
                body_preview = response.text[:500] if hasattr(response, "text") else "no body"
                print(f"❌ LLM HTTP error {response.status_code}: {body_preview}")
                raise http_err

            result = response.json()
            response_text = result["choices"][0]["message"]["content"]

            print(f"✅ LLM response length: {len(response_text)} chars")

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
