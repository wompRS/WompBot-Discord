"""
Trivia System
Manages trivia sessions, question generation, answer validation, and scoring
"""

import asyncio
import time
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple
import re
import json


class TriviaSystem:
    """Manages trivia game sessions"""

    def __init__(self, database, llm_client):
        """
        Initialize Trivia System

        Args:
            database: Database instance
            llm_client: LLM client for question generation
        """
        self.db = database
        self.llm = llm_client

        # In-memory active sessions
        # Structure: {channel_id: session_data}
        self.active_sessions = {}

        # Answer timeout handlers
        # {channel_id: asyncio.Task}
        self.timeout_tasks = {}

    # ===== SESSION MANAGEMENT =====

    async def start_session(self, guild_id, channel_id, user_id, username,
                           topic, difficulty, question_count, time_per_question):
        """
        Start a new trivia session

        Returns: session_id (int)
        """
        # Check if session already active
        if self.is_session_active(channel_id):
            raise Exception("A trivia session is already active in this channel")

        # Generate questions via LLM
        print(f"🎲 Generating {question_count} {difficulty} questions about {topic}...")
        questions = await self.generate_questions(topic, difficulty, question_count)
        print(f"✅ Generated {len(questions)} questions")

        # Create session in database
        session_id = self.db.create_trivia_session(
            guild_id, channel_id, topic, difficulty,
            question_count, time_per_question, user_id, username
        )

        # Store questions in database
        for i, q in enumerate(questions):
            self.db.create_trivia_question(
                session_id, i+1, q['question'], q['answer'], q['alternatives'], difficulty
            )

        # Initialize in-memory session
        self.active_sessions[channel_id] = {
            'session_id': session_id,
            'guild_id': guild_id,
            'channel_id': channel_id,
            'topic': topic,
            'difficulty': difficulty,
            'question_count': question_count,
            'time_per_question': time_per_question,
            'started_by': (user_id, username),
            'started_at': datetime.now(),
            'questions': questions,
            'current_question_num': 0,
            'current_question_start': None,
            'participants': {},
            'status': 'waiting',
            'answers_this_round': set(),
        }

        return session_id

    async def end_session(self, channel_id):
        """
        Finalize session and update stats

        Returns: result dict with leaderboard
        """
        session = self.active_sessions.get(channel_id)
        if not session:
            return None

        # Cancel timeout task if exists
        if channel_id in self.timeout_tasks:
            self.timeout_tasks[channel_id].cancel()
            del self.timeout_tasks[channel_id]

        # Mark as ended in database
        self.db.end_trivia_session(session['session_id'])

        # Determine winner (highest score)
        leaderboard = sorted(
            session['participants'].items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )

        # Update user stats for all participants
        for user_id, data in session['participants'].items():
            is_winner = (leaderboard[0][0] == user_id) if leaderboard else False
            await self.update_user_stats(
                session['guild_id'],
                user_id,
                data['username'],
                session,
                data,
                is_winner
            )

        # Fetch winner's overall stats
        winner_overall_stats = None
        if leaderboard:
            winner_id = leaderboard[0][0]
            winner_overall_stats = await self.get_user_stats(session['guild_id'], winner_id)

        # Clean up in-memory session
        result = {
            'leaderboard': leaderboard,
            'question_count': session['current_question_num'],
            'topic': session['topic'],
            'difficulty': session['difficulty'],
            'winner_overall_stats': winner_overall_stats
        }

        del self.active_sessions[channel_id]

        return result

    def is_session_active(self, channel_id):
        """Check if trivia session is active in channel"""
        return channel_id in self.active_sessions

    def get_active_session(self, channel_id):
        """Get active session data"""
        return self.active_sessions.get(channel_id)

    # ===== QUESTION GENERATION =====

    def _build_generation_prompt(self, topic, difficulty, count):
        """Build LLM prompt for question generation"""

        difficulty_guidance = {
            'easy': 'Simple, general knowledge questions that most people should know',
            'medium': 'Moderate difficulty requiring some specialized knowledge',
            'hard': 'Challenging questions requiring deep knowledge or expertise'
        }

        prompt = f"""Generate exactly {count} trivia questions about: {topic}

Difficulty: {difficulty} - {difficulty_guidance[difficulty]}

CRITICAL RULES:
1. Questions must have ONE clear, specific correct answer
2. Provide 2-4 acceptable alternative answers (variations, spellings, abbreviations)
3. Questions should be factual and verifiable
4. Avoid yes/no questions
5. Answer should be concise (1-5 words typically)

Return ONLY a JSON array in this exact format:
[
  {{
    "question": "Question text here?",
    "answer": "Primary correct answer",
    "alternatives": ["Alternative 1", "Alternative 2"]
  }},
  ...
]

Examples of good questions:
- "What is the capital of France?" -> "Paris" (alternatives: ["france capital"])
- "Who wrote '1984'?" -> "George Orwell" (alternatives: ["Orwell", "Eric Arthur Blair"])
- "What year did World War II end?" -> "1945" (alternatives: ["nineteen forty-five"])

Topic: {topic}
Generate {count} questions now:"""

        return prompt

    async def generate_questions(self, topic, difficulty, count):
        """Generate trivia questions via LLM"""

        prompt = self._build_generation_prompt(topic, difficulty, count)

        # Call LLM with low temperature for consistency
        response = await asyncio.to_thread(
            self.llm.generate_response,
            prompt,
            [],          # conversation_history
            None,        # user_context
            None,        # search_results
            None,        # rag_context
            0,           # retry_count
            None,        # bot_user_id
            None,        # user_id
            None,        # username
            2000,        # max_tokens
            'default',   # personality
            None         # tools
        )

        # Parse JSON from response
        questions = self._parse_questions_from_llm(response)

        # Validate we got the right count
        if len(questions) < count:
            raise Exception(f"LLM only generated {len(questions)}/{count} questions")

        return questions[:count]

    def _extract_json_array(self, text):
        """Extract JSON array from text by finding matching brackets"""
        # Find the first '[' that starts a JSON array
        start = text.find('[')
        if start == -1:
            return None

        # Track bracket depth to find matching ']'
        depth = 0
        in_string = False
        escape_next = False

        for i, char in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == '[':
                depth += 1
            elif char == ']':
                depth -= 1
                if depth == 0:
                    return text[start:i+1]
        return None

    def _parse_questions_from_llm(self, llm_response):
        """Extract JSON array from LLM response"""
        # Try to extract JSON from code blocks first
        code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', llm_response)
        if code_block_match:
            json_str = self._extract_json_array(code_block_match.group(1))
        else:
            json_str = self._extract_json_array(llm_response)

        if not json_str:
            print(f"❌ Could not find JSON in LLM response: {llm_response[:500]}")
            raise Exception("Could not find JSON array in LLM response")

        try:
            questions = json.loads(json_str)

            # Validate structure
            for i, q in enumerate(questions):
                if 'question' not in q or 'answer' not in q:
                    print(f"❌ Question {i+1} missing required fields: {q}")
                    raise Exception(f"Invalid question format at index {i+1}")
                if 'alternatives' not in q:
                    q['alternatives'] = []
                # Ensure alternatives is a list
                elif not isinstance(q['alternatives'], list):
                    print(f"⚠️ Alternatives is not a list for question {i+1}, converting: {q['alternatives']}")
                    q['alternatives'] = [q['alternatives']] if q['alternatives'] else []

            print(f"✅ Parsed {len(questions)} questions successfully")
            return questions
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            print(f"❌ Attempted to parse: {json_str[:500]}")
            raise Exception(f"Failed to parse LLM JSON: {e}")

    # ===== QUESTION FLOW =====

    async def ask_next_question(self, channel_id, timeout_callback):
        """
        Ask next question and set timer

        Returns: question dict, session end result dict (with 'leaderboard' key), or None
        """
        session = self.active_sessions.get(channel_id)
        if not session:
            return None

        # Check if more questions
        if session['current_question_num'] >= len(session['questions']):
            result = await self.end_session(channel_id)
            return result  # Return session end result for display

        # Get current question
        q = session['questions'][session['current_question_num']]
        session['current_question_start'] = time.time()
        session['status'] = 'active'
        session['answers_this_round'] = set()

        # Set timeout task
        timeout_seconds = session['time_per_question']
        async def timeout_handler():
            await asyncio.sleep(timeout_seconds)
            await timeout_callback()

        self.timeout_tasks[channel_id] = asyncio.create_task(timeout_handler())

        return q

    async def handle_timeout(self, channel):
        """Handle question timeout and move to next question"""
        import discord

        session = self.get_active_session(channel.id)
        if not session:
            return

        q_num = session['current_question_num']
        question = session['questions'][q_num]

        # Show correct answer
        await channel.send(f"⏱️ Time's up! The answer was: **{question['answer']}**")

        await asyncio.sleep(2)

        # Move to next question
        session['current_question_num'] += 1
        result = await self.ask_next_question(
            channel.id,
            lambda: self.handle_timeout(channel)
        )

        if result:
            # Check if this is a session end result (has 'leaderboard' key)
            if 'leaderboard' in result:
                # Display session end results
                embed = discord.Embed(
                    title="🏁 Trivia Complete!",
                    description=f"**{result['topic'].title()}** - {result['difficulty'].title()} - {result['question_count']} questions",
                    color=discord.Color.gold()
                )

                if result['leaderboard']:
                    # Winner announcement with overall stats
                    winner_id, winner_data = result['leaderboard'][0]
                    winner_stats = result.get('winner_overall_stats')

                    if winner_stats:
                        accuracy = (winner_stats['total_correct'] / winner_stats['total_questions_answered'] * 100) if winner_stats['total_questions_answered'] > 0 else 0

                        winner_text = (
                            f"🏆 **{winner_data['username']}** wins with **{winner_data['score']} points** this session!\n\n"
                            f"**Overall Stats:**\n"
                            f"• Total Points: **{winner_stats['total_points']:,}** across all sessions\n"
                            f"• Total Wins: **{winner_stats['wins']}** 🏆\n"
                            f"• Accuracy: **{accuracy:.1f}%** ({winner_stats['total_correct']}/{winner_stats['total_questions_answered']} correct)\n"
                            f"• Best Streak: **{winner_stats['best_streak']}** 🔥"
                        )
                        embed.add_field(name="👑 Champion", value=winner_text, inline=False)
                    else:
                        embed.add_field(
                            name="👑 Champion",
                            value=f"🏆 **{winner_data['username']}** wins with **{winner_data['score']} points**!",
                            inline=False
                        )

                    # Session leaderboard
                    leaderboard_text = ""
                    for i, (user_id, data) in enumerate(result['leaderboard'][:10]):
                        rank_emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
                        leaderboard_text += f"{rank_emoji} **{data['username']}** - {data['score']} points\n"

                    embed.add_field(name="Session Leaderboard", value=leaderboard_text, inline=False)

                await channel.send(embed=embed)
            else:
                # It's a question - display it
                q_num = session['current_question_num'] + 1
                total = session['question_count']
                embed = discord.Embed(
                    title=f"Question {q_num}/{total}",
                    description=result['question'],
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"You have {session['time_per_question']} seconds to answer")
                await channel.send(embed=embed)

    # ===== ANSWER PROCESSING =====

    async def submit_answer(self, channel_id, user_id, username, answer_text):
        """
        Process answer submission

        Returns: result dict or None
        """
        session = self.active_sessions.get(channel_id)
        if not session or session['status'] != 'active':
            return None

        # Prevent duplicate answers
        if user_id in session['answers_this_round']:
            return {'error': 'already_answered'}

        session['answers_this_round'].add(user_id)

        # Get current question
        q_num = session['current_question_num']
        question_data = session['questions'][q_num]

        # Validate answer
        is_correct, similarity = self.validate_answer(
            answer_text,
            question_data['answer'],
            question_data['alternatives']
        )

        # Calculate time taken
        time_taken = time.time() - session['current_question_start']

        # Initialize participant if new
        if user_id not in session['participants']:
            session['participants'][user_id] = {
                'username': username,
                'score': 0,
                'streak': 0,
                'answers': []
            }

        participant = session['participants'][user_id]

        # Update streak
        if is_correct:
            participant['streak'] += 1
        else:
            participant['streak'] = 0

        # Calculate points
        points = self._calculate_points(
            is_correct,
            time_taken,
            session['difficulty'],
            participant['streak']
        )

        participant['score'] += points
        participant['answers'].append({
            'question_num': q_num + 1,
            'answer': answer_text,
            'correct': is_correct,
            'time': time_taken,
            'points': points
        })

        # Store answer in database
        question_db_id = self.db.get_trivia_question_id(session['session_id'], q_num + 1)
        if question_db_id:
            self.db.store_trivia_answer(
                session['session_id'],
                question_db_id,
                user_id,
                username,
                answer_text,
                is_correct,
                similarity,
                time_taken,
                points
            )

        return {
            'is_correct': is_correct,
            'similarity': similarity,
            'points': points,
            'time_taken': time_taken,
            'current_score': participant['score'],
            'streak': participant['streak']
        }

    def _normalize_answer(self, answer):
        """Normalize answer for comparison"""
        # Convert to lowercase
        normalized = answer.lower().strip()

        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)

        # Remove common punctuation (keep hyphens in words)
        normalized = re.sub(r'[.,!?;:"\']', '', normalized)

        # Remove articles
        normalized = re.sub(r'\b(a|an|the)\b', '', normalized, flags=re.IGNORECASE)
        normalized = normalized.strip()

        return normalized

    def _calculate_similarity(self, str1, str2):
        """Calculate similarity ratio between two strings"""
        # Normalize both strings
        norm1 = self._normalize_answer(str1)
        norm2 = self._normalize_answer(str2)

        # Use SequenceMatcher for ratio
        ratio = SequenceMatcher(None, norm1, norm2).ratio()

        print(f"      Comparing: '{norm1}' vs '{norm2}' = {ratio:.2f}")
        return ratio

    def validate_answer(self, user_answer, correct_answer, acceptable_answers):
        """
        Validate user answer with fuzzy matching

        Returns: (is_correct: bool, best_similarity: float)
        """
        # Similarity threshold (lower for very short answers)
        answer_length = len(self._normalize_answer(correct_answer))
        THRESHOLD = 0.75 if answer_length <= 5 else 0.85

        # Debug logging
        print(f"🔍 Validating answer: '{user_answer}' vs '{correct_answer}'")
        print(f"   Alternatives: {acceptable_answers}")
        print(f"   Threshold: {THRESHOLD}")

        # Check against primary answer
        similarity = self._calculate_similarity(user_answer, correct_answer)
        print(f"   Primary similarity: {similarity:.2f}")

        if similarity >= THRESHOLD:
            print(f"   ✅ Match! (primary answer)")
            return (True, similarity)

        # Check against alternatives
        best_alt_similarity = 0.0
        if acceptable_answers:
            for i, alt in enumerate(acceptable_answers):
                alt_similarity = self._calculate_similarity(user_answer, alt)
                print(f"   Alternative {i+1} '{alt}' similarity: {alt_similarity:.2f}")
                best_alt_similarity = max(best_alt_similarity, alt_similarity)

                if alt_similarity >= THRESHOLD:
                    print(f"   ✅ Match! (alternative {i+1})")
                    return (True, alt_similarity)

        # Not correct, but return best similarity for stats
        best_overall = max(similarity, best_alt_similarity)
        print(f"   ❌ No match. Best similarity: {best_overall:.2f}")
        return (False, best_overall)

    # ===== SCORING =====

    def _calculate_points(self, is_correct, time_taken, difficulty, streak):
        """Calculate points for an answer"""

        if not is_correct:
            return 0

        # Base points by difficulty
        base_points = {
            'easy': 100,
            'medium': 200,
            'hard': 300
        }

        points = base_points.get(difficulty, 100)

        # Speed bonus (faster = more points)
        # Max 50% bonus for answering in <2 seconds
        # No bonus after 10 seconds
        if time_taken < 2:
            speed_multiplier = 1.5
        elif time_taken < 5:
            speed_multiplier = 1.0 + (5 - time_taken) / 6  # Linear decay
        elif time_taken < 10:
            speed_multiplier = 1.0 + (10 - time_taken) / 20
        else:
            speed_multiplier = 1.0

        points = int(points * speed_multiplier)

        # Streak bonus (every 3 correct in a row = +10%)
        if streak >= 3:
            streak_multiplier = 1.0 + (streak // 3) * 0.1
            points = int(points * streak_multiplier)

        return points

    # ===== STATISTICS =====

    async def get_user_stats(self, guild_id, user_id):
        """Get user trivia statistics"""
        return await asyncio.to_thread(
            self.db.get_trivia_user_stats,
            guild_id,
            user_id
        )

    async def get_leaderboard(self, guild_id, days=30, limit=10):
        """Get trivia leaderboard for guild"""
        return await asyncio.to_thread(
            self.db.get_trivia_leaderboard,
            guild_id,
            days,
            limit
        )

    async def update_user_stats(self, guild_id, user_id, username, session, participant_data, is_winner):
        """Update user statistics after session"""
        # Calculate stats
        questions_answered = len(participant_data['answers'])
        correct_answers = sum(1 for ans in participant_data['answers'] if ans['correct'])
        total_points = participant_data['score']
        total_time = sum(ans['time'] for ans in participant_data['answers'])
        avg_time = total_time / questions_answered if questions_answered > 0 else 0
        best_streak = participant_data['streak']
        topic = session['topic']

        # Update in database
        await asyncio.to_thread(
            self.db.update_trivia_user_stats,
            guild_id,
            user_id,
            username,
            questions_answered,
            correct_answers,
            total_points,
            avg_time,
            best_streak,
            topic,
            is_winner
        )
