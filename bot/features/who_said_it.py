"""
Who Said It? Game
Pull real anonymous quotes from server history and challenge users to guess
who said it. Respects GDPR opt-outs.
"""

import json
import random
import asyncio
import re
from datetime import datetime
from typing import Dict, List, Optional
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)


class WhoSaidItGame:
    """Manage 'Who Said It?' game sessions."""

    def __init__(self, db):
        self.db = db
        self.active_sessions = {}  # {channel_id: session_data}

    def is_session_active(self, channel_id: int) -> bool:
        return channel_id in self.active_sessions

    def get_active_session(self, channel_id: int) -> Optional[Dict]:
        return self.active_sessions.get(channel_id)

    async def start_game(self, channel_id: int, guild_id: int,
                         started_by: int, rounds: int = 5) -> Dict:
        """
        Start a new Who Said It? game.

        Args:
            channel_id: Discord channel ID
            guild_id: Discord guild ID
            started_by: User who started the game
            rounds: Number of rounds (3-10)

        Returns:
            Dict with first quote or error
        """
        if channel_id in self.active_sessions:
            return {'error': 'A game is already active in this channel!'}

        rounds = min(max(rounds, 3), 10)

        # Fetch random quotes from message history
        quotes = await asyncio.to_thread(
            self._fetch_random_quotes, guild_id, rounds * 2  # Fetch extra for filtering
        )

        if len(quotes) < rounds:
            return {'error': f'Not enough message history. Need at least {rounds} qualifying messages.'}

        # Shuffle and select
        random.shuffle(quotes)
        selected = quotes[:rounds]

        session = {
            'guild_id': guild_id,
            'channel_id': channel_id,
            'started_by': started_by,
            'rounds': rounds,
            'current_round': 0,
            'quotes': selected,
            'scores': {},  # {user_id: {correct: int, username: str}}
            'status': 'active',
            'current_answer': None,
            'started_at': datetime.now().isoformat()
        }

        self.active_sessions[channel_id] = session
        await self._save_session(channel_id, session)

        # Return first question
        return self._get_current_question(session)

    def _fetch_random_quotes(self, guild_id: int, count: int) -> List[Dict]:
        """Fetch random qualifying messages from the database."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT m.content, m.user_id, m.username, m.message_id
                        FROM messages m
                        LEFT JOIN user_profiles up ON up.user_id = m.user_id
                        WHERE COALESCE(m.opted_out, FALSE) = FALSE
                            AND COALESCE(up.opted_out, FALSE) = FALSE
                            AND LENGTH(m.content) > 30
                            AND LENGTH(m.content) < 500
                            AND m.content NOT LIKE '!%%'
                            AND m.content NOT LIKE '/%%'
                            AND m.content NOT LIKE 'http%%'
                        ORDER BY RANDOM()
                        LIMIT %s
                    """, (count,))
                    rows = cur.fetchall()

                    quotes = []
                    for row in rows:
                        # Clean the content: strip mentions
                        content = re.sub(r'<@!?\d+>', '[someone]', row['content'])
                        content = re.sub(r'<#\d+>', '[channel]', content)
                        content = re.sub(r'<@&\d+>', '[role]', content)

                        quotes.append({
                            'content': content,
                            'user_id': row['user_id'],
                            'username': row['username']
                        })

                    return quotes
        except Exception as e:
            logger.error("Error fetching quotes for Who Said It: %s", e)
            return []

    def _get_current_question(self, session: Dict) -> Dict:
        """Get the current round's question."""
        idx = session['current_round']
        if idx >= len(session['quotes']):
            return {'game_over': True}

        quote = session['quotes'][idx]
        session['current_answer'] = quote['username']

        return {
            'round': idx + 1,
            'total_rounds': session['rounds'],
            'quote': quote['content'],
            'answer': None  # Don't reveal yet
        }

    async def submit_guess(self, channel_id: int, user_id: int,
                           username: str, guess: str) -> Optional[Dict]:
        """
        Process a guess for who said the current quote.

        Args:
            channel_id: Channel with active game
            user_id: Who is guessing
            username: Display name of guesser
            guess: Their guess text

        Returns:
            Dict with result, or None if no active game
        """
        session = self.active_sessions.get(channel_id)
        if not session or session['status'] != 'active':
            return None

        correct_answer = session.get('current_answer', '')
        if not correct_answer:
            return None

        # Fuzzy match: case-insensitive, check if guess contains the username or vice versa
        guess_lower = guess.lower().strip()
        answer_lower = correct_answer.lower().strip()
        is_correct = (
            guess_lower == answer_lower or
            guess_lower in answer_lower or
            answer_lower in guess_lower
        )

        # Initialize scorer
        if user_id not in session['scores']:
            session['scores'][user_id] = {'correct': 0, 'username': username}

        result = {
            'is_correct': is_correct,
            'correct_answer': correct_answer,
            'guesser': username,
            'round': session['current_round'] + 1,
            'total_rounds': session['rounds']
        }

        if is_correct:
            session['scores'][user_id]['correct'] += 1
            # Move to next round
            session['current_round'] += 1

            if session['current_round'] >= session['rounds']:
                result['game_over'] = True
                result['final_scores'] = self._get_sorted_scores(session)
                await self.end_game(channel_id)
            else:
                next_q = self._get_current_question(session)
                result['next_quote'] = next_q.get('quote')
                result['next_round'] = next_q.get('round')
                await self._save_session(channel_id, session)

        return result

    async def skip_round(self, channel_id: int) -> Optional[Dict]:
        """Skip to next round, revealing the answer."""
        session = self.active_sessions.get(channel_id)
        if not session or session['status'] != 'active':
            return None

        correct_answer = session.get('current_answer', 'Unknown')
        session['current_round'] += 1

        if session['current_round'] >= session['rounds']:
            result = {
                'skipped': True,
                'correct_answer': correct_answer,
                'game_over': True,
                'final_scores': self._get_sorted_scores(session)
            }
            await self.end_game(channel_id)
        else:
            next_q = self._get_current_question(session)
            result = {
                'skipped': True,
                'correct_answer': correct_answer,
                'next_quote': next_q.get('quote'),
                'next_round': next_q.get('round'),
                'total_rounds': session['rounds']
            }
            await self._save_session(channel_id, session)

        return result

    def _get_sorted_scores(self, session: Dict) -> List[Dict]:
        """Get sorted final scores."""
        scores = []
        for uid, data in session['scores'].items():
            scores.append({
                'user_id': uid,
                'username': data['username'],
                'correct': data['correct']
            })
        scores.sort(key=lambda x: x['correct'], reverse=True)
        return scores

    async def end_game(self, channel_id: int) -> Optional[Dict]:
        """End the game and return final scores."""
        session = self.active_sessions.pop(channel_id, None)
        if not session:
            return None

        # Deactivate in DB
        await asyncio.to_thread(self._deactivate_session, channel_id)

        return {
            'final_scores': self._get_sorted_scores(session),
            'total_rounds': session['rounds']
        }

    async def _save_session(self, channel_id: int, session: Dict):
        """Persist session to database."""
        try:
            state = {k: v for k, v in session.items()}
            # Convert scores keys to strings for JSON
            state['scores'] = {str(k): v for k, v in session['scores'].items()}

            await asyncio.to_thread(
                self._save_session_sync, channel_id,
                session['guild_id'], session['started_by'], state
            )
        except Exception as e:
            logger.error("Error saving Who Said It session: %s", e)

    def _save_session_sync(self, channel_id, guild_id, started_by, state):
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM active_who_said_it WHERE channel_id = %s AND is_active = TRUE",
                    (channel_id,)
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        "UPDATE active_who_said_it SET session_state = %s, updated_at = NOW() WHERE id = %s",
                        (json.dumps(state), existing[0])
                    )
                else:
                    cur.execute("""
                        INSERT INTO active_who_said_it (channel_id, guild_id, started_by, session_state)
                        VALUES (%s, %s, %s, %s)
                    """, (channel_id, guild_id, started_by, json.dumps(state)))
                conn.commit()

    def _deactivate_session(self, channel_id):
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE active_who_said_it SET is_active = FALSE, updated_at = NOW() WHERE channel_id = %s AND is_active = TRUE",
                        (channel_id,)
                    )
                    conn.commit()
        except Exception as e:
            logger.error("Error deactivating Who Said It session: %s", e)
