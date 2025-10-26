import os
import requests

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = os.getenv('MODEL_NAME', 'cognitivecomputations/dolphin-2.9.2-qwen-110b')
        
        self.system_prompt = """You are WompBot, a helpful Discord assistant.

RULES:
- NEVER explain what you are or your purpose unless directly asked "who are you" or "what are you"
- If asked for images/GIFs/memes, say: "I can't post images or GIFs"
- Don't mix previous topics into new questions - answer what was asked
- Be direct, clear, and concise
- Use a professional but friendly tone

Just answer the question. Don't explain yourself."""
    
    def should_search(self, message_content, conversation_context):
        """Determine if web search is needed"""
        # Keywords that suggest factual questions
        search_triggers = [
            'what is', 'who is', 'when did', 'how many', 'current',
            'latest', 'recent', 'today', 'price of', 'cost of',
            'statistics', 'data', 'study', 'research', 'source',
            'fact check', 'is it true', 'did', 'verify'
        ]
        
        message_lower = message_content.lower()
        return any(trigger in message_lower for trigger in search_triggers)
    
    def detect_needs_search_from_response(self, response_text):
        """Detect if LLM indicates it needs more information"""
        uncertainty_phrases = [
            "i'm not sure", "i don't know", "i don't have", 
            "i cannot confirm", "i'd need to", "i would need to search",
            "as of my knowledge", "i'm uncertain", "i lack information"
        ]
        
        response_lower = response_text.lower()
        return any(phrase in response_lower for phrase in uncertainty_phrases)
    
    def generate_response(self, user_message, conversation_history, user_context=None, search_results=None, retry_count=0):
        """Generate response using OpenRouter with automatic retry on empty responses"""
        import time

        try:
            messages = [{"role": "system", "content": self.system_prompt}]

            # Add user context if available
            if user_context and user_context.get('behavior'):
                behavior = user_context['behavior']
                context_note = f"\n\nUser context for {user_context['profile']['username']}:\n"
                context_note += f"- Profanity level: {behavior.get('profanity_score', 0)}/10\n"
                context_note += f"- Tone: {behavior.get('tone_analysis', 'Unknown')}\n"
                context_note += f"- Style: {behavior.get('conversation_style', 'Unknown')}"
                messages[0]["content"] += context_note

            # Add conversation history
            for msg in conversation_history[-6:]:  # Last 6 messages
                role = "assistant" if msg.get('username', '').startswith('Bot') else "user"
                # Only add username prefix for user messages, not assistant messages
                if role == "assistant":
                    content = msg['content']
                else:
                    content = f"{msg['username']}: {msg['content']}"
                messages.append({"role": role, "content": content})

            # Add search results if available
            if search_results:
                search_context = "\n\nWeb Search Results:\n" + search_results
                messages.append({"role": "system", "content": search_context})

            # Add current user message
            messages.append({"role": "user", "content": user_message})

            retry_text = f" (retry {retry_count + 1}/3)" if retry_count > 0 else ""
            print(f"🤖 Sending to {self.model}{retry_text}")

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 800,
                "temperature": 0.7
            }

            response = requests.post(self.base_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()

            result = response.json()
            response_text = result['choices'][0]['message']['content']

            print(f"✅ LLM response length: {len(response_text)} chars")

            # Check for empty response and retry
            if not response_text or len(response_text.strip()) == 0:
                print(f"⚠️  WARNING: Empty response from LLM. Full result: {result}")

                # Retry up to 3 times with 2 second delay
                if retry_count < 2:
                    print(f"🔄 Retrying in 2 seconds...")
                    time.sleep(2)
                    return self.generate_response(user_message, conversation_history, user_context, search_results, retry_count + 1)
                else:
                    print(f"❌ Failed after {retry_count + 1} attempts")
                    return None

            return response_text
        except Exception as e:
            print(f"❌ LLM error: {e}")
            # Retry on exceptions too (network issues, timeouts, etc.)
            if retry_count < 2:
                print(f"🔄 Retrying in 2 seconds due to error...")
                time.sleep(2)
                return self.generate_response(user_message, conversation_history, user_context, search_results, retry_count + 1)
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