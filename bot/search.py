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
