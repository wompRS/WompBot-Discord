import logging
import os
import re

import requests
from tavily import TavilyClient

logger = logging.getLogger(__name__)

class SearchEngine:
    def __init__(self):
        # Determine which search provider to use
        self.provider = os.getenv('SEARCH_PROVIDER', 'tavily').lower()

        if self.provider == 'google':
            self.google_api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
            self.google_cx = os.getenv('GOOGLE_SEARCH_CX')
            if not self.google_api_key or not self.google_cx:
                logger.warning("Google Search API key or CX not configured, falling back to Tavily")
                self.provider = 'tavily'

        if self.provider == 'tavily':
            self.tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))

        # Reusable HTTP session for connection pooling (avoids redundant TCP+TLS handshakes)
        self.session = requests.Session()

        logger.info("Search provider: %s", self.provider.upper())

    def search(self, query, max_results=5):
        """Search the web using configured provider"""
        if self.provider == 'google':
            return self._search_google(query, max_results)
        else:
            return self._search_tavily(query, max_results)

    def _search_google(self, query, max_results=5):
        """Search using Google Custom Search API"""
        try:
            logger.info("Google Search: %s", query)

            # Google Custom Search API endpoint
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': self.google_api_key,
                'cx': self.google_cx,
                'q': query,
                'num': min(max_results, 10)  # Google max is 10 per request
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = []
            if 'items' in data:
                for item in data['items']:
                    # Extract snippet from either snippet or htmlSnippet
                    snippet = item.get('snippet', '')
                    if not snippet:
                        snippet = item.get('htmlSnippet', '').replace('<b>', '').replace('</b>', '')

                    results.append({
                        'title': item.get('title', ''),
                        'url': item.get('link', ''),
                        'content': snippet,
                        'score': 1.0  # Google doesn't provide relevance scores
                    })

            logger.info("Found %d Google results", len(results))
            return results

        except requests.exceptions.RequestException as e:
            logger.error("Google Search error: %s: %s", type(e).__name__, e)
            return []
        except Exception as e:
            logger.error("Search error: %s: %s", type(e).__name__, e)
            return []

    def _search_tavily(self, query, max_results=5):
        """Search using Tavily (fallback/default)"""
        try:
            logger.info("Tavily Search: %s", query)
            response = self.tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results
            )

            results = []
            if response and 'results' in response:
                for result in response['results']:
                    results.append({
                        'title': result.get('title', ''),
                        'url': result.get('url', ''),
                        'content': result.get('content', ''),
                        'score': result.get('score', 0)
                    })

            logger.info("Found %d Tavily results", len(results))
            return results
        except Exception as e:
            logger.error("Tavily search error: %s: %s", type(e).__name__, e)
            return []

    def build_contextual_query(self, user_message, conversation_history=None, max_context_msgs=5):
        """
        Build a better search query by incorporating conversation context.

        For follow-up questions like "when is iracings?" after asking about VLN,
        this will produce "iRacing VLN schedule 2026" instead of just "when is iracings".

        For clarifications like "aberdeen in scotland" following "when did it last rain in aberdeen",
        this will combine them into "when did it last rain aberdeen scotland".

        Args:
            user_message: The current user message
            conversation_history: Recent conversation messages (list of dicts with 'content')
            max_context_msgs: Max recent messages to consider for context

        Returns:
            Enhanced search query string
        """
        # Start with the user's message, cleaned up
        query = user_message.strip()

        # Remove common filler words/phrases for better search
        filler_patterns = [
            r"^wompbot\s+", r"^womp bot\s+", r"^hey\s+", r"^hi\s+", r"^yo\s+",
            r"^can you\s+", r"^could you\s+", r"^please\s+", r"^tell me\s+",
            r"^what about\s+", r"^how about\s+", r"^do you know\s+",
            r"^i want to know\s+", r"^i need to know\s+", r"^find out\s+",
            r"^ok\s+wompbot\s+", r"^okay\s+wompbot\s+",
        ]
        query_lower = query.lower()
        for pattern in filler_patterns:
            query = re.sub(pattern, '', query, flags=re.IGNORECASE)
        query = query.strip()
        query_lower = query.lower()

        # Detect if this is likely a follow-up question that needs context
        needs_context = self._is_followup_question(query_lower)

        # Also trigger context enhancement for short queries
        if len(query) < 25:
            needs_context = True

        if not needs_context or not conversation_history:
            return query

        # Check if this looks like a clarification/answer to a previous question
        # (short message that doesn't contain a question word but may be answering one)
        is_clarification = self._is_clarification(query_lower)

        if is_clarification:
            # Find the most recent question from conversation that this might be clarifying
            original_question = self._find_original_question(conversation_history, query_lower)
            if original_question:
                # Combine the original question with the clarification
                combined_query = self._merge_question_with_clarification(original_question, query)
                if combined_query != query:
                    logger.info("Clarification detected: '%s' -> merged with original question -> '%s'", query, combined_query)
                    return combined_query

        # Build context from recent messages (including bot responses!)
        recent_context = []
        for msg in conversation_history[-max_context_msgs:]:
            content = msg.get('content', '')
            if content:
                recent_context.append(content.lower())

        context_text = ' '.join(recent_context)

        # Extract topic keywords from context
        topic_keywords = self._extract_topic_keywords(context_text, query_lower)

        # Add relevant context keywords to the query
        if topic_keywords:
            # Deduplicate while preserving order
            seen = set()
            unique_keywords = []
            for kw in topic_keywords:
                kw_lower = kw.lower()
                if kw_lower not in seen and kw_lower not in query_lower:
                    seen.add(kw_lower)
                    unique_keywords.append(kw)

            if unique_keywords:
                # Prepend context keywords for better search relevance
                enhanced_query = ' '.join(unique_keywords[:4]) + ' ' + query
                logger.info("Enhanced search query: '%s' -> '%s'", query, enhanced_query)
                return enhanced_query

        return query

    def _is_clarification(self, query_lower):
        """
        Detect if a message looks like a clarification/answer to a previous question
        rather than a new question itself.

        Examples of clarifications:
        - "aberdeen in scotland" (clarifying which Aberdeen)
        - "the blue one" (clarifying which item)
        - "last week" (clarifying a time)
        - "python 3.11" (clarifying a version)
        """
        # Very short messages are likely clarifications
        if len(query_lower) < 30:
            # Check if it lacks question words (what, when, where, how, why, who, which, is, are, do, does, can, will)
            question_words = r'\b(what|when|where|how|why|who|which|is|are|do|does|did|can|will|would|should|could)\b'
            if not re.search(question_words, query_lower):
                return True

        # Patterns that indicate clarifications
        clarification_patterns = [
            r'^(the|a|an)\s+\w+\s*(one|version|type|kind)?$',  # "the blue one", "a newer version"
            r'^in\s+\w+',  # "in scotland", "in python"
            r'^\w+\s+in\s+\w+$',  # "aberdeen in scotland"
            r'^(last|next|this)\s+(week|month|year|time)',  # "last week"
            r'^\d+(\.\d+)?$',  # version numbers like "3.11"
            r'^(yes|no|yeah|nah|yep|nope)',  # confirmations
        ]

        for pattern in clarification_patterns:
            if re.match(pattern, query_lower):
                return True

        return False

    def _find_original_question(self, conversation_history, clarification_lower):
        """
        Find the most recent question from conversation history that the current
        clarification might be answering.
        """
        # Look through recent messages (reverse order - most recent first)
        for msg in reversed(conversation_history[-10:]):
            content = msg.get('content', '').lower()

            # Skip bot messages and very short messages
            username = msg.get('username', '').lower()
            if 'wompbot' in username or 'womp bot' in username or len(content) < 10:
                continue

            # Check if this looks like a question that could have prompted the clarification
            # Questions often contain: what, when, where, how, why, who, which, or end with ?
            question_indicators = [
                r'\b(what|when|where|how|why|who|which)\b',
                r'\?$',
                r'\b(is|are|was|were|do|does|did|can|could|will|would)\b.*\b(it|that|there)\b',
            ]

            is_question = any(re.search(pattern, content) for pattern in question_indicators)

            if is_question:
                # Check if the clarification could be answering this question
                # by looking for overlapping topics or keywords
                # Extract key nouns/topics from the question
                question_words = set(re.findall(r'\b[a-z]{3,}\b', content))
                clarification_words = set(re.findall(r'\b[a-z]{3,}\b', clarification_lower))

                # If there's overlap or the clarification seems related, return this question
                overlap = question_words & clarification_words
                if overlap or self._topics_related(content, clarification_lower):
                    return content

        return None

    def _topics_related(self, question, clarification):
        """Check if a clarification seems related to a question."""
        # Check for location clarifications (e.g., "in scotland" clarifying "aberdeen")
        location_patterns = [
            (r'\b(in|at|from)\s+(\w+)', r'\b\2\b'),  # "in scotland" -> look for that place in question
        ]

        # Extract potential location from clarification
        location_match = re.search(r'\b(in|at|from)\s+(\w+)', clarification)
        if location_match:
            # This is a location clarification - very likely related to any question
            # that mentions places or asks "where" type questions
            return True

        # Check if question mentions something the clarification specifies
        # e.g., question about "aberdeen" and clarification "scotland"
        clarification_nouns = set(re.findall(r'\b[a-z]{4,}\b', clarification))
        for noun in clarification_nouns:
            # Skip common words
            if noun in {'this', 'that', 'with', 'from', 'have', 'been', 'would', 'could', 'should'}:
                continue
            # If the noun could be clarifying something in the question
            if any(word in question for word in [noun[:4]]):  # Partial match
                return True

        return False

    def _merge_question_with_clarification(self, original_question, clarification):
        """
        Merge an original question with a clarification to create a better search query.

        Example:
        - original: "when did it last not rain in aberdeen"
        - clarification: "aberdeen in scotland"
        - result: "when did it last not rain aberdeen scotland"
        """
        # Clean up the original question
        question_clean = original_question.strip()
        # Remove bot name mentions
        question_clean = re.sub(r'\bwompbot\b|\bwomp bot\b', '', question_clean, flags=re.IGNORECASE).strip()
        # Remove filler words
        question_clean = re.sub(r'^(hey|hi|yo|ok|okay)\s+', '', question_clean, flags=re.IGNORECASE).strip()

        # Extract the key info from clarification (remove "in", "at", "from" if just specifying location)
        clarification_clean = clarification.strip()
        clarification_clean = re.sub(r'^(it\'?s?|that\'?s?|the)\s+', '', clarification_clean, flags=re.IGNORECASE).strip()

        # Build combined query
        # Take the core question and append the clarification details
        # But avoid duplicating words
        question_words = set(question_clean.lower().split())
        clarification_words = clarification_clean.lower().split()

        # Find new info from clarification not in question
        new_info = [w for w in clarification_words if w not in question_words and len(w) > 2]

        if new_info:
            combined = question_clean + ' ' + ' '.join(new_info)
            return combined

        return clarification

    def _is_followup_question(self, query_lower):
        """Detect if a query is likely a follow-up question needing context."""
        # Very short queries are almost always follow-ups
        if len(query_lower) < 20:
            return True

        # Queries starting with pronouns or references to previous content
        followup_starters = [
            r"^(what|when|where|how|why|who)\s+(is|are|was|were|about)\s+(it|that|this|their|its|the)\b",
            r"^(what|when|where|how|why|who)\s+(is|are|was|were)\s+\w+('s|s)\??$",  # "when is iracings?"
            r"^and\s+",
            r"^but\s+",
            r"^also\s+",
            r"^what about\s+",
            r"^how about\s+",
            r"^same\s+",
            r"^(for|in|on|at)\s+(that|this|it|the)\b",
        ]

        for pattern in followup_starters:
            if re.search(pattern, query_lower):
                return True

        # Queries with possessive references (e.g., "when is iracings" - missing apostrophe)
        # or referencing something mentioned before
        possessive_patterns = [
            r"\b(their|its|his|her)\b",
            r"\b\w+'s\b",  # possessives like "iracing's"
            r"\b\w+s\?$",  # ends with "s?" like "iracings?"
        ]

        for pattern in possessive_patterns:
            if re.search(pattern, query_lower):
                return True

        return False

    def _extract_topic_keywords(self, context_text, query_lower):
        """Extract relevant topic keywords from conversation context."""
        topic_keywords = []

        # Static topic patterns - common subjects that should carry forward
        static_patterns = [
            # Motorsport/Racing - expanded
            ('vln', 'VLN'),
            ('nls', 'NLS'),
            ('nürburgring', 'Nürburgring'),
            ('nurburgring', 'Nürburgring'),
            ('nordschleife', 'Nordschleife'),
            ('iracing', 'iRacing'),
            ('i-racing', 'iRacing'),
            ('gt3', 'GT3'),
            ('gt4', 'GT4'),
            ('gte', 'GTE'),
            ('lmp', 'LMP'),
            ('hypercar', 'Hypercar'),
            ('imsa', 'IMSA'),
            ('wec', 'WEC'),
            ('elms', 'ELMS'),
            ('f1', 'Formula 1'),
            ('formula 1', 'Formula 1'),
            ('formula one', 'Formula 1'),
            ('indycar', 'IndyCar'),
            ('indy 500', 'Indy 500'),
            ('nascar', 'NASCAR'),
            ('cup series', 'NASCAR Cup'),
            ('xfinity', 'NASCAR Xfinity'),
            ('le mans', 'Le Mans'),
            ('24 hours', '24 Hours'),
            ('daytona', 'Daytona'),
            ('sebring', 'Sebring'),
            ('spa', 'Spa'),
            ('bathurst', 'Bathurst'),
            ('suzuka', 'Suzuka'),
            ('monza', 'Monza'),
            ('silverstone', 'Silverstone'),
            ('laguna seca', 'Laguna Seca'),
            ('road america', 'Road America'),
            ('watkins glen', 'Watkins Glen'),
            ('v8 supercars', 'V8 Supercars'),
            ('supercars', 'Supercars'),
            ('dtm', 'DTM'),
            ('btcc', 'BTCC'),
            ('touring car', 'Touring Car'),
            ('endurance', 'endurance'),
            ('sprint', 'sprint race'),

            # Sim racing specific
            ('acc', 'ACC'),
            ('assetto corsa', 'Assetto Corsa'),
            ('rfactor', 'rFactor'),
            ('automobilista', 'Automobilista'),
            ('project cars', 'Project Cars'),

            # Schedule/time related
            ('schedule', 'schedule'),
            ('race', 'race'),
            ('season', 'season'),
            ('calendar', 'calendar'),
            ('round', 'round'),
            ('week', 'week'),

            # Years
            ('2024', '2024'),
            ('2025', '2025'),
            ('2026', '2026'),
            ('2027', '2027'),

            # Tech
            ('python', 'Python'),
            ('javascript', 'JavaScript'),
            ('typescript', 'TypeScript'),
            ('react', 'React'),
            ('node', 'Node.js'),
            ('docker', 'Docker'),
            ('kubernetes', 'Kubernetes'),
            ('api', 'API'),
            ('database', 'database'),
            ('postgresql', 'PostgreSQL'),
            ('mysql', 'MySQL'),
            ('redis', 'Redis'),
            ('aws', 'AWS'),
            ('azure', 'Azure'),
            ('gcp', 'GCP'),

            # Gaming
            ('playstation', 'PlayStation'),
            ('xbox', 'Xbox'),
            ('nintendo', 'Nintendo'),
            ('steam', 'Steam'),
            ('epic games', 'Epic Games'),
        ]

        for pattern, keyword in static_patterns:
            if pattern in context_text and pattern not in query_lower:
                topic_keywords.append(keyword)

        # Dynamic extraction: Find capitalized proper nouns and technical terms
        # from the context that might be relevant
        words_in_context = re.findall(r'\b([A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]+)*)\b', context_text)
        for word in words_in_context:
            word_lower = word.lower()
            if (len(word) > 3 and
                word_lower not in query_lower and
                word_lower not in ['the', 'and', 'for', 'that', 'this', 'with', 'from']):
                # Avoid duplicates from static patterns
                if not any(word_lower == kw.lower() for kw in topic_keywords):
                    topic_keywords.append(word)

        return topic_keywords

    def format_results_for_llm(self, results):
        """Format search results for inclusion in LLM prompt.
        Limits to top 5 results with truncated snippets to save tokens."""
        if not results:
            return "No search results found."

        formatted_lines = ["Search Results (use these to answer, cross-reference sources):\n\n"]
        total_chars = len(formatted_lines[0])
        max_chars = 1500  # Keep compact to leave room for conversation history
        max_results = 5   # Top 5 most relevant results

        for i, result in enumerate(results[:max_results], 1):
            snippet = result.get("content", "")[:200].strip()
            source_domain = result.get('url', 'N/A').split('/')[2] if result.get('url') else 'Unknown'
            entry = (
                f"[{i}] {result.get('title', 'Untitled')} ({source_domain})\n"
                f"    {snippet}\n\n"
            )
            formatted_lines.append(entry)
            total_chars += len(entry)
            if total_chars >= max_chars:
                break

        return "".join(formatted_lines)
