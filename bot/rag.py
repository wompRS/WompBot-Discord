"""
RAG (Retrieval Augmented Generation) System
Provides semantic search, conversation summarization, and intelligent context retrieval
"""

import os
import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import openai
from pgvector.psycopg2 import register_vector
from psycopg2.extras import RealDictCursor
import numpy as np

logger = logging.getLogger(__name__)


class RAGSystem:
    """Handles embeddings, semantic search, and intelligent context retrieval"""

    def __init__(self, database, llm_client):
        """
        Initialize RAG system

        Args:
            database: Database instance
            llm_client: LLM client for summarization
        """
        self.db = database
        self.llm = llm_client

        # Get OpenAI API key from environment
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not set - RAG system will be disabled")
            self.enabled = False
            return

        # Initialize OpenAI client
        try:
            self.client = openai.OpenAI(api_key=self.openai_api_key)
            self.enabled = True
        except Exception as e:
            logger.error("Error initializing OpenAI client: %s", e)
            logger.warning("RAG system will be disabled")
            self.enabled = False
            return

        # Configuration
        self.embedding_model = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
        self.embedding_dimension = 1536  # text-embedding-3-small dimension
        self.max_embedding_batch_size = 200  # Increased for dedicated server (was 100)
        self.similarity_threshold = float(os.getenv('RAG_SIMILARITY_THRESHOLD', '0.7'))

        logger.info("RAG system initialized (model: %s)", self.embedding_model)

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text using OpenAI

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if error
        """
        if not self.enabled or not text or len(text.strip()) == 0:
            return None

        try:
            # Run in thread to avoid blocking
            response = await asyncio.to_thread(
                self.client.embeddings.create,
                input=text[:8000],  # Limit to 8000 chars to avoid token limits
                model=self.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("Error generating embedding: %s", e)
            return None

    async def generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (None for failed embeddings)
        """
        if not self.enabled or not texts:
            return [None] * len(texts)

        # Filter empty texts
        valid_texts = [(i, text[:8000]) for i, text in enumerate(texts) if text and len(text.strip()) > 0]
        if not valid_texts:
            return [None] * len(texts)

        # Process in batches
        embeddings = [None] * len(texts)

        for batch_start in range(0, len(valid_texts), self.max_embedding_batch_size):
            batch = valid_texts[batch_start:batch_start + self.max_embedding_batch_size]
            batch_texts = [text for _, text in batch]

            try:
                response = await asyncio.to_thread(
                    self.client.embeddings.create,
                    input=batch_texts,
                    model=self.embedding_model
                )

                # Map embeddings back to original indices
                for (original_idx, _), embedding_data in zip(batch, response.data):
                    embeddings[original_idx] = embedding_data.embedding

            except Exception as e:
                logger.error("Error generating embeddings batch: %s", e)

        return embeddings

    async def store_message_embedding(self, message_id: int, embedding: List[float]) -> bool:
        """
        Store embedding for a message

        Args:
            message_id: Message ID
            embedding: Embedding vector

        Returns:
            True if successful
        """
        try:
            with self.db.get_connection() as conn:
                register_vector(conn)
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO message_embeddings (message_id, embedding)
                        VALUES (%s, %s)
                        ON CONFLICT (message_id) DO UPDATE
                        SET embedding = EXCLUDED.embedding,
                            updated_at = CURRENT_TIMESTAMP
                    """, (message_id, embedding))
                    conn.commit()
            return True
        except Exception as e:
            logger.error("Error storing embedding: %s", e)
            return False

    async def process_embedding_queue(self, limit: int = 50) -> int:
        """
        Process pending messages in embedding queue

        Args:
            limit: Maximum number of messages to process

        Returns:
            Number of embeddings generated
        """
        if not self.enabled:
            return 0

        try:
            # Get messages needing embeddings
            with self.db.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT eq.id, eq.message_id, m.content
                        FROM embedding_queue eq
                        JOIN messages m ON m.message_id = eq.message_id
                        WHERE eq.attempts < 3
                        ORDER BY eq.priority ASC, eq.created_at ASC
                        LIMIT %s
                    """, (limit,))
                    queue_items = cur.fetchall()

            if not queue_items:
                return 0

            logger.info("Processing %d messages for embedding...", len(queue_items))

            # Generate embeddings
            texts = [item['content'] for item in queue_items]
            embeddings = await self.generate_embeddings_batch(texts)

            # Store embeddings and update queue
            success_count = 0
            for item, embedding in zip(queue_items, embeddings):
                if embedding:
                    if await self.store_message_embedding(item['message_id'], embedding):
                        # Remove from queue
                        with self.db.get_connection() as conn:
                            with conn.cursor() as cur:
                                cur.execute("DELETE FROM embedding_queue WHERE id = %s", (item['id'],))
                                conn.commit()
                        success_count += 1
                else:
                    # Increment attempt count
                    with self.db.get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE embedding_queue
                                SET attempts = attempts + 1,
                                    last_error = 'Failed to generate embedding'
                                WHERE id = %s
                            """, (item['id'],))
                            conn.commit()

            logger.info("Generated %d/%d embeddings", success_count, len(queue_items))
            return success_count

        except Exception as e:
            logger.error("Error processing embedding queue: %s", e)
            return 0

    async def semantic_search(
        self,
        query: str,
        channel_id: Optional[int] = None,
        user_id: Optional[int] = None,
        limit: int = 5,
        max_age_days: Optional[int] = 90
    ) -> List[Dict]:
        """
        Search for semantically similar messages

        Args:
            query: Search query
            channel_id: Limit to specific channel
            user_id: Limit to specific user
            limit: Maximum results
            max_age_days: Maximum age of messages in days

        Returns:
            List of relevant messages with similarity scores
        """
        if not self.enabled:
            return []

        try:
            # Generate query embedding
            query_embedding = await self.generate_embedding(query)
            if not query_embedding:
                return []

            # Build search query - params order: query_embedding, WHERE values, query_embedding, limit
            params = [query_embedding]
            where_clauses = []

            if channel_id:
                where_clauses.append("m.channel_id = %s")
                params.append(channel_id)

            if user_id:
                where_clauses.append("m.user_id = %s")
                params.append(user_id)

            if max_age_days:
                cutoff_date = datetime.now() - timedelta(days=max_age_days)
                where_clauses.append("m.timestamp >= %s")
                params.append(cutoff_date)

            # Add query_embedding again for ORDER BY and limit at the end
            params.extend([query_embedding, limit])

            # SAFETY: where_clauses only contains hardcoded SQL fragments defined above
            # (e.g., "m.channel_id = %s", "m.user_id = %s", "m.timestamp >= %s").
            # No user input is ever interpolated into the clause structure itself;
            # all user-supplied values are passed via parameterized %s placeholders
            # in the params list, which are handled safely by psycopg2.
            where_clause = " AND " + " AND ".join(where_clauses) if where_clauses else ""

            # Perform vector similarity search
            with self.db.get_connection() as conn:
                register_vector(conn)
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Use cosine similarity - cast parameters to vector type
                    cur.execute(f"""
                        SELECT
                            m.message_id,
                            m.user_id,
                            m.username,
                            m.content,
                            m.timestamp,
                            (1 - (me.embedding <=> %s::vector)) as similarity
                        FROM message_embeddings me
                        JOIN messages m ON m.message_id = me.message_id
                        {where_clause}
                        ORDER BY me.embedding <=> %s::vector
                        LIMIT %s
                    """, params)
                    results = cur.fetchall()

            # Filter by similarity threshold
            filtered_results = [
                dict(r) for r in results
                if r['similarity'] >= self.similarity_threshold
            ]

            return filtered_results

        except Exception as e:
            logger.error("Error in semantic search: %s", e)
            return []

    async def summarize_conversation(
        self,
        channel_id: int,
        start_time: datetime,
        end_time: datetime,
        user_id: Optional[int] = None
    ) -> Optional[str]:
        """
        Generate AI summary of conversation segment

        Args:
            channel_id: Channel ID
            start_time: Start timestamp
            end_time: End timestamp
            user_id: Optional user filter

        Returns:
            Summary text or None
        """
        if not self.enabled:
            return None

        try:
            # Get messages in time range
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    if user_id:
                        cur.execute("""
                            SELECT username, content, timestamp
                            FROM messages
                            WHERE channel_id = %s
                              AND timestamp BETWEEN %s AND %s
                              AND user_id = %s
                            ORDER BY timestamp ASC
                        """, (channel_id, start_time, end_time, user_id))
                    else:
                        cur.execute("""
                            SELECT username, content, timestamp
                            FROM messages
                            WHERE channel_id = %s
                              AND timestamp BETWEEN %s AND %s
                            ORDER BY timestamp ASC
                        """, (channel_id, start_time, end_time))

                    messages = cur.fetchall()

            if not messages or len(messages) == 0:
                return None

            # Format messages for summarization
            conversation_text = "\n".join([
                f"[{msg['timestamp']}] {msg['username']}: {msg['content']}"
                for msg in messages
            ])

            # Generate summary using LLM
            summary_prompt = f"""Summarize this conversation in 2-3 concise sentences. Focus on key topics, decisions, and important information mentioned.

Conversation:
{conversation_text[:4000]}  # Limit to avoid token limits

Summary:"""

            # Use LLM to generate summary
            summary = await asyncio.to_thread(
                self.llm.generate_response,
                summary_prompt,
                [],  # No history needed for summarization
                None,  # No user context
                None,  # No additional context
                temperature=0.3  # Lower temperature for factual summary
            )

            # Store summary
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO conversation_summaries
                        (channel_id, user_id, summary, message_count, start_timestamp, end_timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (channel_id, user_id, start_timestamp, end_timestamp)
                        DO UPDATE SET summary = EXCLUDED.summary
                    """, (channel_id, user_id, summary, len(messages), start_time, end_time))
                    conn.commit()

            return summary

        except Exception as e:
            logger.error("Error summarizing conversation: %s", e)
            return None

    async def extract_user_facts(self, user_id: int, message_content: str, message_id: int) -> List[str]:
        """
        Extract facts about user from their message

        Args:
            user_id: User ID
            message_content: Message content
            message_id: Message ID

        Returns:
            List of extracted facts
        """
        if not self.enabled:
            return []

        try:
            # Use LLM to extract facts
            extraction_prompt = f"""Extract factual information about the user from this message. Focus on:
- Technical preferences/tools (e.g., "uses Python", "prefers Docker")
- Projects they're working on
- Problems they're facing
- Skills they have or want to learn

Message: "{message_content}"

Return ONLY a comma-separated list of short facts (5-10 words each), or "NONE" if no facts found.
Example: "uses PostgreSQL database, learning RAG systems, having Docker issues"

Facts:"""

            response = await asyncio.to_thread(
                self.llm.generate_response,
                extraction_prompt,
                [],
                None,
                None,
                temperature=0.2
            )

            # Parse response
            if not response or response.strip().upper() == "NONE":
                return []

            facts = [f.strip() for f in response.split(',') if f.strip()]

            # Store facts
            for fact in facts[:5]:  # Limit to 5 facts per message
                try:
                    with self.db.get_connection() as conn:
                        with conn.cursor() as cur:
                            # Check if similar fact exists
                            cur.execute("""
                                SELECT id, mention_count
                                FROM user_facts
                                WHERE user_id = %s AND fact = %s
                            """, (user_id, fact))
                            existing = cur.fetchone()

                            if existing:
                                # Update mention count
                                cur.execute("""
                                    UPDATE user_facts
                                    SET mention_count = mention_count + 1,
                                        last_confirmed = CURRENT_TIMESTAMP
                                    WHERE id = %s
                                """, (existing['id'],))
                            else:
                                # Insert new fact
                                cur.execute("""
                                    INSERT INTO user_facts
                                    (user_id, fact_type, fact, source_message_id, first_mentioned)
                                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                                """, (user_id, 'general', fact, message_id))

                            conn.commit()
                except Exception as e:
                    logger.warning("Error storing fact: %s", e)

            return facts

        except Exception as e:
            logger.error("Error extracting user facts: %s", e)
            return []

    async def get_relevant_context(
        self,
        query: str,
        channel_id: int,
        user_id: int,
        limit: int = 3
    ) -> Dict[str, any]:
        """
        Get relevant context for a query using RAG

        Args:
            query: User's query/message
            channel_id: Channel ID
            user_id: User ID
            limit: Max number of relevant messages

        Returns:
            Dict with semantic_matches, user_facts, recent_summary
        """
        if not self.enabled:
            return {
                'semantic_matches': [],
                'user_facts': [],
                'recent_summary': None
            }

        try:
            # 1. Semantic search for relevant past messages
            semantic_matches = await self.semantic_search(
                query,
                channel_id=channel_id,
                limit=limit
            )

            # 2. Get user facts
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT fact, confidence, mention_count
                        FROM user_facts
                        WHERE user_id = %s
                        ORDER BY confidence DESC, mention_count DESC
                        LIMIT 10
                    """, (user_id,))
                    user_facts = cur.fetchall()

            # 3. Get recent conversation summary (if exists)
            recent_summary = None
            cutoff_time = datetime.now() - timedelta(hours=24)
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT summary
                        FROM conversation_summaries
                        WHERE channel_id = %s
                          AND start_timestamp >= %s
                        ORDER BY end_timestamp DESC
                        LIMIT 1
                    """, (channel_id, cutoff_time))
                    summary_row = cur.fetchone()
                    if summary_row:
                        recent_summary = summary_row['summary']

            return {
                'semantic_matches': semantic_matches,
                'user_facts': [dict(f) for f in user_facts] if user_facts else [],
                'recent_summary': recent_summary
            }

        except Exception as e:
            logger.error("Error getting relevant context: %s", e)
            return {
                'semantic_matches': [],
                'user_facts': [],
                'recent_summary': None
            }
