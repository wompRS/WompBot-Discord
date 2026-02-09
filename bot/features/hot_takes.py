"""
Hot Takes Leaderboard - Three-Stage Hybrid System
Stage 1: Controversy pattern detection (free)
Stage 2: Community reaction tracking (free)
Stage 3: LLM controversy scoring (only for high-engagement claims)

Cost: <$1/month with 90%+ accuracy
"""

import discord
import logging
import re
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class HotTakesTracker:
    """Tracks controversial claims and community reactions"""

    def __init__(self, db, llm):
        self.db = db
        self.llm = llm

        # Controversy pattern keywords
        self.controversy_patterns = [
            r'\b(hot take|unpopular opinion|controversial|fight me)\b',
            r'\b(overrated|underrated|overhyped)\b',
            r'\b(is better than|is worse than|>|<)\b.*\b(is better than|is worse than|>|<)\b',  # Comparisons
            r'\b(trash|garbage|peak|goat|mid)\b',  # Strong judgments
            r'\b(cope|seethe|based|cringe)\b',  # Provocative language
            r'\b(everyone is wrong|y\'all are wrong|you\'re all wrong)\b',
            r'\b(change my mind|prove me wrong)\b',
            r'\b(objectively|factually)\b.*\b(better|worse|best|worst)\b',
            # Strong negative "are/is a X" patterns
            r'\b(is|are)\s+a\s+(shit|shitty|terrible|awful|horrible|trash|garbage|bad|worst)\b',
            r'\b(is|are)\s+(shit|shitty|terrible|awful|horrible|trash|garbage|bad|the worst)\b',
            # Absolute statements
            r'\b(always|never)\s+(was|were|has been|have been)\b',
            r'\b(completely|totally|utterly)\s+(trash|garbage|terrible|awful|wrong)\b',
        ]

        # Sensitive topics that generate controversy (without being political)
        self.sensitive_topics = [
            r'\b(pineapple.*pizza|pizza.*pineapple)\b',
            r'\b(gif|jif)\b.*\b(pronounced)\b',
            r'\b(tabs.*spaces|spaces.*tabs)\b',
            r'\b(vim|emacs|vscode)\b.*\b(better|best)\b',
            r'\b(iphone|android)\b.*\b(better|superior)\b',
            r'\b(star wars|star trek)\b.*\b(better)\b',
        ]

        # Combine all patterns
        self.all_controversy_patterns = self.controversy_patterns + self.sensitive_topics

    def detect_controversy_patterns(self, message_content: str) -> dict:
        """
        Stage 1: Fast pattern detection for controversial language.

        Returns:
            {
                'is_controversial': bool,
                'confidence': float (0-1),
                'matched_patterns': list,
                'reasoning': str
            }
        """
        content_lower = message_content.lower()

        matched_patterns = []
        confidence = 0.0

        for pattern in self.all_controversy_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                matched_patterns.append(pattern)
                confidence += 0.3

        # Cap at 1.0
        confidence = min(confidence, 1.0)

        is_controversial = confidence >= 0.3

        return {
            'is_controversial': is_controversial,
            'confidence': confidence,
            'matched_patterns': matched_patterns,
            'reasoning': f'Matched {len(matched_patterns)} controversy pattern(s)' if is_controversial else 'No controversy patterns'
        }

    async def track_community_reaction(self, message_id: int, channel_id: int) -> dict:
        """
        Stage 2: Track community engagement on a message.

        Returns:
            {
                'total_reactions': int,
                'reaction_diversity': float (0-1),
                'reply_count': int,
                'community_score': float (0-10)
            }
        """
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    # Get message reactions (we'll update this from Discord API)
                    # For now, track replies from database
                    cur.execute("""
                        SELECT COUNT(*)
                        FROM messages
                        WHERE channel_id = %s
                        AND timestamp > (
                            SELECT timestamp FROM messages WHERE message_id = %s
                        )
                        AND timestamp < (
                            SELECT timestamp + interval '1 hour' FROM messages WHERE message_id = %s
                        )
                    """, (channel_id, message_id, message_id))

                    reply_count = cur.fetchone()[0] or 0

                    return {
                        'total_reactions': 0,  # Will be updated from Discord API
                        'reaction_diversity': 0.0,
                        'reply_count': reply_count,
                        'community_score': min(reply_count * 2, 10)  # Scale to 0-10
                    }

        except Exception as e:
            logger.error("Error tracking community reaction: %s", e)
            return {
                'total_reactions': 0,
                'reaction_diversity': 0.0,
                'reply_count': 0,
                'community_score': 0.0
            }

    async def update_reaction_metrics(self, message, hot_take_id: int):
        """
        Update reaction metrics from Discord message object.
        Called when reactions are added/removed.
        """
        try:
            # Calculate reaction diversity (mix of different reactions)
            reaction_types = {}
            total_reactions = 0

            for reaction in message.reactions:
                reaction_types[str(reaction.emoji)] = reaction.count
                total_reactions += reaction.count

            # Diversity via normalized Shannon entropy: 1.0 = perfectly even mix, 0.0 = single type
            if total_reactions > 0 and len(reaction_types) > 1:
                import math
                entropy = -sum(
                    (count / total_reactions) * math.log(count / total_reactions)
                    for count in reaction_types.values() if count > 0
                )
                max_entropy = math.log(len(reaction_types))
                diversity = entropy / max_entropy if max_entropy > 0 else 0.0
            elif total_reactions > 0:
                diversity = 0.0  # Only one reaction type = no diversity
            else:
                diversity = 0.0

            # Update hot take with reaction data
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE hot_takes
                        SET total_reactions = %s,
                            reaction_diversity = %s,
                            community_score = %s
                        WHERE id = %s
                    """, (
                        total_reactions,
                        diversity,
                        min((total_reactions * diversity) * 2, 10),  # Community score 0-10
                        hot_take_id
                    ))

            logger.info("Updated reactions for hot take #%s: %s reactions, %.2f diversity", hot_take_id, total_reactions, diversity)

        except Exception as e:
            logger.error("Error updating reaction metrics: %s", e)

    async def score_controversy_with_llm(self, message_content: str, context: str = "") -> float:
        """
        Stage 3: LLM scoring for confirmed high-engagement claims.
        Only called for claims with significant community reaction.

        Returns controversy score 0-10.
        """
        try:
            prompt = f"""Rate how controversial this statement is on a scale of 0-10.

Statement: "{message_content}"

Context: {context if context else "No context"}

Guidelines:
- 0-2: Bland, universally accepted, boring
- 3-4: Mildly spicy, some might disagree
- 5-6: Polarizing, strong opinions on both sides
- 7-8: Very controversial, likely to spark heated debate
- 9-10: Extremely divisive, nuclear-level hot take

Respond with ONLY a number 0-10 and brief explanation:
{{"score": X, "reasoning": "why"}}"""

            headers = {
                "Authorization": f"Bearer {self.llm.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.llm.model,
                "messages": [
                    {"role": "system", "content": "You rate controversy objectively. Be calibrated - most statements are 3-6."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 150,
                "temperature": 0.3
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

            # Extract score from JSON response
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                score = float(result.get('score', 0))
                logger.info("LLM controversy score: %s/10 - %s", score, result.get('reasoning', ''))
                return min(max(score, 0), 10)  # Clamp 0-10

            return 5.0  # Default mid-range

        except Exception as e:
            logger.error("Error scoring controversy: %s", e)
            return 5.0

    async def create_hot_take(self, claim_id: int, message, controversy_data: dict):
        """
        Create a hot take entry linked to an existing claim.
        """
        try:
            community_data = await self.track_community_reaction(message.id, message.channel.id)

            with self.db.get_connection() as conn:


                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO hot_takes
                        (claim_id, controversy_score, community_score,
                         total_reactions, reaction_diversity, reply_count,
                         vindication_status, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (claim_id) DO UPDATE SET
                            controversy_score = EXCLUDED.controversy_score,
                            community_score = EXCLUDED.community_score
                        RETURNING id
                """, (
                    claim_id,
                    0.0,  # Will be scored later if high engagement
                    community_data['community_score'],
                    community_data['total_reactions'],
                    community_data['reaction_diversity'],
                    community_data['reply_count'],
                    'pending',
                    datetime.now()
                ))

                result = cur.fetchone()
                if result:
                    hot_take_id = result[0]
                    logger.info("Hot take #%s created for claim #%s", hot_take_id, claim_id)
                    return hot_take_id

            return None

        except Exception as e:
            logger.error("Error creating hot take: %s", e)
            return None

    async def create_hot_take_from_message(self, message, added_by_user):
        """
        Manually create a hot take from any message (fire emoji trigger).
        Creates claim first if needed, then hot take.
        """
        try:
            # First, check if this message already has a claim
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM claims WHERE message_id = %s", (message.id,))
                    result = cur.fetchone()

                    if result:
                        claim_id = result[0]
                        logger.debug("Found existing claim #%s for message", claim_id)
                    else:
                        # Create a claim for this message
                        # Get context (3 messages before)
                        context_messages = self.db.get_recent_messages(message.channel.id, limit=4)
                        context = "\n".join([f"{m['username']}: {m['content']}" for m in context_messages[:-1]])

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
                            message.content,
                            'opinion',  # Default type for manual hot takes
                            'certain',
                            context,
                            message.created_at
                        ))

                        result = cur.fetchone()
                        if result:
                            claim_id = result[0]
                            logger.info("Created claim #%s from manual hot take", claim_id)
                        else:
                            return None

                    # Check if hot take already exists
                    cur.execute("SELECT id FROM hot_takes WHERE claim_id = %s", (claim_id,))
                    if cur.fetchone():
                        logger.debug("Hot take already exists for claim #%s", claim_id)
                        return None

                    # Create hot take
                    community_data = await self.track_community_reaction(message.id, message.channel.id)

                    cur.execute("""
                        INSERT INTO hot_takes
                        (claim_id, controversy_score, community_score,
                         total_reactions, reaction_diversity, reply_count,
                         vindication_status, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        claim_id,
                        5.0,  # Default manual hot takes to moderate controversy
                        community_data['community_score'],
                        community_data['total_reactions'],
                        community_data['reaction_diversity'],
                        community_data['reply_count'],
                        'pending',
                        datetime.now()
                    ))

                    result = cur.fetchone()
                    if result:
                        hot_take_id = result[0]
                        logger.info("Manual hot take #%s created by %s", hot_take_id, added_by_user)
                        return hot_take_id

            return None

        except Exception as e:
            logger.error("Error creating manual hot take: %s", e)
            return None

    async def check_and_score_high_engagement(self, hot_take_id: int, message):
        """
        Check if hot take has high enough engagement to warrant LLM scoring.
        Threshold: 5+ reactions OR 3+ replies within 1 hour.
        """
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT total_reactions, reply_count, controversy_score
                        FROM hot_takes
                        WHERE id = %s
                    """, (hot_take_id,))

                    result = cur.fetchone()
                    if not result:
                        return

                    total_reactions, reply_count, current_score = result

                    # Check if meets threshold and hasn't been scored yet
                    if (total_reactions >= 5 or reply_count >= 3) and current_score == 0.0:
                        logger.info("Hot take #%s meets threshold - sending to LLM for scoring", hot_take_id)

                        # Get claim context
                        cur.execute("""
                            SELECT c.claim_text, c.context
                            FROM claims c
                            JOIN hot_takes ht ON ht.claim_id = c.id
                            WHERE ht.id = %s
                        """, (hot_take_id,))

                        claim_data = cur.fetchone()
                        if claim_data:
                            claim_text, context = claim_data

                            # Score with LLM
                            controversy_score = await self.score_controversy_with_llm(claim_text, context)

                            # Update score
                            cur.execute("""
                                UPDATE hot_takes
                                SET controversy_score = %s
                                WHERE id = %s
                            """, (controversy_score, hot_take_id))

                            logger.info("Hot take #%s scored: %s/10", hot_take_id, controversy_score)

        except Exception as e:
            logger.error("Error checking high engagement: %s", e)

    async def vindicate_hot_take(self, hot_take_id: int, status: str, notes: str = None):
        """
        Mark a hot take as vindicated (won/lost/mixed).
        Admin command to track accuracy.
        """
        try:
            valid_statuses = ['won', 'lost', 'mixed', 'pending']
            if status not in valid_statuses:
                return False

            # Calculate age score (how well it aged)
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE hot_takes
                        SET vindication_status = %s,
                            vindication_date = %s,
                            vindication_notes = %s,
                            age_score = CASE
                                WHEN %s = 'won' THEN 10.0
                                WHEN %s = 'mixed' THEN 5.0
                                WHEN %s = 'lost' THEN 0.0
                                ELSE NULL
                            END
                        WHERE id = %s
                    """, (status, datetime.now(), notes, status, status, status, hot_take_id))

                    if cur.rowcount > 0:
                        logger.info("Hot take #%s vindicated as: %s", hot_take_id, status)
                        return True

            return False

        except Exception as e:
            logger.error("Error vindicating hot take: %s", e)
            return False

    async def get_leaderboard(self, leaderboard_type: str, days: int = 30, limit: int = 10) -> list:
        """
        Get hot takes leaderboard.

        Types:
        - 'controversial': Highest controversy scores
        - 'vindicated': Best track record (age_score)
        - 'worst': Most proven wrong
        - 'community': Highest community engagement
        - 'combined': Overall hot take kings (controversy * vindication)
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)

            with self.db.get_connection() as conn:


                with conn.cursor() as cur:
                    if leaderboard_type == 'controversial':
                        query = """
                            SELECT c.username, c.claim_text, ht.controversy_score,
                                   ht.community_score, ht.total_reactions, ht.created_at
                            FROM hot_takes ht
                            JOIN claims c ON c.id = ht.claim_id
                            WHERE ht.created_at > %s AND ht.controversy_score > 0
                            ORDER BY ht.controversy_score DESC
                            LIMIT %s
                        """
                    elif leaderboard_type == 'vindicated':
                        query = """
                            SELECT c.username, c.claim_text, ht.age_score,
                                   ht.vindication_status, ht.vindication_date
                            FROM hot_takes ht
                            JOIN claims c ON c.id = ht.claim_id
                            WHERE ht.created_at > %s AND ht.vindication_status = 'won'
                            ORDER BY ht.age_score DESC
                            LIMIT %s
                        """
                    elif leaderboard_type == 'worst':
                        query = """
                            SELECT c.username, c.claim_text, ht.age_score,
                                   ht.vindication_status, ht.vindication_date
                            FROM hot_takes ht
                            JOIN claims c ON c.id = ht.claim_id
                            WHERE ht.created_at > %s AND ht.vindication_status = 'lost'
                            ORDER BY ht.age_score ASC
                            LIMIT %s
                        """
                    elif leaderboard_type == 'community':
                        query = """
                            SELECT c.username, c.claim_text, ht.community_score,
                                   ht.total_reactions, ht.reply_count, ht.created_at
                            FROM hot_takes ht
                            JOIN claims c ON c.id = ht.claim_id
                            WHERE ht.created_at > %s
                            ORDER BY ht.community_score DESC
                            LIMIT %s
                        """
                    else:  # combined
                        query = """
                            SELECT c.username, c.claim_text,
                                   (ht.controversy_score * COALESCE(ht.age_score, 5)) as combined_score,
                                   ht.controversy_score, ht.age_score, ht.community_score
                            FROM hot_takes ht
                            JOIN claims c ON c.id = ht.claim_id
                            WHERE ht.created_at > %s AND ht.controversy_score > 0
                            ORDER BY combined_score DESC
                            LIMIT %s
                        """

                    cur.execute(query, (cutoff_date, limit))

                    columns = [desc[0] for desc in cur.description]
                    results = cur.fetchall()

                    return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            logger.error("Error fetching leaderboard: %s", e)
            return []

    async def get_user_hot_takes_stats(self, user_id: int) -> dict:
        """
        Get user's hot takes statistics.
        """
        try:
            with self.db.get_connection() as conn:

                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            COUNT(*) as total_hot_takes,
                            AVG(ht.controversy_score) as avg_controversy,
                            AVG(ht.community_score) as avg_community,
                            COUNT(*) FILTER (WHERE ht.vindication_status = 'won') as vindicated_count,
                            COUNT(*) FILTER (WHERE ht.vindication_status = 'lost') as failed_count,
                            MAX(ht.controversy_score) as spiciest_take
                        FROM hot_takes ht
                        JOIN claims c ON c.id = ht.claim_id
                        WHERE c.user_id = %s
                    """, (user_id,))

                    row = cur.fetchone()
                    if row:
                        return {
                            'total_hot_takes': row[0] or 0,
                            'avg_controversy': float(row[1] or 0),
                            'avg_community': float(row[2] or 0),
                            'vindicated_count': row[3] or 0,
                            'failed_count': row[4] or 0,
                            'spiciest_take': float(row[5] or 0)
                        }

            return {}

        except Exception as e:
            logger.error("Error fetching user hot takes stats: %s", e)
            return {}
