"""
Debate Scorekeeper Feature
Track debates, analyze arguments, detect fallacies, and determine winners
"""

import discord
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json


class DebateScorekeeper:
    """Manage debate tracking and scoring"""

    def __init__(self, db, llm):
        self.db = db
        self.llm = llm
        self.active_debates = {}  # channel_id -> debate_data

    async def start_debate(
        self,
        channel_id: int,
        guild_id: int,
        topic: str,
        started_by_user_id: int,
        started_by_username: str
    ) -> bool:
        """
        Start tracking a debate in a channel.

        Returns True if successful, False if debate already active in channel.
        """
        if channel_id in self.active_debates:
            return False

        self.active_debates[channel_id] = {
            'topic': topic,
            'guild_id': guild_id,
            'channel_id': channel_id,
            'started_by_user_id': started_by_user_id,
            'started_by_username': started_by_username,
            'started_at': datetime.now(),
            'messages': [],
            'participants': set()
        }

        print(f"⚔️ Debate started in channel {channel_id}: '{topic}'")
        return True

    def add_debate_message(self, channel_id: int, user_id: int, username: str, content: str, message_id: int):
        """Add a message to an active debate"""
        if channel_id not in self.active_debates:
            return

        debate = self.active_debates[channel_id]
        debate['messages'].append({
            'user_id': user_id,
            'username': username,
            'content': content,
            'message_id': message_id,
            'timestamp': datetime.now()
        })
        debate['participants'].add(user_id)

    async def end_debate(self, channel_id: int) -> Optional[Dict]:
        """
        End debate and analyze with LLM.

        Returns debate results dict or None if no active debate.
        """
        if channel_id not in self.active_debates:
            return None

        debate = self.active_debates[channel_id]
        ended_at = datetime.now()

        # Must have at least 2 participants and 5 messages
        if len(debate['participants']) < 2 or len(debate['messages']) < 5:
            del self.active_debates[channel_id]
            return {
                'error': 'insufficient_data',
                'message': 'Debate needs at least 2 participants and 5 messages to analyze.'
            }

        # Analyze debate with LLM
        analysis = await self._analyze_debate(debate)

        # Save to database
        debate_id = await self._save_debate(debate, ended_at, analysis)

        # Clean up active debate
        del self.active_debates[channel_id]

        return {
            'debate_id': debate_id,
            'topic': debate['topic'],
            'started_at': debate['started_at'],
            'ended_at': ended_at,
            'duration_minutes': (ended_at - debate['started_at']).total_seconds() / 60,
            'participant_count': len(debate['participants']),
            'message_count': len(debate['messages']),
            'analysis': analysis
        }

    async def _analyze_debate(self, debate: Dict) -> Dict:
        """Use LLM to analyze debate arguments and determine winner"""
        try:
            # Build debate transcript
            transcript = f"Debate Topic: {debate['topic']}\n\n"

            for msg in debate['messages']:
                transcript += f"{msg['username']}: {msg['content']}\n"

            # LLM prompt for analysis
            prompt = f"""Analyze this debate and provide:
1. A score (0-10) for each participant based on argument quality
2. Logical fallacies detected (if any)
3. The winner and why
4. Key arguments from each side

Debate Transcript:
{transcript}

Respond in JSON format:
{{
    "participants": {{
        "username": {{
            "score": 8,
            "strengths": "...",
            "weaknesses": "...",
            "fallacies": ["ad hominem", "strawman"]
        }}
    }},
    "winner": "username",
    "winner_reason": "...",
    "summary": "..."
}}"""

            # Call LLM
            response = await self.llm.generate_response(
                [],  # No conversation history needed
                prompt,
                system_prompt="You are an expert debate judge. Analyze arguments objectively and identify logical fallacies."
            )

            # Try to parse JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                # Fallback if LLM doesn't return valid JSON
                analysis = {
                    'error': 'parse_error',
                    'raw_analysis': response
                }

            return analysis

        except Exception as e:
            print(f"❌ Error analyzing debate: {e}")
            return {
                'error': 'analysis_failed',
                'message': str(e)
            }

    async def _save_debate(self, debate: Dict, ended_at: datetime, analysis: Dict) -> Optional[int]:
        """Save debate to database"""
        try:
            with self.db.conn.cursor() as cur:
                # Insert debate
                cur.execute("""
                    INSERT INTO debates (
                        topic, guild_id, channel_id,
                        started_by_user_id, started_by_username,
                        started_at, ended_at,
                        participant_count, message_count,
                        transcript, analysis
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    debate['topic'],
                    debate['guild_id'],
                    debate['channel_id'],
                    debate['started_by_user_id'],
                    debate['started_by_username'],
                    debate['started_at'],
                    ended_at,
                    len(debate['participants']),
                    len(debate['messages']),
                    json.dumps(debate['messages']),
                    json.dumps(analysis)
                ))

                debate_id = cur.fetchone()[0]

                # Insert participant records
                for user_id in debate['participants']:
                    # Get participant username from messages
                    username = next(
                        (m['username'] for m in debate['messages'] if m['user_id'] == user_id),
                        'Unknown'
                    )

                    # Get score from analysis if available
                    score = None
                    if 'participants' in analysis and username in analysis['participants']:
                        score = analysis['participants'][username].get('score')

                    # Check if winner
                    is_winner = (username == analysis.get('winner', ''))

                    cur.execute("""
                        INSERT INTO debate_participants (
                            debate_id, user_id, username,
                            message_count, score, is_winner
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        debate_id,
                        user_id,
                        username,
                        sum(1 for m in debate['messages'] if m['user_id'] == user_id),
                        score,
                        is_winner
                    ))

                self.db.conn.commit()
                return debate_id

        except Exception as e:
            print(f"❌ Error saving debate: {e}")
            self.db.conn.rollback()
            return None

    async def get_debate_stats(self, user_id: int) -> Optional[Dict]:
        """Get debate statistics for a user"""
        try:
            with self.db.conn.cursor() as cur:
                # Total debates participated in
                cur.execute("""
                    SELECT COUNT(*)
                    FROM debate_participants
                    WHERE user_id = %s
                """, (user_id,))
                total_debates = cur.fetchone()[0] or 0

                if total_debates == 0:
                    return None

                # Wins
                cur.execute("""
                    SELECT COUNT(*)
                    FROM debate_participants
                    WHERE user_id = %s AND is_winner = TRUE
                """, (user_id,))
                wins = cur.fetchone()[0] or 0

                # Average score
                cur.execute("""
                    SELECT AVG(score)
                    FROM debate_participants
                    WHERE user_id = %s AND score IS NOT NULL
                """, (user_id,))
                avg_score_result = cur.fetchone()[0]
                avg_score = round(float(avg_score_result), 2) if avg_score_result else None

                # Most debated topic (approximation - topics they participated in most)
                cur.execute("""
                    SELECT d.topic, COUNT(*) as count
                    FROM debate_participants dp
                    JOIN debates d ON d.id = dp.debate_id
                    WHERE dp.user_id = %s
                    GROUP BY d.topic
                    ORDER BY count DESC
                    LIMIT 1
                """, (user_id,))
                topic_result = cur.fetchone()
                favorite_topic = topic_result[0] if topic_result else None

                # Win rate
                win_rate = round((wins / total_debates * 100), 1) if total_debates > 0 else 0

                return {
                    'total_debates': total_debates,
                    'wins': wins,
                    'losses': total_debates - wins,
                    'win_rate': win_rate,
                    'avg_score': avg_score,
                    'favorite_topic': favorite_topic
                }

        except Exception as e:
            print(f"❌ Error getting debate stats: {e}")
            return None

    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """Get debate leaderboard for a guild"""
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        dp.user_id,
                        dp.username,
                        COUNT(*) as total_debates,
                        SUM(CASE WHEN dp.is_winner THEN 1 ELSE 0 END) as wins,
                        AVG(dp.score) as avg_score
                    FROM debate_participants dp
                    JOIN debates d ON d.id = dp.debate_id
                    WHERE d.guild_id = %s AND dp.score IS NOT NULL
                    GROUP BY dp.user_id, dp.username
                    HAVING COUNT(*) >= 2
                    ORDER BY
                        SUM(CASE WHEN dp.is_winner THEN 1 ELSE 0 END) DESC,
                        AVG(dp.score) DESC
                    LIMIT %s
                """, (guild_id, limit))

                leaderboard = []
                for row in cur.fetchall():
                    win_rate = round((row[3] / row[2] * 100), 1) if row[2] > 0 else 0
                    leaderboard.append({
                        'user_id': row[0],
                        'username': row[1],
                        'total_debates': row[2],
                        'wins': row[3],
                        'win_rate': win_rate,
                        'avg_score': round(float(row[4]), 2) if row[4] else 0
                    })

                return leaderboard

        except Exception as e:
            print(f"❌ Error getting leaderboard: {e}")
            return []

    def is_debate_active(self, channel_id: int) -> bool:
        """Check if there's an active debate in a channel"""
        return channel_id in self.active_debates

    def get_active_debate_topic(self, channel_id: int) -> Optional[str]:
        """Get the topic of an active debate in a channel"""
        if channel_id in self.active_debates:
            return self.active_debates[channel_id]['topic']
        return None
