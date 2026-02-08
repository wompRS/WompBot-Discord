"""
Chat Statistics Module
Provides network graphs, topic trends, primetime analysis, and engagement metrics
"""

import re
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import List, Dict, Optional, Tuple
import json

class ChatStatistics:
    def __init__(self, db):
        self.db = db

    def parse_date_range(self, date_input: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Parse date input as either days (int) or date range (MM/DD/YYYY-MM/DD/YYYY)

        Args:
            date_input: Either "30" for 30 days, or "01/15/2024-02/15/2024" for custom range

        Returns:
            (start_date, end_date) tuple
        """
        try:
            # Try parsing as integer (days)
            days = int(date_input)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            return (start_date, end_date)
        except ValueError:
            pass

        # Try parsing as date range (MM/DD/YYYY-MM/DD/YYYY)
        if '-' in date_input:
            try:
                start_str, end_str = date_input.split('-')
                start_date = datetime.strptime(start_str.strip(), '%m/%d/%Y')
                end_date = datetime.strptime(end_str.strip(), '%m/%d/%Y')
                # Set end_date to end of day
                end_date = end_date.replace(hour=23, minute=59, second=59)
                return (start_date, end_date)
            except ValueError as e:
                raise ValueError(f"Invalid date format. Use MM/DD/YYYY-MM/DD/YYYY (e.g., 01/15/2024-02/15/2024)")

        raise ValueError("Date input must be number of days (e.g., '30') or date range (e.g., '01/15/2024-02/15/2024')")

    def get_cache_key(self, stat_type: str, scope: str, start_date: datetime, end_date: datetime) -> str:
        """Generate cache key for a specific stat query"""
        return f"{stat_type}:{scope}:{start_date.strftime('%Y%m%d')}:{end_date.strftime('%Y%m%d')}"

    def get_cached_stats(self, stat_type: str, scope: str, start_date: datetime, end_date: datetime) -> Optional[dict]:
        """Retrieve cached statistics if still valid"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT results, valid_until
                        FROM stats_cache
                        WHERE stat_type = %s
                          AND scope = %s
                          AND start_date = %s
                          AND end_date = %s
                          AND valid_until > NOW()
                        ORDER BY computed_at DESC
                        LIMIT 1
                    """, (stat_type, scope, start_date, end_date))

                    result = cur.fetchone()
                    if result:
                        return result[0]  # Return JSONB results

            return None
        except Exception as e:
            print(f"❌ Error retrieving cached stats: {e}")
            return None

    def cache_stats(self, stat_type: str, scope: str, start_date: datetime, end_date: datetime,
                   results: dict, cache_hours: int = 6):
        """Cache statistics results"""
        try:
            valid_until = datetime.now() + timedelta(hours=cache_hours)

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO stats_cache
                        (stat_type, scope, start_date, end_date, results, valid_until)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (stat_type, scope, start_date, end_date, json.dumps(results), valid_until))
        except Exception as e:
            print(f"❌ Error caching stats: {e}")

    def get_messages_for_analysis(self, channel_id: Optional[int], start_date: datetime,
                                  end_date: datetime, exclude_opted_out: bool = True,
                                  max_messages: int = 50000) -> List[dict]:
        """Get messages for analysis, excluding opted-out users

        Args:
            channel_id: Optional channel ID to filter by
            start_date: Start of date range
            end_date: End of date range
            exclude_opted_out: Whether to exclude opted-out users
            max_messages: Maximum number of messages to return (default 50000)
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT m.message_id, m.user_id, m.username, m.content,
                               m.timestamp, m.channel_id
                        FROM messages m
                        LEFT JOIN user_profiles up ON up.user_id = m.user_id
                        WHERE m.timestamp BETWEEN %s AND %s
                    """
                    params = [start_date, end_date]

                    if exclude_opted_out:
                        query += " AND COALESCE(m.opted_out, FALSE) = FALSE AND COALESCE(up.opted_out, FALSE) = FALSE"

                    if channel_id:
                        query += " AND m.channel_id = %s"
                        params.append(channel_id)

                    query += " ORDER BY m.timestamp ASC LIMIT %s"
                    params.append(max_messages)

                    cur.execute(query, params)

                    columns = [desc[0] for desc in cur.description]
                    results = cur.fetchall()

                    return [dict(zip(columns, row)) for row in results]
        except Exception as e:
            print(f"❌ Error fetching messages: {e}")
            return []

    def extract_topics_tfidf(self, messages: List[dict], top_n: int = 20) -> List[dict]:
        """
        Extract trending topics using TF-IDF (keyword extraction)

        Args:
            messages: List of message dicts with 'content' field
            top_n: Number of top keywords to return

        Returns:
            List of {keyword, score, count} dicts
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            # Combine all message content
            texts = [msg['content'] for msg in messages if msg.get('content')]

            if not texts:
                return []

            # Custom stopwords (common Discord/chat words to ignore)
            custom_stopwords = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
                'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                'should', 'could', 'may', 'might', 'must', 'can', 'it', 'this', 'that',
                'these', 'those', 'i', 'you', 'he', 'she', 'we', 'they', 'them', 'their',
                'what', 'which', 'who', 'when', 'where', 'why', 'how', 'all', 'each',
                'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
                'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just',
                'lol', 'lmao', 'lmfao', 'yeah', 'yea', 'nah', 'bruh', 'bro', 'tbh', 'imo',
                'like', 'literally', 'actually', 'basically', 'thing', 'things', 'gonna',
                'wanna', 'kinda', 'sorta'
            }

            # TF-IDF vectorizer (with graceful fallback for sparse chats)
            vectorizer_kwargs = dict(
                max_features=top_n * 2,  # Get more candidates
                stop_words=list(custom_stopwords),
                ngram_range=(1, 2),  # Unigrams and bigrams
                min_df=2,  # Must appear in at least 2 messages
                max_df=0.7,  # Ignore if appears in >70% of messages
                token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z]+\b'  # Only alphabetic words
            )

            vectorizer = TfidfVectorizer(**vectorizer_kwargs)

            # Fit and transform with fallback when the sample is tiny
            try:
                tfidf_matrix = vectorizer.fit_transform(texts)
            except ValueError as err:
                if "After pruning, no terms remain" in str(err):
                    fallback_kwargs = dict(vectorizer_kwargs)
                    fallback_kwargs.update({'min_df': 1, 'max_df': 1.0})
                    vectorizer = TfidfVectorizer(**fallback_kwargs)
                    tfidf_matrix = vectorizer.fit_transform(texts)
                else:
                    raise

            feature_names = vectorizer.get_feature_names_out()

            # Calculate average TF-IDF score for each term
            avg_scores = tfidf_matrix.mean(axis=0).A1

            # Count actual occurrences
            word_counts = Counter()
            for text in texts:
                words = re.findall(r'\b[a-zA-Z][a-zA-Z]+\b', text.lower())
                word_counts.update(words)

            # Combine scores and counts
            topics = []
            for idx, score in enumerate(avg_scores):
                keyword = feature_names[idx]
                # For bigrams, count occurrences in original text
                if ' ' in keyword:
                    count = sum(1 for text in texts if keyword in text.lower())
                else:
                    count = word_counts.get(keyword, 0)

                topics.append({
                    'keyword': keyword,
                    'score': float(score),
                    'count': count
                })

            # Sort by score and return top_n
            topics.sort(key=lambda x: x['score'], reverse=True)
            return topics[:top_n]

        except ImportError:
            print("❌ scikit-learn not installed. Install with: pip install scikit-learn")
            return []
        except Exception as e:
            print(f"❌ Error extracting topics: {e}")
            import traceback
            traceback.print_exc()
            return []

    def build_network_graph(self, messages: List[dict], exclude_from_ranking: bool = True) -> dict:
        """
        Build interaction network graph from messages

        Args:
            messages: List of message dicts with user_id, username, content, channel_id
            exclude_from_ranking: If True, excludes bot from top rankings (default True)

        Returns:
            {
                'edges': [(user1, user2, weight), ...],
                'nodes': {user_id: {'username': str, 'degree': int, 'messages': int}},
                'bot_stats': {'user_id': int, 'username': str, 'degree': int, 'messages': int} or None
            }
        """
        try:
            import networkx as nx

            G = nx.DiGraph()
            user_messages = Counter()
            bot_user_id = self.db.bot_user_id if exclude_from_ranking else None

            # Build graph from message sequence (proximity-based connections)
            for i, msg in enumerate(messages):
                user_id = msg['user_id']
                username = msg['username']
                user_messages[user_id] += 1

                # Add node if not exists
                if not G.has_node(user_id):
                    G.add_node(user_id, username=username)

                # Check for @mentions in content
                mentions = re.findall(r'<@!?(\d+)>', msg.get('content', ''))
                for mentioned_id in mentions:
                    mentioned_id_int = int(mentioned_id)
                    if G.has_edge(user_id, mentioned_id_int):
                        G[user_id][mentioned_id_int]['weight'] += 1
                    else:
                        G.add_edge(user_id, mentioned_id_int, weight=1)

                # Conversation proximity: connect to previous messengers in same channel
                # (last 3 messages in same channel)
                lookback = min(i, 3)
                for j in range(i - lookback, i):
                    if j >= 0 and messages[j]['channel_id'] == msg['channel_id']:
                        prev_user = messages[j]['user_id']
                        if prev_user != user_id:
                            if G.has_edge(user_id, prev_user):
                                G[user_id][prev_user]['weight'] += 0.5
                            else:
                                G.add_edge(user_id, prev_user, weight=0.5)

            # Fetch usernames from user_profiles table (preserves usernames even if user left)
            user_ids = list(G.nodes())
            username_map = {}

            try:
                with self.db.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT user_id, username
                            FROM user_profiles
                            WHERE user_id = ANY(%s)
                        """, (user_ids,))

                        for user_id, username in cur.fetchall():
                            username_map[user_id] = username
            except Exception as e:
                print(f"⚠️ Error fetching usernames from profiles: {e}")

            # Calculate metrics
            nodes = {}
            bot_stats = None
            for node in G.nodes():
                degree = G.degree(node)
                # Prioritize: 1) user_profiles username, 2) graph username, 3) fallback to User ID
                username = username_map.get(node) or G.nodes[node].get('username') or f'User {node}'
                node_data = {
                    'username': username,
                    'degree': degree,
                    'messages': user_messages[node]
                }

                # Separate bot stats from main rankings
                if bot_user_id and node == bot_user_id:
                    bot_stats = {'user_id': node, **node_data}
                else:
                    nodes[node] = node_data

            # Get edges with weights
            edges = [(u, v, d['weight']) for u, v, d in G.edges(data=True)]

            return {
                'edges': edges,
                'nodes': nodes,
                'bot_stats': bot_stats  # Tracked separately, not in rankings
            }

        except ImportError:
            print("❌ networkx not installed. Install with: pip install networkx")
            return {'edges': [], 'nodes': {}, 'bot_stats': None}
        except Exception as e:
            print(f"❌ Error building network graph: {e}")
            import traceback
            traceback.print_exc()
            return {'edges': [], 'nodes': {}, 'bot_stats': None}

    def calculate_primetime(self, messages: List[dict]) -> dict:
        """
        Calculate activity patterns (hourly heatmap, day of week breakdown)

        Returns:
            {
                'hourly': {0: count, 1: count, ...},
                'daily': {0: count, 1: count, ...},  # 0=Monday
                'peak_hour': int,
                'peak_day': int
            }
        """
        hourly = Counter()
        daily = Counter()

        for msg in messages:
            timestamp = msg['timestamp']
            hourly[timestamp.hour] += 1
            daily[timestamp.weekday()] += 1

        peak_hour = hourly.most_common(1)[0][0] if hourly else 0
        peak_day = daily.most_common(1)[0][0] if daily else 0

        return {
            'hourly': dict(hourly),
            'daily': dict(daily),
            'peak_hour': peak_hour,
            'peak_day': peak_day,
            'total_messages': len(messages)
        }

    def calculate_engagement(self, messages: List[dict], exclude_from_ranking: bool = True) -> dict:
        """
        Calculate engagement metrics

        Args:
            messages: List of message dicts
            exclude_from_ranking: If True, excludes bot from top_responders ranking

        Returns:
            {
                'avg_message_length': float,
                'total_messages': int,
                'unique_users': int,
                'avg_messages_per_user': float,
                'top_responders': [(username, response_count), ...],
                'bot_responses': int or None  # Bot's response count tracked separately
            }
        """
        bot_user_id = self.db.bot_user_id if exclude_from_ranking else None

        total_length = sum(len(msg.get('content', '')) for msg in messages)
        unique_users = len(set(msg['user_id'] for msg in messages if not (bot_user_id and msg['user_id'] == bot_user_id)))

        # Calculate conversation threads (messages within 5 minutes)
        user_responses = Counter()
        bot_responses = 0
        for i in range(1, len(messages)):
            current = messages[i]
            previous = messages[i-1]

            # If same channel, different user, within 5 minutes = likely response
            if (current['channel_id'] == previous['channel_id'] and
                current['user_id'] != previous['user_id'] and
                (current['timestamp'] - previous['timestamp']).total_seconds() < 300):
                # Track bot responses separately
                if bot_user_id and current['user_id'] == bot_user_id:
                    bot_responses += 1
                else:
                    user_responses[current['username']] += 1

        return {
            'avg_message_length': total_length / len(messages) if messages else 0,
            'total_messages': len(messages),
            'unique_users': unique_users,
            'avg_messages_per_user': len(messages) / unique_users if unique_users > 0 else 0,
            'top_responders': user_responses.most_common(10),
            'bot_responses': bot_responses if bot_user_id else None  # Tracked separately
        }

    def format_as_discord_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """
        Format data as Discord markdown table

        Args:
            headers: List of column headers
            rows: List of rows (each row is a list of values)

        Returns:
            Formatted markdown table string
        """
        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        # Build table
        lines = []

        # Header
        header_line = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
        lines.append(header_line)

        # Separator
        separator = "|" + "|".join("-" * (w + 2) for w in col_widths) + "|"
        lines.append(separator)

        # Rows
        for row in rows:
            row_line = "| " + " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)) + " |"
            lines.append(row_line)

        return "```\n" + "\n".join(lines) + "\n```"
