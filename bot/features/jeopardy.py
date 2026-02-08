"""
Channel Jeopardy Game
Jeopardy variant with categories generated from server's actual discussion topics.
Players pick categories and point values, answer in form of a question.
"""

import json
import asyncio
import time
import random
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

JEOPARDY_GENERATION_PROMPT = """Generate a Jeopardy game board with {num_categories} categories and {clues_per} clues per category.

{topic_context}

For each category, create clues at increasing difficulty (point values: {point_values}).
Each clue should have:
- "clue": The Jeopardy-style clue (a statement/description)
- "answer": The correct response (should be phrased as a question, e.g. "What is Python?")
- "answer_key": The key word(s) to match against (e.g. "Python")
- "alternatives": A list of acceptable alternative answers (just the key words)

Return valid JSON in this exact format:
{{
    "categories": [
        {{
            "name": "CATEGORY NAME IN CAPS",
            "clues": [
                {{
                    "value": {first_value},
                    "clue": "This programming language uses indentation for code blocks",
                    "answer": "What is Python?",
                    "answer_key": "Python",
                    "alternatives": ["python3", "cpython"]
                }},
                ...more clues at increasing values...
            ]
        }},
        ...more categories...
    ]
}}

Make clues interesting, varied, and progressively harder. Low-value clues should be easy,
high-value clues should be challenging. Keep clues concise (1-2 sentences max).
"""


class JeopardyGame:
    """Manage Channel Jeopardy game sessions."""

    def __init__(self, db, llm, chat_stats=None):
        self.db = db
        self.llm = llm
        self.chat_stats = chat_stats
        self.active_sessions = {}  # {channel_id: session_data}

    def is_session_active(self, channel_id: int) -> bool:
        return channel_id in self.active_sessions

    def get_active_session(self, channel_id: int) -> Optional[Dict]:
        return self.active_sessions.get(channel_id)

    async def start_game(self, channel_id: int, guild_id: int,
                         started_by: int, num_categories: int = 4,
                         clues_per: int = 5) -> Dict:
        """
        Start a new Jeopardy game.

        Args:
            channel_id: Discord channel ID
            guild_id: Discord guild ID
            started_by: User who started the game
            num_categories: Number of categories (3-6)
            clues_per: Clues per category (3-5)

        Returns:
            Dict with game board or error
        """
        if channel_id in self.active_sessions:
            return {'error': 'A Jeopardy game is already active in this channel!'}

        num_categories = min(max(num_categories, 3), 6)
        clues_per = min(max(clues_per, 3), 5)

        # Point values scale with clues_per
        point_values = [200 * (i + 1) for i in range(clues_per)]

        # Try to get server topics for context
        topic_context = ""
        if self.chat_stats:
            try:
                messages = await asyncio.to_thread(
                    self._fetch_recent_messages, guild_id
                )
                if messages:
                    topics = self.chat_stats.extract_topics_tfidf(messages, top_n=10)
                    if topics:
                        topic_names = [t[0] for t in topics[:10]]
                        topic_context = (
                            f"The server frequently discusses these topics: {', '.join(topic_names)}. "
                            f"Try to make 1-2 categories related to these server topics. "
                            f"The remaining categories should be general knowledge (science, history, pop culture, etc)."
                        )
            except Exception as e:
                logger.warning("Could not fetch server topics for Jeopardy: %s", e)

        if not topic_context:
            topic_context = "Create diverse general knowledge categories (science, history, pop culture, geography, technology, etc)."

        # Generate the game board via LLM
        try:
            prompt = JEOPARDY_GENERATION_PROMPT.format(
                num_categories=num_categories,
                clues_per=clues_per,
                topic_context=topic_context,
                point_values=", ".join(str(v) for v in point_values),
                first_value=point_values[0]
            )

            response = await self.llm.simple_completion(
                prompt=prompt,
                system_prompt="You are a Jeopardy game board generator. Return only valid JSON, no extra text.",
                max_tokens=2000
            )

            # Parse the JSON response
            board = self._parse_board(response, num_categories, clues_per, point_values)
            if not board:
                return {'error': 'Failed to generate game board. Try again!'}

        except Exception as e:
            logger.error("Error generating Jeopardy board: %s", e)
            return {'error': f'Failed to generate game board: {str(e)}'}

        session = {
            'guild_id': guild_id,
            'channel_id': channel_id,
            'started_by': started_by,
            'board': board,  # {categories: [{name, clues: [{value, clue, answer, answer_key, alternatives, revealed}]}]}
            'scores': {},  # {user_id: {username: str, score: int}}
            'current_clue': None,  # {category_idx, clue_idx, value, clue, answer_key, alternatives, asked_at}
            'clues_remaining': sum(len(cat['clues']) for cat in board['categories']),
            'status': 'board',  # 'board' (picking), 'answering' (waiting for answer)
            'last_correct_user': None,  # User who gets to pick next
            'started_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat()
        }

        self.active_sessions[channel_id] = session
        await self._save_session(channel_id, session)

        return {
            'board': board,
            'categories': [cat['name'] for cat in board['categories']],
            'point_values': point_values,
            'clues_remaining': session['clues_remaining']
        }

    def _parse_board(self, response: str, num_categories: int,
                     clues_per: int, point_values: List[int]) -> Optional[Dict]:
        """Parse the LLM-generated board JSON."""
        try:
            # Try to extract JSON from the response
            text = response.strip()
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()

            # Find the JSON object
            start = text.find('{')
            end = text.rfind('}') + 1
            if start == -1 or end == 0:
                return None

            board = json.loads(text[start:end])

            # Validate structure
            if 'categories' not in board:
                return None

            categories = board['categories'][:num_categories]
            if len(categories) < 2:
                return None

            # Normalize and validate each category
            for cat in categories:
                if 'name' not in cat or 'clues' not in cat:
                    return None

                clues = cat['clues'][:clues_per]
                for i, clue in enumerate(clues):
                    # Ensure all required fields exist
                    if 'clue' not in clue or 'answer_key' not in clue:
                        return None

                    # Normalize
                    clue['value'] = point_values[i] if i < len(point_values) else point_values[-1]
                    clue['revealed'] = False
                    if 'alternatives' not in clue:
                        clue['alternatives'] = []
                    if 'answer' not in clue:
                        clue['answer'] = f"What is {clue['answer_key']}?"

                cat['clues'] = clues

            board['categories'] = categories
            return board

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error("Failed to parse Jeopardy board: %s", e)
            return None

    def _fetch_recent_messages(self, guild_id: int) -> List[Dict]:
        """Fetch recent messages for topic extraction."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT content, user_id, username
                        FROM messages
                        WHERE COALESCE(opted_out, FALSE) = FALSE
                            AND LENGTH(content) > 20
                            AND content NOT LIKE '!%%'
                            AND content NOT LIKE '/%%'
                            AND timestamp > NOW() - INTERVAL '14 days'
                        ORDER BY RANDOM()
                        LIMIT 500
                    """)
                    return cur.fetchall()
        except Exception as e:
            logger.error("Error fetching messages for Jeopardy topics: %s", e)
            return []

    async def select_clue(self, channel_id: int, category_name: str,
                          value: int) -> Optional[Dict]:
        """
        Select a clue from the board.

        Args:
            channel_id: Channel with active game
            category_name: Category name (fuzzy matched)
            value: Point value

        Returns:
            Dict with clue info, or error
        """
        session = self.active_sessions.get(channel_id)
        if not session:
            return {'error': 'No active Jeopardy game in this channel!'}

        if session['status'] == 'answering':
            return {'error': 'A clue is already active! Answer it first or use `/jeopardy_pass` to skip.'}

        # Find the category (fuzzy match)
        cat_idx = None
        best_match = 0
        for i, cat in enumerate(session['board']['categories']):
            similarity = SequenceMatcher(
                None,
                category_name.lower().strip(),
                cat['name'].lower().strip()
            ).ratio()
            if similarity > best_match:
                best_match = similarity
                cat_idx = i

        if cat_idx is None or best_match < 0.4:
            categories = [c['name'] for c in session['board']['categories']]
            return {'error': f'Category not found. Available: {", ".join(categories)}'}

        category = session['board']['categories'][cat_idx]

        # Find the clue by value
        clue_idx = None
        for i, clue in enumerate(category['clues']):
            if clue['value'] == value and not clue['revealed']:
                clue_idx = i
                break

        if clue_idx is None:
            available = [str(c['value']) for c in category['clues'] if not c['revealed']]
            if not available:
                return {'error': f'All clues in "{category["name"]}" have been revealed!'}
            return {'error': f'Value ${value} not available. Available values: ${", $".join(available)}'}

        clue = category['clues'][clue_idx]

        # Set current clue
        session['current_clue'] = {
            'category_idx': cat_idx,
            'clue_idx': clue_idx,
            'category_name': category['name'],
            'value': clue['value'],
            'clue': clue['clue'],
            'answer': clue['answer'],
            'answer_key': clue['answer_key'],
            'alternatives': clue.get('alternatives', []),
            'asked_at': time.time()
        }
        session['status'] = 'answering'
        session['last_activity'] = datetime.now().isoformat()

        await self._save_session(channel_id, session)

        return {
            'category': category['name'],
            'value': clue['value'],
            'clue': clue['clue']
        }

    async def submit_answer(self, channel_id: int, user_id: int,
                            username: str, answer: str) -> Optional[Dict]:
        """
        Process a Jeopardy answer.

        Args:
            channel_id: Channel with active game
            user_id: Answering user
            username: Display name
            answer: Their answer text

        Returns:
            Dict with result, or None if no active clue
        """
        session = self.active_sessions.get(channel_id)
        if not session or session['status'] != 'answering':
            return None

        current = session.get('current_clue')
        if not current:
            return None

        # Initialize scorer
        if user_id not in session['scores']:
            session['scores'][user_id] = {'username': username, 'score': 0}

        # Check answer (fuzzy match)
        is_correct, similarity = self._check_answer(
            answer,
            current['answer_key'],
            current.get('alternatives', [])
        )

        time_taken = time.time() - current['asked_at']

        result = {
            'is_correct': is_correct,
            'similarity': similarity,
            'correct_answer': current['answer'],
            'value': current['value'],
            'category': current['category_name'],
            'guesser': username,
            'time_taken': round(time_taken, 1)
        }

        if is_correct:
            # Award points
            session['scores'][user_id]['score'] += current['value']
            session['last_correct_user'] = user_id
            result['new_score'] = session['scores'][user_id]['score']

            # Mark clue as revealed
            cat_idx = current['category_idx']
            clue_idx = current['clue_idx']
            session['board']['categories'][cat_idx]['clues'][clue_idx]['revealed'] = True
            session['clues_remaining'] -= 1

            # Clear current clue
            session['current_clue'] = None
            session['status'] = 'board'

            # Check if game is over
            if session['clues_remaining'] <= 0:
                result['game_over'] = True
                result['final_scores'] = self._get_sorted_scores(session)
                await self.end_game(channel_id)
            else:
                result['clues_remaining'] = session['clues_remaining']
                await self._save_session(channel_id, session)
        else:
            # Wrong answer - deduct points
            session['scores'][user_id]['score'] -= current['value']
            result['new_score'] = session['scores'][user_id]['score']
            result['deducted'] = current['value']
            await self._save_session(channel_id, session)

        return result

    async def pass_clue(self, channel_id: int) -> Optional[Dict]:
        """Skip the current clue and reveal the answer."""
        session = self.active_sessions.get(channel_id)
        if not session or session['status'] != 'answering':
            return None

        current = session.get('current_clue')
        if not current:
            return None

        # Reveal the clue
        cat_idx = current['category_idx']
        clue_idx = current['clue_idx']
        session['board']['categories'][cat_idx]['clues'][clue_idx]['revealed'] = True
        session['clues_remaining'] -= 1

        result = {
            'passed': True,
            'correct_answer': current['answer'],
            'category': current['category_name'],
            'value': current['value']
        }

        session['current_clue'] = None
        session['status'] = 'board'

        if session['clues_remaining'] <= 0:
            result['game_over'] = True
            result['final_scores'] = self._get_sorted_scores(session)
            await self.end_game(channel_id)
        else:
            result['clues_remaining'] = session['clues_remaining']
            await self._save_session(channel_id, session)

        return result

    def _check_answer(self, user_answer: str, correct_key: str,
                      alternatives: List[str]) -> tuple:
        """
        Check if the user's answer is correct using fuzzy matching.

        Returns:
            (is_correct, best_similarity_score)
        """
        # Strip "what is/who is/where is" prefix if present
        normalized = user_answer.lower().strip()
        for prefix in ['what is ', 'what are ', 'who is ', 'who are ',
                       'where is ', 'where are ', 'when is ', 'when was ',
                       'what was ', 'who was ']:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break

        # Remove trailing question mark and articles
        normalized = normalized.rstrip('?').strip()
        for article in ['the ', 'a ', 'an ']:
            if normalized.startswith(article):
                normalized = normalized[len(article):]

        # Shorter answer threshold
        threshold = 0.75 if len(correct_key) <= 5 else 0.80

        # Check primary answer
        correct_norm = correct_key.lower().strip()
        similarity = SequenceMatcher(None, normalized, correct_norm).ratio()
        if similarity >= threshold:
            return (True, similarity)

        # Check exact containment
        if correct_norm in normalized or normalized in correct_norm:
            return (True, 0.95)

        # Check alternatives
        best = similarity
        for alt in alternatives:
            alt_norm = alt.lower().strip()
            alt_sim = SequenceMatcher(None, normalized, alt_norm).ratio()
            if alt_sim >= threshold:
                return (True, alt_sim)
            best = max(best, alt_sim)

            # Check containment for alternatives
            if alt_norm in normalized or normalized in alt_norm:
                return (True, 0.95)

        return (False, best)

    def get_board_display(self, channel_id: int) -> Optional[Dict]:
        """Get the current board state for display."""
        session = self.active_sessions.get(channel_id)
        if not session:
            return None

        board_data = []
        for cat in session['board']['categories']:
            cat_data = {
                'name': cat['name'],
                'clues': []
            }
            for clue in cat['clues']:
                cat_data['clues'].append({
                    'value': clue['value'],
                    'revealed': clue['revealed']
                })
            board_data.append(cat_data)

        return {
            'categories': board_data,
            'scores': self._get_sorted_scores(session),
            'clues_remaining': session['clues_remaining'],
            'status': session['status'],
            'current_clue': session.get('current_clue', {}).get('category_name') if session.get('current_clue') else None
        }

    def _get_sorted_scores(self, session: Dict) -> List[Dict]:
        """Get sorted scores."""
        scores = []
        for uid, data in session['scores'].items():
            scores.append({
                'user_id': uid,
                'username': data['username'],
                'score': data['score']
            })
        scores.sort(key=lambda x: x['score'], reverse=True)
        return scores

    async def end_game(self, channel_id: int) -> Optional[Dict]:
        """End the game and return final scores."""
        session = self.active_sessions.pop(channel_id, None)
        if not session:
            return None

        await asyncio.to_thread(self._deactivate_session, channel_id)

        return {
            'final_scores': self._get_sorted_scores(session),
            'clues_remaining': session.get('clues_remaining', 0),
            'total_clues': sum(len(cat['clues']) for cat in session['board']['categories'])
        }

    async def check_timeouts(self) -> List[int]:
        """Check for games inactive for 15+ minutes. Returns timed-out channel IDs."""
        timed_out = []
        now = datetime.now()

        for channel_id, session in list(self.active_sessions.items()):
            try:
                last_activity = datetime.fromisoformat(session['last_activity'])
                if (now - last_activity).total_seconds() > 900:  # 15 minutes
                    timed_out.append(channel_id)
            except Exception:
                pass

        for channel_id in timed_out:
            self.active_sessions.pop(channel_id, None)
            await asyncio.to_thread(self._deactivate_session, channel_id)

        return timed_out

    # ── Database persistence ──

    async def _save_session(self, channel_id: int, session: Dict):
        """Persist session to database."""
        try:
            state = dict(session)
            # Convert scores keys to strings for JSON
            state['scores'] = {str(k): v for k, v in session['scores'].items()}
            # Remove non-serializable fields
            if state.get('current_clue') and 'asked_at' in state['current_clue']:
                state['current_clue']['asked_at'] = state['current_clue']['asked_at']

            await asyncio.to_thread(
                self._save_session_sync, channel_id,
                session['guild_id'], session['started_by'], state
            )
        except Exception as e:
            logger.error("Error saving Jeopardy session: %s", e)

    def _save_session_sync(self, channel_id, guild_id, started_by, state):
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM active_jeopardy WHERE channel_id = %s AND is_active = TRUE",
                    (channel_id,)
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        "UPDATE active_jeopardy SET session_state = %s, updated_at = NOW() WHERE id = %s",
                        (json.dumps(state), existing[0])
                    )
                else:
                    cur.execute("""
                        INSERT INTO active_jeopardy (channel_id, guild_id, started_by, session_state)
                        VALUES (%s, %s, %s, %s)
                    """, (channel_id, guild_id, started_by, json.dumps(state)))
                conn.commit()

    def _deactivate_session(self, channel_id):
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE active_jeopardy SET is_active = FALSE, updated_at = NOW() WHERE channel_id = %s AND is_active = TRUE",
                        (channel_id,)
                    )
                    conn.commit()
        except Exception as e:
            logger.error("Error deactivating Jeopardy session: %s", e)
