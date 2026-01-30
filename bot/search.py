import os
import requests
from tavily import TavilyClient

class SearchEngine:
    def __init__(self):
        # Determine which search provider to use
        self.provider = os.getenv('SEARCH_PROVIDER', 'tavily').lower()

        if self.provider == 'google':
            self.google_api_key = os.getenv('GOOGLE_SEARCH_API_KEY')
            self.google_cx = os.getenv('GOOGLE_SEARCH_CX')
            if not self.google_api_key or not self.google_cx:
                print("⚠️ Google Search API key or CX not configured, falling back to Tavily")
                self.provider = 'tavily'

        if self.provider == 'tavily':
            self.tavily_client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))

        print(f"🔍 Search provider: {self.provider.upper()}")

    def search(self, query, max_results=7):
        """Search the web using configured provider"""
        if self.provider == 'google':
            return self._search_google(query, max_results)
        else:
            return self._search_tavily(query, max_results)

    def _search_google(self, query, max_results=7):
        """Search using Google Custom Search API"""
        try:
            print(f"🔍 Google Search: {query}")

            # Google Custom Search API endpoint
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': self.google_api_key,
                'cx': self.google_cx,
                'q': query,
                'num': min(max_results, 10)  # Google max is 10 per request
            }

            response = requests.get(url, params=params, timeout=10)
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

            print(f"✅ Found {len(results)} Google results")
            return results

        except requests.exceptions.RequestException as e:
            print(f"❌ Google Search error: {type(e).__name__}: {e}")
            return []
        except Exception as e:
            print(f"❌ Search error: {type(e).__name__}: {e}")
            return []

    def _search_tavily(self, query, max_results=7):
        """Search using Tavily (fallback/default)"""
        try:
            print(f"🔍 Tavily Search: {query}")
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

            print(f"✅ Found {len(results)} Tavily results")
            return results
        except Exception as e:
            print(f"❌ Tavily search error: {type(e).__name__}: {e}")
            return []

    def build_contextual_query(self, user_message, conversation_history=None, max_context_msgs=5):
        """
        Build a better search query by incorporating conversation context.

        For follow-up questions like "when is iracings?" after asking about VLN,
        this will produce "iRacing VLN schedule 2026" instead of just "when is iracings".

        Args:
            user_message: The current user message
            conversation_history: Recent conversation messages (list of dicts with 'content')
            max_context_msgs: Max recent messages to consider for context

        Returns:
            Enhanced search query string
        """
        import re

        # Start with the user's message, cleaned up
        query = user_message.strip()

        # Remove common filler words/phrases for better search
        filler_patterns = [
            r"^wompbot\s+", r"^womp bot\s+", r"^hey\s+", r"^hi\s+", r"^yo\s+",
            r"^can you\s+", r"^could you\s+", r"^please\s+", r"^tell me\s+",
            r"^what about\s+", r"^how about\s+", r"^do you know\s+",
            r"^i want to know\s+", r"^i need to know\s+", r"^find out\s+",
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
                print(f"🔍 Enhanced search query: '{query}' → '{enhanced_query}'")
                return enhanced_query

        return query

    def _is_followup_question(self, query_lower):
        """Detect if a query is likely a follow-up question needing context."""
        import re

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
        import re

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
        """Format search results for inclusion in LLM prompt"""
        if not results:
            return "No search results found."

        formatted_lines = ["Search Results (cross-reference at least 2 sources):\n\n"]
        total_chars = len(formatted_lines[0])
        max_chars = 2000  # Increased to fit more sources for corroboration

        for i, result in enumerate(results, 1):
            snippet = result.get("content", "")[:350].strip()
            source_domain = result.get('url', 'N/A').split('/')[2] if result.get('url') else 'Unknown'
            entry = (
                f"[{i}] {result.get('title', 'Untitled')}\n"
                f"    Source: {source_domain}\n"
                f"    URL: {result.get('url', 'N/A')}\n"
                f"    Content: {snippet}...\n\n"
            )
            formatted_lines.append(entry)
            total_chars += len(entry)
            if total_chars >= max_chars:
                break

        return "".join(formatted_lines)
