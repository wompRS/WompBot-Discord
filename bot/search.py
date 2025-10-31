import os
from tavily import TavilyClient

class SearchEngine:
    def __init__(self):
        self.client = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))
    
    def search(self, query, max_results=5):
        """Search the web using Tavily"""
        try:
            print(f"🔍 Searching: {query}")
            response = self.client.search(
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
            
            print(f"✅ Found {len(results)} results")
            return results
        except Exception as e:
            print(f"❌ Search error: {type(e).__name__}: {e}")
            return []

    def format_results_for_llm(self, results):
        """Format search results for inclusion in LLM prompt"""
        if not results:
            return "No search results found."

        formatted_lines = ["Search Results:\n"]
        total_chars = len(formatted_lines[0])
        max_chars = 1500

        for i, result in enumerate(results, 1):
            snippet = result.get("content", "")[:300].strip()
            entry = (
                f"{i}. {result.get('title', 'Untitled')}\n"
                f"   URL: {result.get('url', 'N/A')}\n"
                f"   {snippet}...\n\n"
            )
            formatted_lines.append(entry)
            total_chars += len(entry)
            if total_chars >= max_chars:
                break

        return "".join(formatted_lines)
