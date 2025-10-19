import discord
from discord.ext import commands
import json
from datetime import datetime
from features.claim_detector import ClaimDetector

class ClaimsTracker:
    """Tracks user claims and quotes"""

    def __init__(self, db, llm):
        self.db = db
        self.llm = llm
        self.wompie_user_id = None  # Will be set from main.py
        self.claim_detector = ClaimDetector()  # Fast pre-filter

    async def analyze_message_for_claim(self, message):
        """Analyze if message contains a trackable claim"""
        try:
            # Skip very short messages
            if len(message.content) < 20:
                return None

            # STAGE 1: Fast keyword pre-filter (FREE, INSTANT)
            pre_filter_result = self.claim_detector.is_likely_claim(message.content)

            if not pre_filter_result['is_likely']:
                # Not a claim - skip LLM analysis (SAVES MONEY!)
                print(f"⏭️  Skipped (not claim-like): {message.content[:50]}... | {pre_filter_result['reasoning']}")
                return None

            # STAGE 2: LLM verification (PAID, only for likely claims)
            print(f"🔍 LLM analyzing likely claim: {message.content[:50]}... | Confidence: {pre_filter_result['confidence']:.2f}")
            
            prompt = f"""Analyze this message and determine if it contains a trackable claim.

A trackable claim is:
- A factual assertion that can be verified (e.g., "Trump always spits when talking")
- A strong prediction (e.g., "Bitcoin will hit 100k by next year")
- A guarantee or absolute statement (e.g., "I will never eat pineapple pizza")
- A bold opinion stated as fact (e.g., "EVs are always worse for the environment")

NOT trackable:
- Casual conversation (e.g., "I don't always agree with you")
- Questions
- Obvious jokes or sarcasm
- Vague statements without specifics
- Simple preferences (e.g., "I like pizza")

Message: "{message.content}"

Respond in JSON format:
{{
    "is_trackable": true/false,
    "claim_text": "exact claim if trackable, otherwise null",
    "claim_type": "prediction/fact/opinion/guarantee or null",
    "confidence_level": "certain/probable/uncertain or null",
    "reasoning": "brief explanation"
}}"""

            headers = {
                "Authorization": f"Bearer {self.llm.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.llm.model,
                "messages": [
                    {"role": "system", "content": "You are an expert at identifying trackable claims. Be selective - only flag substantial claims worth tracking."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 300,
                "temperature": 0.2
            }
            
            import requests
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result_text = response.json()['choices'][0]['message']['content'].strip()
            print(f"🤖 LLM Response: {result_text[:200]}")
            
            # Parse JSON response
            # Try to extract JSON even if there's extra text
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                if result.get('is_trackable'):
                    print(f"✅ Trackable claim detected: {result['claim_text']}")
                    return result
                else:
                    print(f"❌ Not trackable: {result.get('reasoning', 'No reason given')}")
            
            return None
            
        except Exception as e:
            print(f"❌ Error analyzing claim: {e}")
            return None
    
    async def store_claim(self, message, claim_data):
        """Store a tracked claim in database"""
        try:
            # Get surrounding context (3 messages before)
            context_messages = self.db.get_recent_messages(message.channel.id, limit=4)
            context = "\n".join([f"{m['username']}: {m['content']}" for m in context_messages[:-1]])
            
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO claims 
                    (user_id, username, message_id, channel_id, channel_name, 
                     claim_text, claim_type, confidence_level, context, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (message_id) DO NOTHING
                    RETURNING id
                """, (
                    message.author.id,
                    str(message.author),
                    message.id,
                    message.channel.id,
                    message.channel.name,
                    claim_data['claim_text'],
                    claim_data['claim_type'],
                    claim_data['confidence_level'],
                    context,
                    message.created_at
                ))
                
                result = cur.fetchone()
                if result:
                    claim_id = result[0]
                    print(f"📝 Tracked claim #{claim_id} from {message.author}")
                    return claim_id
            
            return None
            
        except Exception as e:
            print(f"❌ Error storing claim: {e}")
            return None
    
    async def handle_claim_edit(self, before, after):
        """Track when a tracked claim is edited"""
        try:
            with self.db.conn.cursor() as cur:
                # Check if message has a tracked claim
                cur.execute("SELECT id, original_text, edit_history FROM claims WHERE message_id = %s", (before.id,))
                result = cur.fetchone()
                
                if result:
                    claim_id, original_text, edit_history = result
                    
                    # Initialize edit history
                    if not edit_history:
                        edit_history = []
                        original_text = before.content
                    
                    # Add edit to history
                    edit_history.append({
                        'text': after.content,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    cur.execute("""
                        UPDATE claims 
                        SET is_edited = TRUE,
                            original_text = %s,
                            edit_history = %s,
                            claim_text = %s
                        WHERE id = %s
                    """, (original_text, json.dumps(edit_history), after.content, claim_id))
                    
                    print(f"✏️  Claim #{claim_id} edited - history preserved")
        
        except Exception as e:
            print(f"❌ Error tracking claim edit: {e}")
    
    async def handle_claim_deletion(self, message):
        """Track when a tracked claim is deleted"""
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    UPDATE claims 
                    SET is_deleted = TRUE,
                        deleted_at = %s,
                        deleted_text = claim_text
                    WHERE message_id = %s
                """, (datetime.now(), message.id))
                
                if cur.rowcount > 0:
                    print(f"🗑️  Claim from message {message.id} marked as deleted")
        
        except Exception as e:
            print(f"❌ Error tracking claim deletion: {e}")
    
    async def get_user_claims(self, user_id, include_deleted=False):
        """Get all claims by a user"""
        try:
            with self.db.conn.cursor() as cur:
                query = """
                    SELECT id, claim_text, claim_type, confidence_level, 
                           timestamp, verification_status, is_edited, is_deleted,
                           message_id, channel_id
                    FROM claims 
                    WHERE user_id = %s
                """
                if not include_deleted:
                    query += " AND is_deleted = FALSE"
                query += " ORDER BY timestamp DESC"
                
                cur.execute(query, (user_id,))
                
                columns = [desc[0] for desc in cur.description]
                results = cur.fetchall()
                
                return [dict(zip(columns, row)) for row in results]
        
        except Exception as e:
            print(f"❌ Error fetching user claims: {e}")
            return []
    
    async def check_contradiction(self, new_claim, user_id):
        """Check if new claim contradicts past claims"""
        try:
            # Get user's past claims
            past_claims = await self.get_user_claims(user_id)
            
            if len(past_claims) < 2:
                return None
            
            # Build contradiction check prompt
            past_claims_text = "\n".join([
                f"{i+1}. [{c['timestamp'].strftime('%Y-%m-%d')}] {c['claim_text']}"
                for i, c in enumerate(past_claims[:10])  # Check last 10 claims
            ])
            
            prompt = f"""Check if this new claim contradicts any past claims:

New claim: "{new_claim['claim_text']}"

Past claims:
{past_claims_text}

If there's a contradiction, respond with JSON:
{{
    "contradicts": true,
    "claim_number": X,
    "explanation": "brief explanation of contradiction"
}}

If no contradiction, respond with:
{{
    "contradicts": false
}}"""

            headers = {
                "Authorization": f"Bearer {self.llm.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.llm.model,
                "messages": [
                    {"role": "system", "content": "You identify contradictions in claims. Be precise."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 200,
                "temperature": 0.1
            }
            
            import requests
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result_text = response.json()['choices'][0]['message']['content'].strip()
            
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                if result.get('contradicts'):
                    return {
                        'contradicted_claim': past_claims[result['claim_number'] - 1],
                        'explanation': result['explanation']
                    }
            
            return None
            
        except Exception as e:
            print(f"❌ Error checking contradictions: {e}")
            return None
    
    async def store_quote(self, message, added_by_user):
        """Store a quote when someone reacts with cloud emoji"""
        try:
            # Get context (2 messages before and after)
            all_messages = self.db.get_recent_messages(message.channel.id, limit=10)
            
            # Find the quoted message in context
            quote_index = next((i for i, m in enumerate(all_messages) if m.get('message_id') == message.id), None)
            
            context = ""
            if quote_index is not None:
                start = max(0, quote_index - 2)
                end = min(len(all_messages), quote_index + 3)
                context_messages = all_messages[start:end]
                context = "\n".join([f"{m['username']}: {m['content']}" for m in context_messages])
            
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO quotes 
                    (user_id, username, message_id, channel_id, channel_name,
                     quote_text, context, timestamp, added_by_user_id, added_by_username)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (message_id) 
                    DO UPDATE SET reaction_count = quotes.reaction_count + 1
                    RETURNING id
                """, (
                    message.author.id,
                    str(message.author),
                    message.id,
                    message.channel.id,
                    message.channel.name,
                    message.content,
                    context,
                    message.created_at,
                    added_by_user.id,
                    str(added_by_user)
                ))
                
                result = cur.fetchone()
                if result:
                    quote_id = result[0]
                    print(f"☁️  Quote #{quote_id} saved from {message.author}")
                    return quote_id
            
            return None
            
        except Exception as e:
            print(f"❌ Error storing quote: {e}")
            return None
    
    def get_user_quotes(self, user_id, limit=None):
        """Get all quotes from a user"""
        try:
            with self.db.conn.cursor() as cur:
                query = """
                    SELECT id, quote_text, timestamp, reaction_count, 
                           channel_name, message_id, context
                    FROM quotes 
                    WHERE user_id = %s
                    ORDER BY timestamp DESC
                """
                if limit:
                    query += f" LIMIT {limit}"
                
                cur.execute(query, (user_id,))
                
                columns = [desc[0] for desc in cur.description]
                results = cur.fetchall()
                
                return [dict(zip(columns, row)) for row in results]
        
        except Exception as e:
            print(f"❌ Error fetching quotes: {e}")
            return []
