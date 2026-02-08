import asyncio
import discord
from discord.ext import commands
import json
import logging
import re
from datetime import datetime
from features.claim_detector import ClaimDetector

logger = logging.getLogger(__name__)

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
                logger.debug("Skipped (not claim-like): %s... | %s", message.content[:50], pre_filter_result['reasoning'])
                return None

            # STAGE 2: LLM verification (PAID, only for likely claims)
            logger.info("LLM analyzing likely claim: %s... | Confidence: %.2f",
                        message.content[:50], pre_filter_result['confidence'])

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

            full_prompt = (
                "You are an expert at identifying trackable claims. "
                "Be selective - only flag substantial claims worth tracking.\n\n"
                + prompt
            )

            result_text = await asyncio.to_thread(
                self.llm.simple_completion,
                full_prompt,
                max_tokens=300,
                temperature=0.2,
                cost_request_type="claim_analysis"
            )

            if not result_text:
                return None

            result_text = result_text.strip()
            logger.debug("LLM Response: %s", result_text[:200])

            # Parse JSON response - extract JSON even if there's extra text
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())

                if result.get('is_trackable'):
                    logger.info("Trackable claim detected: %s", result['claim_text'])
                    return result
                else:
                    logger.debug("Not trackable: %s", result.get('reasoning', 'No reason given'))

            return None

        except Exception as e:
            logger.error("Error analyzing claim: %s", e)
            return None
    
    async def store_claim(self, message, claim_data):
        """Store a tracked claim in database"""
        try:
            # Get surrounding context (3 messages before)
            context_messages = self.db.get_recent_messages(message.channel.id, limit=4)
            context = "\n".join([f"{m['username']}: {m['content']}" for m in context_messages[:-1]])

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
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
                        logger.info("Tracked claim #%d from %s", claim_id, message.author)
                        return claim_id

            return None
            
        except Exception as e:
            logger.error("Error storing claim: %s", e)
            return None
    
    async def handle_claim_edit(self, before, after):
        """Track when a tracked claim is edited"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
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

                        logger.info("Claim #%d edited - history preserved", claim_id)
        
        except Exception as e:
            logger.error("Error tracking claim edit: %s", e)
    
    async def handle_claim_deletion(self, message):
        """Track when a tracked claim is deleted"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE claims
                        SET is_deleted = TRUE,
                            deleted_at = %s,
                            deleted_text = claim_text
                        WHERE message_id = %s
                    """, (datetime.now(), message.id))

                    if cur.rowcount > 0:
                        logger.info("Claim from message %s marked as deleted", message.id)
        
        except Exception as e:
            logger.error("Error tracking claim deletion: %s", e)
    
    async def get_user_claims(self, user_id, include_deleted=False):
        """Get all claims by a user"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
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
            logger.error("Error fetching user claims: %s", e)
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

            full_prompt = (
                "You identify contradictions in claims. Be precise.\n\n"
                + prompt
            )

            result_text = await asyncio.to_thread(
                self.llm.simple_completion,
                full_prompt,
                max_tokens=200,
                temperature=0.1,
                cost_request_type="claim_contradiction"
            )

            if not result_text:
                return None

            result_text = result_text.strip()

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
            logger.error("Error checking contradictions: %s", e)
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

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
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
                        logger.info("Quote #%d saved from %s", quote_id, message.author)
                        return quote_id

            return None
            
        except Exception as e:
            logger.error("Error storing quote: %s", e)
            return None
    
    def get_user_quotes(self, user_id, limit=None):
        """Get all quotes from a user"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT id, quote_text, timestamp, reaction_count,
                               channel_name, message_id, context
                        FROM quotes
                        WHERE user_id = %s
                        ORDER BY timestamp DESC
                    """
                    params = [user_id]
                    if limit:
                        query += " LIMIT %s"
                        params.append(limit)

                    cur.execute(query, params)

                    columns = [desc[0] for desc in cur.description]
                    results = cur.fetchall()

                    return [dict(zip(columns, row)) for row in results]
        
        except Exception as e:
            logger.error("Error fetching quotes: %s", e)
            return []
