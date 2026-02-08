"""
Devil's Advocate Mode
Bot argues the opposing side of any topic. Uses debate scoring
to track quality. 30-minute inactivity timeout.
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

DEVILS_ADVOCATE_PROMPT = """You are playing devil's advocate on the topic: "{topic}"

Your job is to argue the OPPOSING side of whatever position the user takes.
Be intellectually rigorous, cite potential counterarguments, and challenge assumptions.
Stay respectful but firm. Use logic, evidence, and reasoning.

Rules:
- Always argue the opposite of the user's position
- Be concise (2-3 paragraphs max)
- Use facts and logical reasoning
- Stay on topic
- Don't break character or acknowledge you're playing devil's advocate
- If the user makes a strong point, acknowledge it briefly but counter with something stronger
"""


class DevilsAdvocate:
    """Manage Devil's Advocate debate sessions."""

    def __init__(self, db, llm):
        self.db = db
        self.llm = llm
        self.active_sessions = {}  # {channel_id: session_data}

    def is_session_active(self, channel_id: int) -> bool:
        return channel_id in self.active_sessions

    def get_active_session(self, channel_id: int) -> Optional[Dict]:
        return self.active_sessions.get(channel_id)

    async def start_session(self, channel_id: int, guild_id: int,
                            topic: str, user_id: int) -> Dict:
        """
        Start a Devil's Advocate session.

        Args:
            channel_id: Discord channel ID
            guild_id: Discord guild ID
            topic: Debate topic
            user_id: Who started it

        Returns:
            Dict with opening statement or error
        """
        if channel_id in self.active_sessions:
            return {'error': "A devil's advocate session is already active in this channel!"}

        session = {
            'guild_id': guild_id,
            'channel_id': channel_id,
            'started_by': user_id,
            'topic': topic,
            'exchange_count': 0,
            'history': [],  # [{role: 'user'/'assistant', content: str}]
            'started_at': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'status': 'active'
        }

        # Generate opening statement
        try:
            system_prompt = DEVILS_ADVOCATE_PROMPT.format(topic=topic)
            opening = await self.llm.simple_completion(
                prompt=f"The user wants to discuss: {topic}\n\nProvide a brief opening statement presenting the contrarian view on this topic. Be provocative but intellectually honest.",
                system_prompt=system_prompt,
                max_tokens=500
            )

            session['history'].append({'role': 'assistant', 'content': opening})
            self.active_sessions[channel_id] = session
            await self._save_session(channel_id, session)

            return {
                'topic': topic,
                'response': opening
            }
        except Exception as e:
            logger.error("Error starting devil's advocate: %s", e)
            return {'error': str(e)}

    async def respond(self, channel_id: int, user_message: str) -> Optional[Dict]:
        """
        Generate a counter-argument response.

        Args:
            channel_id: Channel with active session
            user_message: The user's argument

        Returns:
            Dict with response, or None if no active session
        """
        session = self.active_sessions.get(channel_id)
        if not session or session['status'] != 'active':
            return None

        # Update activity timestamp
        session['last_activity'] = datetime.now().isoformat()
        session['exchange_count'] += 1
        session['history'].append({'role': 'user', 'content': user_message})

        # Build conversation context (keep last 6 exchanges to stay within context)
        recent_history = session['history'][-12:]  # 6 exchanges = 12 messages
        history_text = "\n".join(
            f"{'User' if h['role'] == 'user' else 'Devil\\'s Advocate'}: {h['content']}"
            for h in recent_history[:-1]  # Exclude the latest user message
        )

        try:
            system_prompt = DEVILS_ADVOCATE_PROMPT.format(topic=session['topic'])
            prompt = f"Conversation so far:\n{history_text}\n\nUser's latest argument: {user_message}\n\nProvide your counter-argument:"

            response = await self.llm.simple_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=600
            )

            session['history'].append({'role': 'assistant', 'content': response})
            await self._save_session(channel_id, session)

            return {
                'response': response,
                'exchange_count': session['exchange_count']
            }
        except Exception as e:
            logger.error("Error in devil's advocate response: %s", e)
            return {'error': str(e)}

    async def end_session(self, channel_id: int) -> Optional[Dict]:
        """End a Devil's Advocate session."""
        session = self.active_sessions.pop(channel_id, None)
        if not session:
            return None

        await asyncio.to_thread(self._deactivate_session, channel_id)

        return {
            'topic': session['topic'],
            'exchange_count': session['exchange_count'],
            'duration_minutes': self._session_duration(session)
        }

    def _session_duration(self, session: Dict) -> int:
        """Get session duration in minutes."""
        try:
            started = datetime.fromisoformat(session['started_at'])
            return int((datetime.now() - started).total_seconds() / 60)
        except Exception:
            return 0

    async def check_timeouts(self) -> List[int]:
        """Check for sessions that have been inactive for 30+ minutes.
        Returns list of channel_ids that timed out."""
        timed_out = []
        now = datetime.now()

        for channel_id, session in list(self.active_sessions.items()):
            try:
                last_activity = datetime.fromisoformat(session['last_activity'])
                if (now - last_activity).total_seconds() > 1800:  # 30 minutes
                    timed_out.append(channel_id)
            except Exception:
                pass

        for channel_id in timed_out:
            self.active_sessions.pop(channel_id, None)
            await asyncio.to_thread(self._deactivate_session, channel_id)

        return timed_out

    async def _save_session(self, channel_id: int, session: Dict):
        """Persist session to database."""
        try:
            state = dict(session)
            await asyncio.to_thread(
                self._save_session_sync, channel_id,
                session['guild_id'], session['topic'],
                session['started_by'], state
            )
        except Exception as e:
            logger.error("Error saving devil's advocate session: %s", e)

    def _save_session_sync(self, channel_id, guild_id, topic, started_by, state):
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM active_devils_advocate WHERE channel_id = %s AND is_active = TRUE",
                    (channel_id,)
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        "UPDATE active_devils_advocate SET session_state = %s, updated_at = NOW() WHERE id = %s",
                        (json.dumps(state), existing[0])
                    )
                else:
                    cur.execute("""
                        INSERT INTO active_devils_advocate (channel_id, guild_id, topic, started_by, session_state)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (channel_id, guild_id, topic, started_by, json.dumps(state)))
                conn.commit()

    def _deactivate_session(self, channel_id):
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE active_devils_advocate SET is_active = FALSE, updated_at = NOW() WHERE channel_id = %s AND is_active = TRUE",
                        (channel_id,)
                    )
                    conn.commit()
        except Exception as e:
            logger.error("Error deactivating devil's advocate session: %s", e)
